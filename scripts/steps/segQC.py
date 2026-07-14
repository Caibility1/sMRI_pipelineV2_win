import csv
import time
import subprocess
from pathlib import Path

import nibabel as nib


# =========================
# 安全开关
# =========================
# 本脚本只读取 NIfTI header，不修改 NAS 文件。
# DRY_RUN=True：只在终端打印结果，不写出 CSV。
# DRY_RUN=False：额外写出本地 CSV 报告。
DRY_RUN = True


# =========================
# NAS 配置
# =========================

NAS_ROOT = r"\\10.19.136.231"
USERNAME = "linm"
PASSWORD = "fGWH|1,I"
CONNECT_NAS = True


# =========================
# 数据集路径配置
# =========================

SEG_DIR = Path(
    r"\\10.19.136.231\002\XUXIU_ASD\2_Processing\1_sMRI\4_sMRI_segmentation"
    #r"\\10.19.136.231\002\CBCP\CBCP_MRI\4_VisualQC_Processing\Site1_STU\1_sMRI\4_sMRI_segmentation\4_uAI_version2"
)

# 严格按你确认的两套尺寸判断
ACPC_SHAPE = (243, 291, 198)
RAW_SHAPE = (208, 300, 320)


# =========================
# 文件名配置
# =========================
# brain: brain.nii.gz
# mask: 兼容 mask / tissue
# dk_struct: 兼容 dk-struct / dk_struct

REQUIRED_FILES = {
    "brain": [
        "brain.nii.gz",
        "brain.nii",
    ],
    "mask": [
        "mask.nii.gz",
        "mask.nii",
        "tissue.nii.gz",
        "tissue.nii",
    ],
    "dk_struct": [
        "dk-struct.nii.gz",
        "dk-struct.nii",
        "dk_struct.nii.gz",
        "dk_struct.nii",
    ],
}


# =========================
# NAS 保护参数
# =========================
# 串行读取 header，不开多进程，避免压 NAS。
# 如果觉得太慢，可以把 SLEEP_SECONDS_PER_CASE 改成 0。
SLEEP_SECONDS_PER_CASE = 0.01

# 先抽检时可以设成 10 / 50 等；全量检查设为 None。
MAX_CASES = None

REPORT_CSV = "segmentation_dim_check_report.csv"


def run_cmd(cmd):
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="ignore",
        shell=False,
    )
    return result


def connect_nas():
    cmd = [
        "net",
        "use",
        NAS_ROOT,
        PASSWORD,
        f"/user:{USERNAME}",
        "/persistent:no",
    ]

    result = run_cmd(cmd)

    if result.returncode == 0:
        print(f"[OK] 已连接 NAS：{NAS_ROOT}")
        return True

    output = (result.stdout or "") + "\n" + (result.stderr or "")

    if "命令成功完成" in output or "The command completed successfully" in output:
        print(f"[OK] 已连接 NAS：{NAS_ROOT}")
        return True

    if "已存在" in output or "multiple connections" in output.lower() or "1219" in output:
        print("[提示] NAS 可能已经连接过，尝试继续访问目录。")
        return True

    print("[警告] NAS 自动连接失败。")
    print("stdout:")
    print(result.stdout)
    print("stderr:")
    print(result.stderr)
    print("如果后面目录仍然能访问，可以忽略；否则请检查账密或 NAS 连接状态。")
    return False


def find_existing_file(case_dir: Path, candidates):
    for name in candidates:
        p = case_dir / name
        if p.is_file():
            return p
    return None


def read_nii_header_info(path: Path):
    """
    只读取 NIfTI header，不读取完整 image data。

    不要在这里使用：
    - img.get_fdata()
    - np.asarray(img.dataobj)

    这类操作会真正读取体素数据，可能明显增加 NAS 压力。
    """
    img = nib.load(str(path))

    shape = tuple(int(x) for x in img.shape[:3])
    zooms = tuple(float(x) for x in img.header.get_zooms()[:3])
    dtype = str(img.get_data_dtype())
    size_mb = path.stat().st_size / 1024 / 1024

    return {
        "shape": shape,
        "zooms": zooms,
        "dtype": dtype,
        "size_mb": size_mb,
    }


def shape_to_str(shape):
    if shape is None:
        return ""
    return "x".join(str(x) for x in shape)


def zooms_to_str(zooms):
    if zooms is None:
        return ""
    return "x".join(f"{x:.4g}" for x in zooms)


def classify_case(file_infos, missing_files, unreadable_files):
    """
    分类规则：

    CORRECT:
        brain / mask / dk-struct 三者都存在、都可读、shape 完全一致，
        且 shape == ACPC_SHAPE，也就是 198×243×291。

    MATCH_BUT_RAW_SHAPE:
        三者 shape 完全一致，但 shape == RAW_SHAPE，也就是 320×208×300。
        说明 segmentation 内部自洽，但处于原始 T1/T2 grid，不符合当前 ACPC pipeline 预期。

    MATCH_BUT_OTHER_WRONG_SHAPE:
        三者 shape 完全一致，但既不是 ACPC_SHAPE，也不是 RAW_SHAPE。

    MISMATCH:
        三者都能读，但 shape 不完全一致。

    MISSING:
        有文件缺失。

    UNREADABLE:
        文件存在但 header 读取失败。
    """

    if missing_files:
        return "MISSING"

    if unreadable_files:
        return "UNREADABLE"

    shapes = {
        key: value["shape"]
        for key, value in file_infos.items()
    }

    unique_shapes = set(shapes.values())

    if len(unique_shapes) != 1:
        return "MISMATCH"

    only_shape = next(iter(unique_shapes))

    if only_shape == ACPC_SHAPE:
        return "CORRECT"

    if only_shape == RAW_SHAPE:
        return "MATCH_BUT_RAW_SHAPE"

    return "MATCH_BUT_OTHER_WRONG_SHAPE"


def main():
    if CONNECT_NAS:
        connect_nas()

    if not SEG_DIR.is_dir():
        raise FileNotFoundError(f"segmentation 目录不存在或无法访问：{SEG_DIR}")

    print("\n========== 开始检查 segmentation 维度 ==========")
    print(f"SEG_DIR: {SEG_DIR}")
    print(f"ACPC_SHAPE / 正确尺寸: {ACPC_SHAPE}")
    print(f"RAW_SHAPE / 原始尺寸:  {RAW_SHAPE}")
    print(f"DRY_RUN: {DRY_RUN}")
    print("说明：本脚本只读取 NIfTI header，不读取完整体素数据，不修改 NAS 文件。")
    if DRY_RUN:
        print("DRY_RUN=True：不会写出本地 CSV，只在终端打印结果。")
    else:
        print(f"DRY_RUN=False：会额外写出本地 CSV 报告：{REPORT_CSV}")
    print("")

    case_dirs = sorted(
        [p for p in SEG_DIR.iterdir() if p.is_dir()],
        key=lambda x: x.name
    )

    if MAX_CASES is not None:
        case_dirs = case_dirs[:MAX_CASES]

    total_count = 0

    correct_count = 0
    mismatch_count = 0
    match_raw_count = 0
    match_other_wrong_count = 0
    missing_count = 0
    unreadable_count = 0

    correct_ids = []
    mismatch_items = []
    match_raw_items = []
    match_other_wrong_items = []
    missing_items = []
    unreadable_items = []

    rows = []

    for case_dir in case_dirs:
        total_count += 1
        case_id = case_dir.name

        file_paths = {}
        file_infos = {}
        missing_files = []
        unreadable_files = []

        for logical_name, candidates in REQUIRED_FILES.items():
            path = find_existing_file(case_dir, candidates)

            if path is None:
                missing_files.append(logical_name)
                file_paths[logical_name] = None
                continue

            file_paths[logical_name] = path

            try:
                info = read_nii_header_info(path)
                file_infos[logical_name] = info
            except Exception as e:
                unreadable_files.append((logical_name, repr(e)))

        status = classify_case(file_infos, missing_files, unreadable_files)

        brain_shape = file_infos.get("brain", {}).get("shape")
        mask_shape = file_infos.get("mask", {}).get("shape")
        dk_shape = file_infos.get("dk_struct", {}).get("shape")

        brain_zooms = file_infos.get("brain", {}).get("zooms")
        mask_zooms = file_infos.get("mask", {}).get("zooms")
        dk_zooms = file_infos.get("dk_struct", {}).get("zooms")

        brain_size = file_infos.get("brain", {}).get("size_mb")
        mask_size = file_infos.get("mask", {}).get("size_mb")
        dk_size = file_infos.get("dk_struct", {}).get("size_mb")

        row = {
            "case_id": case_id,
            "status": status,

            "brain_path": str(file_paths.get("brain") or ""),
            "mask_path": str(file_paths.get("mask") or ""),
            "dk_struct_path": str(file_paths.get("dk_struct") or ""),

            "brain_shape": shape_to_str(brain_shape),
            "mask_shape": shape_to_str(mask_shape),
            "dk_struct_shape": shape_to_str(dk_shape),

            "brain_zooms": zooms_to_str(brain_zooms),
            "mask_zooms": zooms_to_str(mask_zooms),
            "dk_struct_zooms": zooms_to_str(dk_zooms),

            "brain_size_mb": "" if brain_size is None else f"{brain_size:.2f}",
            "mask_size_mb": "" if mask_size is None else f"{mask_size:.2f}",
            "dk_struct_size_mb": "" if dk_size is None else f"{dk_size:.2f}",

            "missing_files": ",".join(missing_files),
            "unreadable_files": "; ".join([f"{x[0]}:{x[1]}" for x in unreadable_files]),
        }

        rows.append(row)

        if status == "CORRECT":
            correct_count += 1
            correct_ids.append(case_id)

        elif status == "MISMATCH":
            mismatch_count += 1
            mismatch_items.append(row)
            print(
                f"[MISMATCH] {case_id}: "
                f"brain={row['brain_shape']}, "
                f"mask={row['mask_shape']}, "
                f"dk_struct={row['dk_struct_shape']}"
            )

        elif status == "MATCH_BUT_RAW_SHAPE":
            match_raw_count += 1
            match_raw_items.append(row)
            print(
                f"[MATCH_BUT_RAW_SHAPE] {case_id}: "
                f"shape={row['brain_shape']}，三者匹配，但属于原始 T1/T2 尺寸"
            )

        elif status == "MATCH_BUT_OTHER_WRONG_SHAPE":
            match_other_wrong_count += 1
            match_other_wrong_items.append(row)
            print(
                f"[MATCH_BUT_OTHER_WRONG_SHAPE] {case_id}: "
                f"shape={row['brain_shape']}，三者匹配，但不是 ACPC 或原始尺寸"
            )

        elif status == "MISSING":
            missing_count += 1
            missing_items.append(row)
            print(
                f"[MISSING] {case_id}: "
                f"missing={row['missing_files']}"
            )

        elif status == "UNREADABLE":
            unreadable_count += 1
            unreadable_items.append(row)
            print(
                f"[UNREADABLE] {case_id}: "
                f"{row['unreadable_files']}"
            )

        else:
            print(f"[UNKNOWN] {case_id}: status={status}")

        if SLEEP_SECONDS_PER_CASE > 0:
            time.sleep(SLEEP_SECONDS_PER_CASE)

    if not DRY_RUN:
        fieldnames = [
            "case_id",
            "status",

            "brain_path",
            "mask_path",
            "dk_struct_path",

            "brain_shape",
            "mask_shape",
            "dk_struct_shape",

            "brain_zooms",
            "mask_zooms",
            "dk_struct_zooms",

            "brain_size_mb",
            "mask_size_mb",
            "dk_struct_size_mb",

            "missing_files",
            "unreadable_files",
        ]

        with open(REPORT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print("\n========== 检查完成 ==========")
    print(f"一共检查 ID 数量：{total_count}")
    print(f"正确 ACPC 尺寸数量：{correct_count}")
    print(f"尺寸不匹配数量：{mismatch_count}")
    print(f"三者匹配但为原始 T1/T2 尺寸数量：{match_raw_count}")
    print(f"三者匹配但为其他异常尺寸数量：{match_other_wrong_count}")
    print(f"缺文件数量：{missing_count}")
    print(f"文件存在但 header 读取失败数量：{unreadable_count}")

    print("\n========== 分类解释 ==========")
    print("CORRECT：brain / mask / dk-struct 三者 shape 一致，且为 ACPC 后标准尺寸 198×243×291。")
    print("MISMATCH：三者都能读，但 shape 不一致。")
    print("MATCH_BUT_RAW_SHAPE：三者 shape 一致，但为原始 T1/T2 尺寸 320×208×300。")
    print("MATCH_BUT_OTHER_WRONG_SHAPE：三者 shape 一致，但既不是 198×243×291，也不是 320×208×300。")
    print("MISSING：缺 brain / mask / dk-struct 中至少一个。")
    print("UNREADABLE：文件存在，但 NIfTI header 读取失败。")

    if mismatch_items:
        print("\n========== 尺寸不匹配 ID ==========")
        for row in mismatch_items:
            print(
                f"{row['case_id']}\t"
                f"brain={row['brain_shape']}\t"
                f"mask={row['mask_shape']}\t"
                f"dk_struct={row['dk_struct_shape']}"
            )

    if match_raw_items:
        print("\n========== 三者匹配但为原始 T1/T2 尺寸 ID ==========")
        for row in match_raw_items:
            print(
                f"{row['case_id']}\t"
                f"shape={row['brain_shape']}\t"
                f"brain_size={row['brain_size_mb']}MB\t"
                f"mask_size={row['mask_size_mb']}MB\t"
                f"dk_struct_size={row['dk_struct_size_mb']}MB"
            )

    if match_other_wrong_items:
        print("\n========== 三者匹配但为其他异常尺寸 ID ==========")
        for row in match_other_wrong_items:
            print(
                f"{row['case_id']}\t"
                f"shape={row['brain_shape']}\t"
                f"brain_size={row['brain_size_mb']}MB"
            )

    if missing_items:
        print("\n========== 缺文件 ID ==========")
        for row in missing_items:
            print(
                f"{row['case_id']}\t"
                f"missing={row['missing_files']}"
            )

    if unreadable_items:
        print("\n========== 读取失败 ID ==========")
        for row in unreadable_items:
            print(
                f"{row['case_id']}\t"
                f"{row['unreadable_files']}"
            )

    if not DRY_RUN:
        print(f"\nCSV 报告已写出：{REPORT_CSV}")
    else:
        print("\nDRY_RUN=True，本次没有写出 CSV。若需要保存表格，把 DRY_RUN 改成 False。")


if __name__ == "__main__":
    main()