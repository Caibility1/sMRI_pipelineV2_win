import posixpath
import stat
import paramiko

HOST = "10.15.49.7"
PORT = 22112
USERNAME = "linmo2025"
PASSWORD = r"E>vq2fgPr9"

ROOT = "/public_bme2/bme-zhanghan/linmo2025/2026/0506_CBCP/0_rawdata"

# 先预演；确认没问题后改成 False 真改名
DRY_RUN = False


def is_dir_attr(attr):
    return stat.S_ISDIR(attr.st_mode)


def is_file_attr(attr):
    return stat.S_ISREG(attr.st_mode)


def is_nifti(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(".nii") or lower.endswith(".nii.gz")


def list_subject_files(sftp, subject_dir):
    files = []
    for attr in sftp.listdir_attr(subject_dir):
        if is_file_attr(attr):
            files.append(attr.filename)
    return files


def get_candidates(file_names, modality):
    res = []
    for name in file_names:
        lower = name.lower()
        if modality in lower and is_nifti(name):
            res.append(name)
    return res


def rename_if_needed(sftp, subject_dir, file_names, modality, target_name):
    """
    返回:
    - exists: 已经有标准名
    - renamed: 成功改名（或 DRY_RUN 下将改名）
    - missing: 没找到候选
    - conflict: 多候选冲突
    """
    if target_name in file_names:
        return "exists", None

    candidates = get_candidates(file_names, modality)

    if len(candidates) == 0:
        return "missing", None

    if len(candidates) > 1:
        return "conflict", candidates

    src_name = candidates[0]
    src_path = posixpath.join(subject_dir, src_name)
    dst_path = posixpath.join(subject_dir, target_name)

    if not DRY_RUN:
        sftp.rename(src_path, dst_path)

    return "renamed", [src_name]


def print_id_list(title, items):
    print(f"\n{title}")
    if not items:
        print("  无")
        return
    for x in sorted(items):
        print(f"  {x}")


def print_conflict_dict(title, data):
    print(f"\n{title}")
    if not data:
        print("  无")
        return
    for subject_id in sorted(data):
        print(f"  {subject_id}")
        for name in data[subject_id]:
            print(f"    {name}")


def main():
    transport = None
    sftp = None

    try:
        transport = paramiko.Transport((HOST, PORT))
        transport.connect(username=USERNAME, password=PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        root_attr = sftp.stat(ROOT)
        if not stat.S_ISDIR(root_attr.st_mode):
            print(f"远端路径不是文件夹: {ROOT}")
            return

        stats_dict = {
            "subjects": 0,
            "t1_exists": 0,
            "t1_renamed": 0,
            "t1_missing": 0,
            "t1_conflict": 0,
            "t2_exists": 0,
            "t2_renamed": 0,
            "t2_missing": 0,
            "t2_conflict": 0,
            "exceptions": 0,
        }

        t1_conflict_cases = {}
        t2_conflict_cases = {}
        t1_missing_cases = []
        t2_missing_cases = []
        exception_cases = {}

        for attr in sftp.listdir_attr(ROOT):
            if not is_dir_attr(attr):
                continue

            subject_id = attr.filename
            subject_dir = posixpath.join(ROOT, subject_id)
            stats_dict["subjects"] += 1

            try:
                file_names = list_subject_files(sftp, subject_dir)

                t1_status, t1_info = rename_if_needed(
                    sftp, subject_dir, file_names, "t1", "T1.nii.gz"
                )
                t2_status, t2_info = rename_if_needed(
                    sftp, subject_dir, file_names, "t2", "T2.nii.gz"
                )

                stats_dict[f"t1_{t1_status}"] += 1
                stats_dict[f"t2_{t2_status}"] += 1

                if t1_status == "conflict":
                    t1_conflict_cases[subject_id] = t1_info
                elif t1_status == "missing":
                    t1_missing_cases.append(subject_id)

                if t2_status == "conflict":
                    t2_conflict_cases[subject_id] = t2_info
                elif t2_status == "missing":
                    t2_missing_cases.append(subject_id)

            except Exception as e:
                stats_dict["exceptions"] += 1
                exception_cases[subject_id] = str(e)

        print("=" * 80)
        print("完成")
        print(f"模式: {'预演 DRY_RUN=True' if DRY_RUN else '真实改名 DRY_RUN=False'}")
        print(f"病例文件夹总数: {stats_dict['subjects']}")
        print()
        print(f"T1 已是标准名: {stats_dict['t1_exists']}")
        print(f"T1 成功改名: {stats_dict['t1_renamed']}")
        print(f"T1 未找到候选: {stats_dict['t1_missing']}")
        print(f"T1 多候选冲突: {stats_dict['t1_conflict']}")
        print()
        print(f"T2 已是标准名: {stats_dict['t2_exists']}")
        print(f"T2 成功改名: {stats_dict['t2_renamed']}")
        print(f"T2 未找到候选: {stats_dict['t2_missing']}")
        print(f"T2 多候选冲突: {stats_dict['t2_conflict']}")
        print()
        print(f"处理异常: {stats_dict['exceptions']}")
        print("=" * 80)

        print_conflict_dict("T1 冲突 ID 列表：", t1_conflict_cases)
        print_conflict_dict("T2 冲突 ID 列表：", t2_conflict_cases)

        print_id_list("T1 未找到候选 ID 列表：", t1_missing_cases)
        print_id_list("T2 未找到候选 ID 列表：", t2_missing_cases)

        print("\n处理异常 ID 列表：")
        if not exception_cases:
            print("  无")
        else:
            for subject_id in sorted(exception_cases):
                print(f"  {subject_id}")
                print(f"    {exception_cases[subject_id]}")

    finally:
        if sftp is not None:
            sftp.close()
        if transport is not None:
            transport.close()


if __name__ == "__main__":
    main()