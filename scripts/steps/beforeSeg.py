from pathlib import Path
import shutil
import subprocess
import sys
import time


# ============================================================
# 你主要只改这里
# ============================================================

# 选择运行来源：
# "LOCAL"   = 本地路径
# "NAS"     = NAS 路径
# "CLUSTER" = 集群路径，通过 SSH 执行
# "ASK"     = 每次运行时手动选择
RUN_SOURCE = "NAS"

# 安全锁：
# True  = 只预演，打印将删除什么，不实际删除
# False = 真实删除。真实删除前仍然需要输入 DELETE 二次确认
DRY_RUN = False

# 真实删除时是否要求二次确认
REQUIRE_CONFIRM_WHEN_REAL_DELETE = True

# 三种来源分别对应的 ROOT。
# 这个 ROOT 下面应该有 justT1 和 T1T2 两个文件夹：
#
# ROOT/
#   justT1/
#     ID1/
#   T1T2/
#     ID2/
#
ROOT_BY_SOURCE = {
    "LOCAL": Path(r"D:\University\master\QC2026\2026\0511_questionable"),

    "NAS": Path(r"\\10.19.136.231\002\CBCP\CBCP_MRI\toBeSegmented\0622_CBCP"),

    "CLUSTER": "/public_bme2/bme-zhanghan/linmo2025/2026/0507_ASD/0511_questionable",
}

# 删除规则。
# 这里写不带 .nii.gz 的名字即可，脚本会自动补成 T1_acpc.nii.gz / T2_acpc.nii.gz。
#
# justT1 每个 ID 文件夹：只保留 T1_acpc.nii.gz
# T1T2 每个 ID 文件夹：只保留 T1_acpc.nii.gz 和 T2_acpc.nii.gz
KEEP_RULES = {
    "justT1": ["T1_acpc"],
    "T1T2": ["T1_acpc", "T2_acpc"],
}

# NAS 连接配置
NAS_SHARE = r"\\10.19.136.231\002"
NAS_USERNAME = "linm"
NAS_PASSWORD = "l9cG5/g{"

# 集群 SSH 配置
CLUSTER_HOST = "10.15.49.7"
CLUSTER_PORT = 22112
CLUSTER_USERNAME = "linmo2025"
CLUSTER_PASSWORD = "E>vq2fgPr9"

# ============================================================
# 下面一般不用改
# ============================================================


def build_config_from_keep_rules():
    """
    把用户写的 T1_acpc / T2_acpc 自动转成实际文件名：
    T1_acpc.nii.gz / T2_acpc.nii.gz
    """
    config = {}

    for folder_name, keep_list in KEEP_RULES.items():
        keep_names = set()

        for name in keep_list:
            name = str(name).strip()

            if not name:
                continue

            if name.endswith(".nii.gz"):
                keep_names.add(name)
            else:
                keep_names.add(name + ".nii.gz")

        config[folder_name] = keep_names

    return config


CONFIG = build_config_from_keep_rules()


# ============================================================
# 通用确认与来源选择
# ============================================================

def choose_run_target():
    mode = RUN_SOURCE.strip().upper()

    if mode in {"LOCAL", "NAS", "CLUSTER"}:
        return mode

    if mode != "ASK":
        raise ValueError("RUN_SOURCE 只能是 ASK / LOCAL / NAS / CLUSTER")

    print("\n请选择运行位置：")
    print("1. LOCAL   本地路径，例如 D:\\University\\...")
    print("2. NAS     NAS 路径，例如 \\\\10.19.136.231\\002\\...")
    print("3. CLUSTER 集群路径，通过 SSH 登录后在集群上执行")
    ans = input("请输入 1 / 2 / 3：").strip()

    if ans == "1":
        return "LOCAL"
    if ans == "2":
        return "NAS"
    if ans == "3":
        return "CLUSTER"

    raise ValueError("输入无效，只能输入 1 / 2 / 3")


def get_root_for_target(target: str):
    if target not in ROOT_BY_SOURCE:
        raise ValueError(f"ROOT_BY_SOURCE 里没有配置这个来源: {target}")
    return ROOT_BY_SOURCE[target]


def confirm_real_delete(target: str, root_str: str):
    if DRY_RUN:
        return True

    if not REQUIRE_CONFIRM_WHEN_REAL_DELETE:
        return True

    print("\n" + "!" * 90)
    print("危险操作确认")
    print("当前 DRY_RUN=False，将真实删除文件/文件夹。")
    print(f"运行位置: {target}")
    print(f"ROOT: {root_str}")
    print("")
    print("这个脚本会：")

    for folder_name, keep_names in CONFIG.items():
        print(f"  - 进入 ROOT/{folder_name}/每个ID，只保留: {sorted(keep_names)}")

    print("  - 删除其他所有文件和文件夹")
    print("")
    print("如果确认执行，请输入大写 DELETE。其他输入都会取消。")
    print("!" * 90)

    ans = input("请输入 DELETE 以确认真实删除：").strip()

    if ans != "DELETE":
        print("[取消] 未输入 DELETE，已终止。")
        return False

    return True


# ============================================================
# NAS 连接
# ============================================================

def run_windows_cmd(cmd):
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
    print("\n========== 正在连接 NAS ==========")
    print(f"NAS_SHARE: {NAS_SHARE}")
    print(f"USER: {NAS_USERNAME}")

    cmd = [
        "net",
        "use",
        NAS_SHARE,
        NAS_PASSWORD,
        f"/user:{NAS_USERNAME}",
        "/persistent:no",
    ]

    result = run_windows_cmd(cmd)

    if result.returncode == 0:
        print(f"[OK] 已连接 NAS：{NAS_SHARE}")
        return True

    output = (result.stdout or "") + "\n" + (result.stderr or "")

    if "命令成功完成" in output or "The command completed successfully" in output:
        print(f"[OK] 已连接 NAS：{NAS_SHARE}")
        return True

    if "已存在" in output or "multiple connections" in output.lower() or "1219" in output:
        print("[提示] NAS 可能已经连接过，尝试继续访问目录。")
        return True

    print("[警告] NAS 自动连接失败。")
    print("stdout:")
    print(result.stdout)
    print("stderr:")
    print(result.stderr)
    print("如果后面目录仍然能访问，可以继续；否则请检查 NAS 路径、账密或已有连接。")
    return False


# ============================================================
# LOCAL / NAS 共用清理逻辑
# ============================================================

def clean_subject_folder_path(subject_dir: Path, keep_names: set[str]):
    removed_count = 0
    failed_count = 0
    kept_count = 0

    try:
        items = sorted(subject_dir.iterdir(), key=lambda x: x.name)
    except Exception as e:
        print(f"  [读取失败] {subject_dir} -> {e}")
        return 0, 1, 0

    for item in items:
        # 只保留指定文件名的普通文件
        if item.is_file() and item.name in keep_names:
            print(f"  [KEEP] 保留文件: {item}")
            kept_count += 1
            continue

        # 符号链接：只删链接本身，不递归
        if item.is_symlink():
            print(f"  [{'DRY-RUN' if DRY_RUN else 'DELETE'}] 删除符号链接: {item}")
            if not DRY_RUN:
                try:
                    item.unlink()
                except Exception as e:
                    print(f"  [删除失败] {item} -> {e}")
                    failed_count += 1
                    continue
            removed_count += 1
            continue

        # 其他文件全部删除
        if item.is_file():
            print(f"  [{'DRY-RUN' if DRY_RUN else 'DELETE'}] 删除文件: {item}")
            if not DRY_RUN:
                try:
                    item.unlink()
                except Exception as e:
                    print(f"  [删除失败] {item} -> {e}")
                    failed_count += 1
                    continue
            removed_count += 1
            continue

        # 其他文件夹全部递归删除
        if item.is_dir():
            print(f"  [{'DRY-RUN' if DRY_RUN else 'DELETE'}] 删除文件夹: {item}")
            if not DRY_RUN:
                try:
                    shutil.rmtree(item)
                except Exception as e:
                    print(f"  [删除失败] {item} -> {e}")
                    failed_count += 1
                    continue
            removed_count += 1
            continue

        print(f"  [SKIP] 跳过未知类型: {item}")

    return removed_count, failed_count, kept_count


def clean_parent_folder_path(parent_dir: Path, keep_names: set[str]):
    if not parent_dir.exists():
        print(f"[跳过] 不存在: {parent_dir}")
        return 0, 0, 0, 0

    if not parent_dir.is_dir():
        print(f"[跳过] 不是文件夹: {parent_dir}")
        return 0, 0, 0, 0

    subject_count = 0
    removed_count = 0
    failed_count = 0
    kept_count = 0

    for subject_dir in sorted(parent_dir.iterdir(), key=lambda x: x.name):
        if not subject_dir.is_dir():
            continue

        subject_count += 1
        print(f"\n处理数据文件夹: {subject_dir}")

        removed, failed, kept = clean_subject_folder_path(subject_dir, keep_names)
        removed_count += removed
        failed_count += failed
        kept_count += kept

    return subject_count, removed_count, failed_count, kept_count


def run_path_mode(target: str, root: Path):
    if target == "NAS":
        connect_nas()

    if not confirm_real_delete(target, str(root)):
        return

    print("\n" + "=" * 90)
    print(f"{target} 清理模式")
    print(f"ROOT: {root}")
    print(f"模式: {'预演 DRY_RUN=True' if DRY_RUN else '真实删除 DRY_RUN=False'}")
    print("说明：本脚本只删除 ROOT/justT1 和 ROOT/T1T2 中每个 ID 文件夹内的非保留项。")
    print("说明：本脚本不负责把数据分类到 justT1 / T1T2。")
    print("=" * 90)

    if not root.exists():
        print(f"[ERROR] ROOT 不存在或无法访问：{root}")
        return

    if not root.is_dir():
        print(f"[ERROR] ROOT 不是文件夹：{root}")
        return

    total_subjects = 0
    total_removed = 0
    total_failed = 0
    total_kept = 0

    for folder_name, keep_names in CONFIG.items():
        parent_dir = root / folder_name

        print(f"\n{'=' * 90}")
        print(f"开始处理: {parent_dir}")
        print(f"仅保留: {sorted(keep_names)}")
        print(f"模式: {'预演 DRY_RUN=True' if DRY_RUN else '真实删除 DRY_RUN=False'}")
        print(f"{'=' * 90}")

        subject_count, removed_count, failed_count, kept_count = clean_parent_folder_path(
            parent_dir,
            keep_names,
        )

        total_subjects += subject_count
        total_removed += removed_count
        total_failed += failed_count
        total_kept += kept_count

        print(f"\n[{folder_name}] 数据文件夹数: {subject_count}")
        print(f"[{folder_name}] 保留文件数: {kept_count}")
        print(f"[{folder_name}] {'将删除' if DRY_RUN else '已删除'}项目数: {removed_count}")
        print(f"[{folder_name}] 删除失败项目数: {failed_count}")

    print(f"\n{'=' * 90}")
    print("全部完成")
    print(f"运行位置: {target}")
    print(f"ROOT: {root}")
    print(f"总数据文件夹数: {total_subjects}")
    print(f"总保留文件数: {total_kept}")
    print(f"总{'将删除' if DRY_RUN else '已删除'}项目数: {total_removed}")
    print(f"总失败项目数: {total_failed}")
    print(f"{'=' * 90}")


# ============================================================
# CLUSTER 逻辑
# ============================================================

def build_remote_script():
    config_as_python_literal = repr({k: sorted(v) for k, v in CONFIG.items()})
    cluster_root = ROOT_BY_SOURCE["CLUSTER"]

    remote_template = r'''
from pathlib import Path
import shutil

DRY_RUN = __DRY_RUN__
REMOTE_ROOT = Path(__REMOTE_ROOT_REPR__)
CONFIG_RAW = __CONFIG_REPR__
CONFIG = {k: set(v) for k, v in CONFIG_RAW.items()}


def clean_subject_folder(subject_dir: Path, keep_names: set[str]):
    removed_count = 0
    failed_count = 0
    kept_count = 0

    try:
        items = sorted(subject_dir.iterdir(), key=lambda x: x.name)
    except Exception as e:
        print(f"  [读取失败] {subject_dir} -> {e}", flush=True)
        return 0, 1, 0

    for item in items:
        if item.is_file() and item.name in keep_names:
            print(f"  [KEEP] 保留文件: {item}", flush=True)
            kept_count += 1
            continue

        if item.is_symlink():
            print(f"  [{'DRY-RUN' if DRY_RUN else 'DELETE'}] 删除符号链接: {item}", flush=True)
            if not DRY_RUN:
                try:
                    item.unlink()
                except Exception as e:
                    print(f"  [删除失败] {item} -> {e}", flush=True)
                    failed_count += 1
                    continue
            removed_count += 1
            continue

        if item.is_file():
            print(f"  [{'DRY-RUN' if DRY_RUN else 'DELETE'}] 删除文件: {item}", flush=True)
            if not DRY_RUN:
                try:
                    item.unlink()
                except Exception as e:
                    print(f"  [删除失败] {item} -> {e}", flush=True)
                    failed_count += 1
                    continue
            removed_count += 1
            continue

        if item.is_dir():
            print(f"  [{'DRY-RUN' if DRY_RUN else 'DELETE'}] 删除文件夹: {item}", flush=True)
            if not DRY_RUN:
                try:
                    shutil.rmtree(item)
                except Exception as e:
                    print(f"  [删除失败] {item} -> {e}", flush=True)
                    failed_count += 1
                    continue
            removed_count += 1
            continue

        print(f"  [SKIP] 跳过未知类型: {item}", flush=True)

    return removed_count, failed_count, kept_count


def clean_parent_folder(parent_dir: Path, keep_names: set[str]):
    if not parent_dir.exists():
        print(f"[跳过] 不存在: {parent_dir}", flush=True)
        return 0, 0, 0, 0

    if not parent_dir.is_dir():
        print(f"[跳过] 不是文件夹: {parent_dir}", flush=True)
        return 0, 0, 0, 0

    subject_count = 0
    removed_count = 0
    failed_count = 0
    kept_count = 0

    for subject_dir in sorted(parent_dir.iterdir(), key=lambda x: x.name):
        if not subject_dir.is_dir():
            continue

        subject_count += 1
        print(f"\n处理数据文件夹: {subject_dir}", flush=True)

        removed, failed, kept = clean_subject_folder(subject_dir, keep_names)
        removed_count += removed
        failed_count += failed
        kept_count += kept

    return subject_count, removed_count, failed_count, kept_count


def main():
    print("=" * 90, flush=True)
    print("CLUSTER 清理模式", flush=True)
    print(f"REMOTE_ROOT: {REMOTE_ROOT}", flush=True)
    print(f"模式: {'预演 DRY_RUN=True' if DRY_RUN else '真实删除 DRY_RUN=False'}", flush=True)
    print("说明：本脚本只删除 ROOT/justT1 和 ROOT/T1T2 中每个 ID 文件夹内的非保留项。", flush=True)
    print("=" * 90, flush=True)

    if not REMOTE_ROOT.exists():
        print(f"[ERROR] REMOTE_ROOT 不存在：{REMOTE_ROOT}", flush=True)
        return

    if not REMOTE_ROOT.is_dir():
        print(f"[ERROR] REMOTE_ROOT 不是文件夹：{REMOTE_ROOT}", flush=True)
        return

    total_subjects = 0
    total_removed = 0
    total_failed = 0
    total_kept = 0

    for folder_name, keep_names in CONFIG.items():
        parent_dir = REMOTE_ROOT / folder_name

        print(f"\n{'=' * 90}", flush=True)
        print(f"开始处理: {parent_dir}", flush=True)
        print(f"仅保留: {sorted(keep_names)}", flush=True)
        print(f"模式: {'预演 DRY_RUN=True' if DRY_RUN else '真实删除 DRY_RUN=False'}", flush=True)
        print(f"{'=' * 90}", flush=True)

        subject_count, removed_count, failed_count, kept_count = clean_parent_folder(
            parent_dir,
            keep_names,
        )

        total_subjects += subject_count
        total_removed += removed_count
        total_failed += failed_count
        total_kept += kept_count

        print(f"\n[{folder_name}] 数据文件夹数: {subject_count}", flush=True)
        print(f"[{folder_name}] 保留文件数: {kept_count}", flush=True)
        print(f"[{folder_name}] {'将删除' if DRY_RUN else '已删除'}项目数: {removed_count}", flush=True)
        print(f"[{folder_name}] 删除失败项目数: {failed_count}", flush=True)

    print(f"\n{'=' * 90}", flush=True)
    print("全部完成", flush=True)
    print("运行位置: CLUSTER", flush=True)
    print(f"REMOTE_ROOT: {REMOTE_ROOT}", flush=True)
    print(f"总数据文件夹数: {total_subjects}", flush=True)
    print(f"总保留文件数: {total_kept}", flush=True)
    print(f"总{'将删除' if DRY_RUN else '已删除'}项目数: {total_removed}", flush=True)
    print(f"总失败项目数: {total_failed}", flush=True)
    print(f"{'=' * 90}", flush=True)


if __name__ == "__main__":
    main()
'''

    remote_script = remote_template
    remote_script = remote_script.replace("__DRY_RUN__", repr(DRY_RUN))
    remote_script = remote_script.replace("__REMOTE_ROOT_REPR__", repr(cluster_root))
    remote_script = remote_script.replace("__CONFIG_REPR__", config_as_python_literal)

    return remote_script


def run_cluster_mode():
    cluster_root = ROOT_BY_SOURCE["CLUSTER"]

    if not confirm_real_delete("CLUSTER", cluster_root):
        return

    try:
        import paramiko
    except ImportError:
        print("[ERROR] 当前 Python 环境没有安装 paramiko。")
        print("请先运行：pip install paramiko")
        sys.exit(1)

    print("\n" + "=" * 90)
    print("正在连接集群")
    print(f"HOST: {CLUSTER_USERNAME}@{CLUSTER_HOST}:{CLUSTER_PORT}")
    print(f"REMOTE_ROOT: {cluster_root}")
    print(f"模式: {'预演 DRY_RUN=True' if DRY_RUN else '真实删除 DRY_RUN=False'}")
    print("=" * 90)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=CLUSTER_HOST,
            port=CLUSTER_PORT,
            username=CLUSTER_USERNAME,
            password=CLUSTER_PASSWORD,
            timeout=20,
            banner_timeout=20,
            auth_timeout=20,
        )
    except Exception as e:
        print(f"[ERROR] SSH 连接失败：{repr(e)}")
        sys.exit(1)

    print("[OK] SSH 已连接")

    remote_script = build_remote_script()
    command = "python3 - <<'PY_REMOTE_SCRIPT'\n" + remote_script + "\nPY_REMOTE_SCRIPT\n"

    print("\n========== 开始在集群上执行清理脚本 ==========\n")

    stdin, stdout, stderr = ssh.exec_command(command)

    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            data = stdout.channel.recv(4096).decode("utf-8", errors="ignore")
            print(data, end="")
        if stderr.channel.recv_stderr_ready():
            data = stderr.channel.recv_stderr(4096).decode("utf-8", errors="ignore")
            print(data, end="")
        time.sleep(0.2)

    remaining_out = stdout.read().decode("utf-8", errors="ignore")
    remaining_err = stderr.read().decode("utf-8", errors="ignore")

    if remaining_out:
        print(remaining_out, end="")
    if remaining_err:
        print(remaining_err, end="")

    exit_status = stdout.channel.recv_exit_status()
    ssh.close()

    print("\n========== 集群任务结束 ==========")
    print(f"远程退出码：{exit_status}")

    if exit_status != 0:
        print("[ERROR] 远程脚本执行失败，请看上面的报错。")
        sys.exit(exit_status)


# ============================================================
# 主入口
# ============================================================

def main():
    target = choose_run_target()
    root = get_root_for_target(target)

    print("\n" + "=" * 90)
    print("脚本配置确认")
    print(f"运行位置: {target}")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"ROOT: {root}")
    print(f"CONFIG: { {k: sorted(v) for k, v in CONFIG.items()} }")
    print("")
    print("功能说明：")
    print("本脚本只做删除清理，不做分类。")
    print("它假设 ROOT 下面已经有 justT1 和 T1T2。")
    print("justT1 每个 ID 只保留 T1_acpc.nii.gz。")
    print("T1T2 每个 ID 只保留 T1_acpc.nii.gz 和 T2_acpc.nii.gz。")
    print("=" * 90)

    if target in {"LOCAL", "NAS"}:
        run_path_mode(target, root)
    elif target == "CLUSTER":
        run_cluster_mode()
    else:
        raise RuntimeError(f"未知运行位置: {target}")


if __name__ == "__main__":
    main()