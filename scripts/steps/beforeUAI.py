import shutil
from pathlib import Path

# =========================
# 配置区
# =========================
ROOT_DIR = Path(r"D:\University\master\QC2026\2026\0604_CBCP\fail\justT1")

# True = 只打印将要删除的内容，不真正执行
# False = 真正执行删除
DRY_RUN = False

# 每个被试文件夹下唯一允许保留的文件
KEEP_FILES = {
    "T1_acpc.nii.gz",
    "T2_acpc.nii.gz",
}


def log(msg):
    print(msg)


def delete_file(path: Path):
    if DRY_RUN:
        log(f"[DRY-RUN] 删除文件: {path}")
    else:
        path.unlink(missing_ok=True)
        log(f"[删除文件] {path}")


def delete_dir(path: Path):
    if DRY_RUN:
        log(f"[DRY-RUN] 删除文件夹: {path}")
    else:
        shutil.rmtree(path, ignore_errors=True)
        log(f"[删除文件夹] {path}")


def process_subject(subject_dir: Path):
    log("=" * 80)
    log(f"处理被试文件夹: {subject_dir}")

    if not subject_dir.is_dir():
        log(f"[跳过] 不是文件夹: {subject_dir}")
        return

    # 先检查根目录下是否存在要保留的文件
    existing_names = {p.name for p in subject_dir.iterdir() if p.is_file()}
    missing = [name for name in KEEP_FILES if name not in existing_names]

    if missing:
        log(f"[警告] 该被试根目录缺少以下保留文件: {missing}")
        log("[警告] 为避免误删，该被试先跳过，不执行删除。")
        return

    # 删除除 KEEP_FILES 之外的所有根目录内容
    for item in subject_dir.iterdir():
        if item.is_file():
            if item.name in KEEP_FILES:
                log(f"[保留文件] {item}")
            else:
                delete_file(item)

        elif item.is_dir():
            delete_dir(item)

        else:
            log(f"[跳过] 未知类型: {item}")

    log(f"[完成] {subject_dir.name}")


def main():
    if not ROOT_DIR.exists():
        raise FileNotFoundError(f"根目录不存在: {ROOT_DIR}")

    subject_dirs = [p for p in ROOT_DIR.iterdir() if p.is_dir()]
    log(f"根目录: {ROOT_DIR}")
    log(f"被试数量: {len(subject_dirs)}")
    log(f"DRY_RUN = {DRY_RUN}")
    log("开始处理...\n")

    for subject_dir in subject_dirs:
        process_subject(subject_dir)

    log("\n全部完成。")


if __name__ == "__main__":
    main()