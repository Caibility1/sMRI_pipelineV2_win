import os
import stat
import subprocess
from pathlib import Path
from collections import defaultdict

import pandas as pd
import paramiko


# =========================
# 本地 Excel
# =========================
EXCEL_PATH = Path(r"D:\University\master\QC2026\2026\tmp.xlsx")

# =========================
# NAS 配置
# =========================
NAS_SHARE = r"\\10.19.136.231\002"
NAS_USERNAME = r"linm"
NAS_PASSWORD = r"l9cG5/g{"

# 每个 sheet 对应的根目录：
# \\10.19.136.231\002\CBCP\CBCP_MRI\4_VisualQC_Processing\<sheet名>\1_sMRI\2_sMRI_QCpass_T1_T2
def get_source_root(sheet_name: str) -> Path:
    return Path(
        #rf"\\10.19.136.231\002\CBCP\CBCP_MRI\4_VisualQC_Processing\{sheet_name}\1_sMRI\2_sMRI_QCpass_T1_T2"
        rf"\\10.19.136.231\002\CBCP\CBCP_MRI\4_VisualQC_Processing\{sheet_name}\1_sMRI\1_sMRI_data"
    )

# =========================
# 集群 SFTP 配置
# =========================
SFTP_HOST = "10.15.49.7"
SFTP_PORT = 22112
SFTP_USERNAME = "linmo2025"
SFTP_PASSWORD = r"E>vq2fgPr9"

REMOTE_DEST_ROOT = "/public_bme2/bme-zhanghan/linmo2025/2026/0506_CBCP/0_rawdata2"

# True: 远端已存在同名目录时跳过
# False: 若已存在则继续上传，可能覆盖同名文件
SKIP_IF_REMOTE_EXISTS = True

# True: 找 ID 时如果直接子目录没找到，再递归搜
ENABLE_RECURSIVE_FALLBACK = True


# =========================
# 工具函数
# =========================
def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return result.returncode, result.stdout, result.stderr


def connect_nas():
    # 先删掉旧连接，避免 1219 冲突
    run_cmd(["net", "use", NAS_SHARE, "/delete", "/y"])
    code, out, err = run_cmd(["net", "use", NAS_SHARE, NAS_PASSWORD, f"/user:{NAS_USERNAME}"])
    if code != 0:
        raise RuntimeError(f"NAS 连接失败\nstdout:\n{out}\nstderr:\n{err}")


def disconnect_nas():
    run_cmd(["net", "use", NAS_SHARE, "/delete", "/y"])


def normalize_id(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None
    if s.lower() == "subnum":
        return None
    if s.endswith(".0"):
        core = s[:-2]
        if core.isdigit():
            s = core
    return s


def build_direct_index(source_root: Path):
    idx = {}
    if not source_root.exists():
        return idx
    for p in source_root.iterdir():
        if p.is_dir():
            idx[p.name] = p
    return idx


def recursive_find_by_name(source_root: Path, folder_name: str):
    matches = []
    for p in source_root.rglob(folder_name):
        if p.is_dir() and p.name == folder_name:
            matches.append(p)
    return matches


def sftp_connect():
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(transport)
    return transport, sftp


def sftp_exists(sftp, remote_path):
    try:
        sftp.stat(remote_path)
        return True
    except FileNotFoundError:
        return False
    except IOError:
        return False


def sftp_isdir(sftp, remote_path):
    try:
        return stat.S_ISDIR(sftp.stat(remote_path).st_mode)
    except Exception:
        return False


def sftp_mkdir_p(sftp, remote_directory):
    remote_directory = remote_directory.replace("\\", "/")
    if remote_directory in ("", "/"):
        return

    parts = remote_directory.strip("/").split("/")
    current = "/"
    for part in parts:
        current = os.path.join(current, part).replace("\\", "/")
        if not sftp_exists(sftp, current):
            sftp.mkdir(current)


def upload_dir_recursive(sftp, local_dir: Path, remote_dir: str):
    local_dir = Path(local_dir)
    remote_dir = remote_dir.replace("\\", "/")

    sftp_mkdir_p(sftp, remote_dir)

    for item in local_dir.iterdir():
        remote_item = f"{remote_dir}/{item.name}"
        if item.is_dir():
            upload_dir_recursive(sftp, item, remote_item)
        elif item.is_file():
            sftp.put(str(item), remote_item)


# =========================
# 主逻辑
# =========================
def main():
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel 不存在: {EXCEL_PATH}")

    workbook = pd.read_excel(EXCEL_PATH, sheet_name=None, dtype=str)

    print(f"检测到 {len(workbook)} 个 sheet: {list(workbook.keys())}")

    overall_not_found = defaultdict(list)
    overall_uploaded = defaultdict(list)
    overall_skipped = defaultdict(list)
    overall_failed = defaultdict(list)

    transport = None
    sftp = None

    try:
        print("\n连接 NAS ...")
        connect_nas()
        print("NAS 已连接。")

        print("连接集群 SFTP ...")
        transport, sftp = sftp_connect()
        print("SFTP 已连接。")

        sftp_mkdir_p(sftp, REMOTE_DEST_ROOT)

        for sheet_name, df in workbook.items():
            print("\n" + "=" * 90)
            print(f"开始处理 sheet: {sheet_name}")

            if df.shape[1] < 1:
                print(f"[跳过] {sheet_name} 没有列")
                continue

            first_col = df.columns[0]
            ids = [normalize_id(x) for x in df[first_col].tolist()]
            ids = [x for x in ids if x is not None]
            ids = list(dict.fromkeys(ids))

            print(f"{sheet_name} 第一列有效 ID 数量: {len(ids)}")

            source_root = get_source_root(sheet_name)
            print(f"源目录: {source_root}")

            if not source_root.exists():
                print(f"[失败] 源目录不存在: {source_root}")
                overall_failed[sheet_name].append(f"源目录不存在: {source_root}")
                overall_not_found[sheet_name].extend(ids)
                continue

            direct_index = build_direct_index(source_root)

            for sid in ids:
                try:
                    src_dir = direct_index.get(sid)

                    if src_dir is None and ENABLE_RECURSIVE_FALLBACK:
                        matches = recursive_find_by_name(source_root, sid)
                        if len(matches) == 1:
                            src_dir = matches[0]
                        elif len(matches) > 1:
                            overall_failed[sheet_name].append(
                                f"{sid} -> 递归搜索命中多个目录: {[str(x) for x in matches]}"
                            )
                            print(f"[重名冲突] {sid}")
                            continue

                    if src_dir is None:
                        overall_not_found[sheet_name].append(sid)
                        print(f"[未找到] {sid}")
                        continue

                    remote_target = f"{REMOTE_DEST_ROOT}/{sid}"

                    if SKIP_IF_REMOTE_EXISTS and sftp_exists(sftp, remote_target):
                        overall_skipped[sheet_name].append(sid)
                        print(f"[跳过-远端已存在] {sid}")
                        continue

                    print(f"[上传] {sid}")
                    upload_dir_recursive(sftp, src_dir, remote_target)
                    overall_uploaded[sheet_name].append(sid)

                except Exception as e:
                    overall_failed[sheet_name].append(f"{sid} -> {e}")
                    print(f"[失败] {sid} -> {e}")

        print("\n" + "=" * 90)
        print("全部完成，结果如下：")

        for sheet_name in workbook.keys():
            print(f"\n{sheet_name}")
            print(f"  成功上传: {len(overall_uploaded[sheet_name])}")
            print(f"  已存在跳过: {len(overall_skipped[sheet_name])}")
            print(f"  未找到: {len(overall_not_found[sheet_name])}")
            print(f"  失败: {len(overall_failed[sheet_name])}")

            if overall_not_found[sheet_name]:
                print("  没找到的 ID：")
                for sid in overall_not_found[sheet_name]:
                    print(f"    {sid}")

            if overall_failed[sheet_name]:
                print("  失败详情：")
                for info in overall_failed[sheet_name]:
                    print(f"    {info}")

    finally:
        if sftp is not None:
            sftp.close()
        if transport is not None:
            transport.close()

        print("\n断开 NAS ...")
        disconnect_nas()
        print("NAS 已断开。")


if __name__ == "__main__":
    main()