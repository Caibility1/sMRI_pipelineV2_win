# add_brain_from_nas.py
# 功能：
# 1. 遍历本地 segmentation 结果：
#       D:\University\master\QC2026\2026\0604_CBCP\20260617_results\justT1\ID
#       D:\University\master\QC2026\2026\0604_CBCP\20260617_results\T1T2\ID
#
# 2. 根据 ID 前缀决定去哪个 NAS 来源找原始 T1_acpc.nii.gz：
#       0101... -> Site1_STU
#       N...    -> Site2_XMH
#       03...   -> Site3_CZH
#       04...   -> ASD
#
# 3. 找到后复制到 segmentation 的对应 ID 文件夹中，命名为：
#       brain.nii.gz
#
# 4. 打印 total / success / failed / skipped，以及失败 ID。
#
# 兼容 Python 3.7 / 3.8 / 3.9，不使用 Path | None 这种新语法。

from pathlib import Path
import shutil
import subprocess
import os
import sys


# =========================================================
# 你主要改这里
# =========================================================

DRY_RUN = False          # 先 True 预览；确认无误后改 False 真复制
OVERWRITE = False        # 本地已有 brain.nii.gz 时是否覆盖

LOCAL_SEG_ROOT = Path(r"D:\University\master\QC2026\2026\0604_CBCP\20260617_results")

LOCAL_GROUPS = [
    "justT1",
    "T1T2",
]

LOCAL_BRAIN_NAME = "brain.nii.gz"

SOURCE_T1_NAMES = [
    "T1_acpc.nii.gz",
    "T1_acpc.nii",
]


# ========== NAS 账号密码 ==========
# 默认用第二行密码。
# 第三行那个先作为备用密码留着，不自动使用；如果默认密码不行，你自己把 password 改成 alt_password。

NAS_USER = "linm"
NAS_PASSWORD = "fGWH|1,I"
NAS_ALT_PASSWORD = r"l9cG5/g{"


# ========== NAS 连接 ==========
# 脚本会先执行 net use 连接这两个共享。
# 如果你电脑已经手动连上了，也可以把 CONNECT_NAS 改成 False。

CONNECT_NAS = True

# 如果 Windows 已经用另一个账号连过同一个 NAS，可能报 1219。
# 遇到这种情况，可以把 DELETE_EXISTING_NET_USE 改成 True，让脚本先 net use /delete。
DELETE_EXISTING_NET_USE = False

NAS_CONNECTIONS = [
    {
        "name": "CBCP_NAS_002",
        "share": r"\\10.19.136.231\002",
        "user": NAS_USER,
        "password": NAS_PASSWORD,
    },
    {
        "name": "ASD_NAS_data3",
        "share": r"\\10.19.138.153\data3",
        "user": NAS_USER,
        "password": NAS_PASSWORD,
    },
]


# ========== 数据源规则 ==========
# 每条规则：
#   name      : 来源名字
#   prefixes  : ID 前缀
#   roots     : 去哪些根目录下找 ID
#
# 注意：
# Site1 / Site2 / Site3 我按你给的结构统一写成：
#   SiteX_xxx\1_sMRI\3_sMRI_preprocessing
#
# ASD 目前按你给的：
#   \\10.19.138.153\data3\XUXIU_ASD

NAS_SOURCES = [
    {
        "name": "Site1_STU",
        "prefixes": ["0101"],
        "roots": [
            Path(r"\\10.19.136.231\002\CBCP\CBCP_MRI\4_VisualQC_Processing\Site1_STU\1_sMRI\3_sMRI_preprocessing"),
        ],
    },
    {
        "name": "Site2_XMH",
        "prefixes": ["N"],
        "roots": [
            Path(r"\\10.19.136.231\002\CBCP\CBCP_MRI\4_VisualQC_Processing\Site2_XMH\1_sMRI\3_sMRI_preprocessing"),
        ],
    },
    {
        "name": "Site3_CZH",
        "prefixes": ["04"],
        "roots": [
            Path(r"\\10.19.136.231\002\CBCP\CBCP_MRI\4_VisualQC_Processing\Site3_CZH\1_sMRI\3_sMRI_preprocessing"),
        ],
    },
    {
        "name": "ASD",
        "prefixes": ["0103"],
        "roots": [
            Path(r"\\10.19.138.153\data3\XUXIU_ASD\2_Processing\1_sMRI\3_sMRI_preprocessing"),
        ],
    },
]


# ========== 查找策略 ==========
# EXACT_ID_DIR_FIRST:
#   优先查 root\ID\T1_acpc.nii.gz
#
# FALLBACK_SCAN_IMMEDIATE_CHILDREN:
#   如果 root\ID 不存在，则只扫描 root 的一级子文件夹，找名字等于 ID 或以 ID 开头的文件夹。
#   这个不会递归扫整个 site，速度相对可控。
#
# RECURSIVE_WITHIN_ID_DIR:
#   一旦找到某个 ID 文件夹，就允许在这个 ID 文件夹内部递归找 T1_acpc.nii.gz。
#   注意递归范围只限单个 ID 文件夹，不会全站递归。

EXACT_ID_DIR_FIRST = True
FALLBACK_SCAN_IMMEDIATE_CHILDREN = True
RECURSIVE_WITHIN_ID_DIR = True


# ========== 集群配置：当前不用，先留着方便以后改回去 ==========
CLUSTER_CONFIG = {
    "host": "10.15.49.7",
    "port": 22112,
    "user": "linmo2025",
    "password": "E>vq2fgPr9.",
    "base": "/public_bme2/bme-zhanghan/linmo2025/2026/0604_CBCP",
    "search_dirs": [
        "justT1",
        "T1T2",
        "T1T2_f2",
        "fail/justT1_f",
        "fail/T1T2_f",
    ],
}

# =========================================================
# 主逻辑一般不用改
# =========================================================


DIR_CACHE = {}


def log(msg):
    print(msg)


def run_cmd(cmd):
    """
    运行 Windows 命令。
    不用 shell=True，避免密码里的 | 被当成管道符。
    """
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="gbk",
            errors="ignore"
        )
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 999, "", str(e)


def connect_one_nas(conn):
    share = conn["share"]
    user = conn["user"]
    password = conn["password"]

    if DELETE_EXISTING_NET_USE:
        delete_cmd = ["net", "use", share, "/delete", "/y"]
        code, out, err = run_cmd(delete_cmd)
        log("[NET USE DELETE] {} returncode={}".format(share, code))

    cmd = [
        "net",
        "use",
        share,
        password,
        "/user:{}".format(user),
        "/persistent:no",
    ]

    code, out, err = run_cmd(cmd)

    if code == 0:
        log("[NET USE OK] {}".format(share))
        return True

    # 如果已经连接过，net use 可能返回错误。
    # 这时只要路径能访问，就继续。
    if Path(share).exists():
        log("[NET USE WARNING] {} net use 返回错误，但路径可访问，继续。".format(share))
        if out.strip():
            log("  stdout: {}".format(out.strip()))
        if err.strip():
            log("  stderr: {}".format(err.strip()))
        return True

    log("[NET USE ERROR] 无法连接 NAS: {}".format(share))
    if out.strip():
        log("  stdout: {}".format(out.strip()))
    if err.strip():
        log("  stderr: {}".format(err.strip()))
    return False


def connect_all_nas():
    if not CONNECT_NAS:
        log("[INFO] CONNECT_NAS=False，跳过 net use。")
        return True

    log("========== connect NAS ==========")

    all_ok = True

    for conn in NAS_CONNECTIONS:
        ok = connect_one_nas(conn)
        if not ok:
            all_ok = False

    log("")

    return all_ok


def collect_local_id_dirs():
    """
    收集本地 segmentation 结果里的 ID 文件夹。
    返回：
        [(group_name, id_name, id_dir), ...]
    """
    items = []

    for group in LOCAL_GROUPS:
        group_dir = LOCAL_SEG_ROOT / group

        if not group_dir.exists():
            log("[WARNING] 本地分类文件夹不存在，跳过：{}".format(group_dir))
            continue

        for p in group_dir.iterdir():
            if p.is_dir():
                items.append((group, p.name, p))

    return items


def get_source_for_id(id_name):
    """
    根据 ID 前缀选择 NAS_SOURCE。
    """
    for source in NAS_SOURCES:
        for prefix in source["prefixes"]:
            if id_name.startswith(prefix):
                return source

    return None


def list_immediate_dirs(root):
    """
    缓存 root 的一级子目录，避免每个 ID 都重新扫一遍。
    """
    key = str(root)

    if key in DIR_CACHE:
        return DIR_CACHE[key]

    dirs = []

    try:
        for p in root.iterdir():
            if p.is_dir():
                dirs.append(p)
    except Exception as e:
        log("[WARNING] 无法列出目录：{}，原因：{}".format(root, e))

    DIR_CACHE[key] = dirs
    return dirs


def candidate_id_dirs_from_root(root, id_name):
    """
    在一个 root 下找可能的 ID 文件夹。
    优先 root\ID。
    如果没有，再扫描 root 的一级子文件夹，找：
        ID
        ID_xxx
        ID-xxx
    """
    candidates = []

    if EXACT_ID_DIR_FIRST:
        exact_dir = root / id_name
        if exact_dir.exists() and exact_dir.is_dir():
            candidates.append(exact_dir)
            return candidates

    if not FALLBACK_SCAN_IMMEDIATE_CHILDREN:
        return candidates

    children = list_immediate_dirs(root)

    for child in children:
        name = child.name

        if name == id_name:
            candidates.append(child)
        elif name.startswith(id_name + "_"):
            candidates.append(child)
        elif name.startswith(id_name + "-"):
            candidates.append(child)

    return candidates


def find_t1_in_id_dir(id_dir):
    """
    在一个 ID 文件夹里找 T1_acpc.nii.gz / T1_acpc.nii。
    先查直接子文件。
    找不到时，可在 ID 文件夹内部递归。
    """
    direct_found = []

    for t1_name in SOURCE_T1_NAMES:
        p = id_dir / t1_name
        if p.exists() and p.is_file():
            direct_found.append(p)

    if direct_found:
        return sorted(direct_found, key=lambda x: len(str(x)))[0]

    if not RECURSIVE_WITHIN_ID_DIR:
        return None

    recursive_found = []

    for t1_name in SOURCE_T1_NAMES:
        try:
            for p in id_dir.rglob(t1_name):
                if p.exists() and p.is_file():
                    recursive_found.append(p)
        except Exception as e:
            log("[WARNING] 递归搜索失败：{}，原因：{}".format(id_dir, e))

    if recursive_found:
        return sorted(recursive_found, key=lambda x: len(str(x)))[0]

    return None


def find_source_t1(id_name):
    """
    根据 ID 前缀选 source，然后在该 source 的 roots 里找 T1。
    返回：
        source_name, source_t1_path, matched_id_dir

    找不到则：
        None, None, None
    """
    source = get_source_for_id(id_name)

    if source is None:
        return None, None, None

    source_name = source["name"]

    for root in source["roots"]:
        if not root.exists():
            log("[WARNING] 来源根目录不存在或不可访问：{}".format(root))
            continue

        candidate_dirs = candidate_id_dirs_from_root(root, id_name)

        for id_dir in candidate_dirs:
            t1_path = find_t1_in_id_dir(id_dir)
            if t1_path is not None:
                return source_name, t1_path, id_dir

    return source_name, None, None


def copy_one(source_t1, local_brain):
    """
    复制 source_t1 到 local_brain。
    使用临时文件，避免复制中断留下半截 brain.nii.gz。
    """
    if local_brain.exists() and not OVERWRITE:
        return False, "本地已存在 brain.nii.gz 且 OVERWRITE=False"

    tmp_path = local_brain.with_name(local_brain.name + ".tmp_copy")

    if tmp_path.exists():
        tmp_path.unlink()

    shutil.copy2(str(source_t1), str(tmp_path))
    os.replace(str(tmp_path), str(local_brain))

    return True, "ok"


def main():
    if not LOCAL_SEG_ROOT.exists():
        log("[ERROR] 本地 segmentation 根目录不存在：{}".format(LOCAL_SEG_ROOT))
        sys.exit(1)

    local_items = collect_local_id_dirs()

    log("========== add brain.nii.gz from NAS ==========")
    log("LOCAL_SEG_ROOT: {}".format(LOCAL_SEG_ROOT))
    log("DRY_RUN       : {}".format(DRY_RUN))
    log("OVERWRITE     : {}".format(OVERWRITE))
    log("")
    log("本地待处理 ID 总数: {}".format(len(local_items)))
    log("")

    if len(local_items) == 0:
        log("[ERROR] 没有找到任何本地 ID 文件夹。")
        sys.exit(1)

    nas_ok = connect_all_nas()

    if not nas_ok:
        log("[ERROR] NAS 连接失败。")
        log("如果你确认已经手动连接 NAS，可以把 CONNECT_NAS 改成 False 再试。")
        sys.exit(1)

    total = 0
    success = []
    failed = []
    skipped = []

    log("========== processing ==========")

    for group, id_name, id_dir in sorted(local_items, key=lambda x: (x[0], x[1])):
        total += 1

        local_brain = id_dir / LOCAL_BRAIN_NAME

        if local_brain.exists() and not OVERWRITE:
            skipped.append((group, id_name, "本地已存在 brain.nii.gz"))
            log("[SKIP] {}/{}: brain.nii.gz already exists".format(group, id_name))
            continue

        source = get_source_for_id(id_name)

        if source is None:
            failed.append((group, id_name, "ID 前缀无法判断来源"))
            log("[FAIL] {}/{}: unknown prefix".format(group, id_name))
            continue

        source_name, source_t1, matched_id_dir = find_source_t1(id_name)

        if source_t1 is None:
            failed.append((group, id_name, "在 {} 中没找到 T1_acpc.nii.gz".format(source_name)))
            log("[FAIL] {}/{}: not found in {}".format(group, id_name, source_name))
            continue

        if DRY_RUN:
            success.append((group, id_name, source_name, str(source_t1)))
            log("[DRY-RUN] {}/{}: {} -> {}".format(
                group,
                id_name,
                source_t1,
                local_brain
            ))
        else:
            ok, msg = copy_one(source_t1, local_brain)

            if ok:
                success.append((group, id_name, source_name, str(source_t1)))
                log("[OK] {}/{}: copied from {}".format(group, id_name, source_name))
            else:
                failed.append((group, id_name, msg))
                log("[FAIL] {}/{}: {}".format(group, id_name, msg))

    log("")
    log("========== summary ==========")
    log("total   : {}".format(total))
    log("success : {}".format(len(success)))
    log("failed  : {}".format(len(failed)))
    log("skipped : {}".format(len(skipped)))

    if failed:
        log("")
        log("Failed IDs:")
        for group, id_name, reason in failed:
            log("  {}/{}: {}".format(group, id_name, reason))

    if skipped:
        log("")
        log("Skipped IDs:")
        for group, id_name, reason in skipped:
            log("  {}/{}: {}".format(group, id_name, reason))

    log("")
    if DRY_RUN:
        log("当前是 DRY_RUN=True，没有真正复制文件。确认打印路径没问题后，把 DRY_RUN 改成 False 再跑。")
    else:
        log("完成。")


if __name__ == "__main__":
    main()