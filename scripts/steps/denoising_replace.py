from pathlib import Path
import shutil
import re

# ===================== 路径设置 =====================

questionable_dir = Path(r"D:\University\master\QC2026\2026\0604_CBCP\questionable")

fixed_source_dirs = [
    Path(r"D:\University\master\QC2026\2026\0604_CBCP\20260609"),
    # 以后有新的去噪来源，直接继续加：
    # Path(r"D:\University\master\QC2026\2026\修正后\0510"),
    # Path(r"D:\University\master\QC2026\2026\修正后\0512"),
]

wait_seg_dir = questionable_dir.parent / "待分割"

# True  = 只预演，不复制、不移动
# False = 真正执行
DRY_RUN = True

SOURCE_T1_CANDIDATE_NAMES = [
    "T1_age.nii.gz",
]

TARGET_T1_NAME = "T1_acpc.nii.gz"


# ===================== ID 处理 =====================

def extract_core_id(folder_name: str) -> str:
    """
    只删除末尾的月龄后缀：_1mo / _24mo / _231mo

    0101030001_1mo          -> 0101030001
    sub203_231mo            -> sub203
    N1121_01010348_24mo     -> N1121_01010348

    不会按 '_' split，所以不会误伤 N1121_01010348 这种 ID。
    """
    name = folder_name.strip()
    return re.sub(r"_\d{1,3}mo$", "", name, flags=re.IGNORECASE)


def make_match_key(folder_name: str) -> str:
    return extract_core_id(folder_name).lower()


# ===================== 工具函数 =====================

def is_subject_folder(p: Path) -> bool:
    return p.is_dir()


def find_source_t1(subj_dir: Path):
    for name in SOURCE_T1_CANDIDATE_NAMES:
        candidate = subj_dir / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def safe_move_folder(src: Path, dst_parent: Path) -> Path:
    """
    移动到待分割。
    如果目标已存在，自动加后缀，避免覆盖。
    """
    dst_parent.mkdir(parents=True, exist_ok=True)

    dst = dst_parent / src.name
    if not dst.exists():
        shutil.move(str(src), str(dst))
        return dst

    i = 1
    while True:
        new_dst = dst_parent / f"{src.name}_moved_{i}"
        if not new_dst.exists():
            shutil.move(str(src), str(new_dst))
            return new_dst
        i += 1


# ===================== 主流程 =====================

def main():
    if not questionable_dir.exists():
        raise FileNotFoundError(f"questionable_dir 不存在：{questionable_dir}")

    wait_seg_dir.mkdir(parents=True, exist_ok=True)

    fixed_t1_map = {}

    source_missing_dirs = []
    fixed_subject_missing_t1 = []
    duplicate_fixed_ids = []
    source_scan_summary = []

    # ===================== 扫描修正来源 =====================

    for source_dir in fixed_source_dirs:
        if not source_dir.exists():
            source_missing_dirs.append(str(source_dir))
            continue

        source_folder_count = 0
        source_valid_t1_count = 0
        source_missing_t1_count = 0
        source_duplicate_count = 0

        for subj_dir in source_dir.iterdir():
            if not is_subject_folder(subj_dir):
                continue

            source_folder_count += 1

            folder_name = subj_dir.name
            core_id = extract_core_id(folder_name)
            match_key = make_match_key(folder_name)

            source_t1 = find_source_t1(subj_dir)

            if source_t1 is None:
                source_missing_t1_count += 1
                fixed_subject_missing_t1.append({
                    "folder_name": folder_name,
                    "core_id": core_id,
                    "source_dir": str(source_dir),
                })
                continue

            source_valid_t1_count += 1

            if match_key not in fixed_t1_map:
                fixed_t1_map[match_key] = {
                    "folder_name": folder_name,
                    "core_id": core_id,
                    "t1_path": source_t1,
                    "source_dir": source_dir,
                }
            else:
                source_duplicate_count += 1
                old = fixed_t1_map[match_key]

                duplicate_fixed_ids.append({
                    "core_id": core_id,
                    "kept_folder_name": old["folder_name"],
                    "kept_t1": str(old["t1_path"]),
                    "kept_source": str(old["source_dir"]),
                    "ignored_folder_name": folder_name,
                    "ignored_t1": str(source_t1),
                    "ignored_source": str(source_dir),
                })

        source_scan_summary.append({
            "source_dir": str(source_dir),
            "source_folder_count": source_folder_count,
            "source_valid_t1_count": source_valid_t1_count,
            "source_missing_t1_count": source_missing_t1_count,
            "source_duplicate_count": source_duplicate_count,
        })

    # ===================== 处理 questionable =====================

    questionable_subjects = [p for p in questionable_dir.iterdir() if is_subject_folder(p)]

    questionable_key_seen = {}
    duplicate_questionable_ids = []

    for subj_dir in questionable_subjects:
        folder_name = subj_dir.name
        core_id = extract_core_id(folder_name)
        match_key = make_match_key(folder_name)

        if match_key in questionable_key_seen:
            duplicate_questionable_ids.append({
                "core_id": core_id,
                "folder_a": questionable_key_seen[match_key],
                "folder_b": folder_name,
            })
        else:
            questionable_key_seen[match_key] = folder_name

    replaced = []
    moved_to_wait_seg = []
    missing_denoised = []
    questionable_missing_t1_after = []

    for subj_dir in questionable_subjects:
        folder_name = subj_dir.name
        core_id = extract_core_id(folder_name)
        match_key = make_match_key(folder_name)

        target_t1 = subj_dir / TARGET_T1_NAME
        fixed_info = fixed_t1_map.get(match_key)

        if fixed_info is not None:
            source_t1 = fixed_info["t1_path"]
            source_dir = fixed_info["source_dir"]
            source_folder_name = fixed_info["folder_name"]

            if DRY_RUN:
                print(f"[DRY-RUN] 替换：{source_t1} -> {target_t1}")
            else:
                # 直接覆盖，不备份
                shutil.copy2(source_t1, target_t1)

            replaced.append({
                "questionable_folder": folder_name,
                "questionable_core_id": core_id,
                "source_folder": source_folder_name,
                "source_t1": str(source_t1),
                "source_dir": str(source_dir),
                "target_t1": str(target_t1),
            })

        else:
            missing_denoised.append({
                "folder_name": folder_name,
                "core_id": core_id,
            })

            if DRY_RUN:
                print(f"[DRY-RUN] 移动未去噪/未修正数据：{subj_dir} -> {wait_seg_dir / folder_name}")
                moved_path = wait_seg_dir / folder_name
            else:
                moved_path = safe_move_folder(subj_dir, wait_seg_dir)

            moved_to_wait_seg.append(str(moved_path))

    questionable_keys = {make_match_key(p.name) for p in questionable_subjects}
    fixed_extra_keys = sorted([key for key in fixed_t1_map.keys() if key not in questionable_keys])

    if not DRY_RUN:
        for p in questionable_dir.iterdir():
            if is_subject_folder(p) and not (p / TARGET_T1_NAME).exists():
                questionable_missing_t1_after.append({
                    "folder_name": p.name,
                    "core_id": extract_core_id(p.name),
                })

    # ===================== 打印总结 =====================

    print("\n==================== 处理完成 ====================")
    print(f"questionable 目录：{questionable_dir}")
    print(f"待分割目录：{wait_seg_dir}")
    print(f"DRY_RUN：{DRY_RUN}")
    print("备份：关闭。旧 T1.nii.gz 会被直接覆盖。")

    print("\n==================== ID 匹配规则 ====================")
    print("匹配时只删除文件夹名末尾的 _数字mo。")
    print("例如：")
    print("  0101030001_1mo      -> 0101030001")
    print("  sub203_231mo        -> sub203")
    print("  N1121_01010348_24mo -> N1121_01010348")

    print("\n==================== 修正来源扫描统计 ====================")

    if source_missing_dirs:
        print("\n以下修正来源目录不存在，已跳过：")
        for p in source_missing_dirs:
            print(p)

    for item in source_scan_summary:
        print("\n来源目录：", item["source_dir"])
        print(f"  文件夹数量：{item['source_folder_count']}")
        print(f"  找到可用 T1 的数量：{item['source_valid_t1_count']}")
        print(f"  缺少可用 T1 的数量：{item['source_missing_t1_count']}")
        print(f"  去掉月龄后 ID 重复、已忽略的数量：{item['source_duplicate_count']}")

    print("\n==================== 总体数量统计 ====================")
    print(f"所有修正来源中，可用于匹配的唯一 core ID 数量：{len(fixed_t1_map)}")
    print(f"questionable 中文件夹数量：{len(questionable_subjects)}")
    print(f"成功替换 T1 的数量：{len(replaced)}")
    print(f"没有去噪/没有修正 T1，已移动到待分割的数量：{len(missing_denoised)}")
    print(f"修正来源中文件夹存在但缺少可用 T1 的数量：{len(fixed_subject_missing_t1)}")
    print(f"修正来源中有可用 T1，但 questionable 里没有对应 core ID 的数量：{len(fixed_extra_keys)}")
    print(f"修正来源中去掉月龄后 core ID 重复的数量：{len(duplicate_fixed_ids)}")
    print(f"questionable 中去掉月龄后 core ID 重复的数量：{len(duplicate_questionable_ids)}")

    print("\n==================== 已替换的 ID ====================")
    if replaced:
        for item in sorted(replaced, key=lambda x: x["questionable_core_id"]):
            print(
                f"{item['questionable_folder']} "
                f"[core_id={item['questionable_core_id']}]  <--  "
                f"{item['source_folder']} | {item['source_t1']}"
            )
    else:
        print("无")

    print("\n==================== 没有去噪/没有修正 T1 的 ID，已移到待分割 ====================")
    if missing_denoised:
        for item in sorted(missing_denoised, key=lambda x: x["core_id"]):
            print(f"{item['folder_name']}  [core_id={item['core_id']}]")
    else:
        print("无")

    print("\n==================== 修正来源中文件夹存在但缺少可用 T1 ====================")
    if fixed_subject_missing_t1:
        for item in sorted(fixed_subject_missing_t1, key=lambda x: x["core_id"]):
            print(f"{item['folder_name']}  [core_id={item['core_id']}] | 来源：{item['source_dir']}")
    else:
        print("无")

    print("\n==================== 修正来源中有，但 questionable 里没有的 core ID ====================")
    if fixed_extra_keys:
        for key in fixed_extra_keys:
            info = fixed_t1_map[key]
            print(
                f"{info['folder_name']} "
                f"[core_id={info['core_id']}] | 来源：{info['source_dir']}"
            )
    else:
        print("无")

    print("\n==================== 修正来源去掉月龄后 core ID 重复，已保留第一个 ====================")
    if duplicate_fixed_ids:
        for item in sorted(duplicate_fixed_ids, key=lambda x: x["core_id"]):
            print(f"core_id={item['core_id']}")
            print(f"  保留：{item['kept_folder_name']} | {item['kept_t1']}")
            print(f"  忽略：{item['ignored_folder_name']} | {item['ignored_t1']}")
    else:
        print("无")

    print("\n==================== questionable 去掉月龄后 core ID 重复，需要人工注意 ====================")
    if duplicate_questionable_ids:
        for item in sorted(duplicate_questionable_ids, key=lambda x: x["core_id"]):
            print(f"core_id={item['core_id']}")
            print(f"  文件夹1：{item['folder_a']}")
            print(f"  文件夹2：{item['folder_b']}")
    else:
        print("无")

    if questionable_missing_t1_after:
        print("\n==================== 警告：处理后 questionable 中仍缺少 T1.nii.gz 的 ID ====================")
        for item in sorted(questionable_missing_t1_after, key=lambda x: x["core_id"]):
            print(f"{item['folder_name']}  [core_id={item['core_id']}]")
    else:
        print("\n处理后 questionable 中剩余的文件夹均应已有 T1.nii.gz。")


if __name__ == "__main__":
    main()