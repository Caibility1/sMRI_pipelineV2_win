from pathlib import Path
import shutil

# ===================== 路径设置 =====================

source_dir = Path(r"D:\University\master\QC2026\2026\0511_questionable\3_skullstrip")

# 同级目录
out_t1t2_dir = source_dir.parent / "T1T2"
out_just_t1_dir = source_dir.parent / "justT1"

T1_NAME = "T1.nii.gz"
T2_NAME = "T2.nii.gz"

# True  = 只预演，不真正复制
# False = 真正复制
DRY_RUN = False

# 如果目标文件夹已经存在，是否删除后重新复制
OVERWRITE_EXISTING = True


# ===================== 工具函数 =====================

def copy_subject_folder(src: Path, dst_parent: Path) -> Path:
    """
    复制整个 subject 文件夹到 dst_parent 下。
    如果目标已存在：
      - OVERWRITE_EXISTING=True：先删除旧目标，再重新复制
      - OVERWRITE_EXISTING=False：自动加后缀，避免覆盖
    """
    dst_parent.mkdir(parents=True, exist_ok=True)

    dst = dst_parent / src.name

    if dst.exists():
        if OVERWRITE_EXISTING:
            shutil.rmtree(dst)
        else:
            i = 1
            while True:
                new_dst = dst_parent / f"{src.name}_copy_{i}"
                if not new_dst.exists():
                    dst = new_dst
                    break
                i += 1

    shutil.copytree(src, dst)
    return dst


# ===================== 主流程 =====================

def main():
    if not source_dir.exists():
        raise FileNotFoundError(f"source_dir 不存在：{source_dir}")

    out_t1t2_dir.mkdir(parents=True, exist_ok=True)
    out_just_t1_dir.mkdir(parents=True, exist_ok=True)

    subjects = [p for p in source_dir.iterdir() if p.is_dir()]

    copied_t1t2 = []
    copied_just_t1 = []
    skipped_no_t1 = []
    skipped_only_t2 = []
    skipped_empty_or_other = []

    for subj_dir in subjects:
        t1_path = subj_dir / T1_NAME
        t2_path = subj_dir / T2_NAME

        has_t1 = t1_path.exists() and t1_path.is_file()
        has_t2 = t2_path.exists() and t2_path.is_file()

        if has_t1 and has_t2:
            target_parent = out_t1t2_dir

            if DRY_RUN:
                print(f"[DRY-RUN] T1+T2：{subj_dir} -> {target_parent / subj_dir.name}")
            else:
                copied_path = copy_subject_folder(subj_dir, target_parent)
                print(f"[复制 T1+T2] {subj_dir.name} -> {copied_path}")

            copied_t1t2.append(subj_dir.name)

        elif has_t1 and not has_t2:
            target_parent = out_just_t1_dir

            if DRY_RUN:
                print(f"[DRY-RUN] just T1：{subj_dir} -> {target_parent / subj_dir.name}")
            else:
                copied_path = copy_subject_folder(subj_dir, target_parent)
                print(f"[复制 justT1] {subj_dir.name} -> {copied_path}")

            copied_just_t1.append(subj_dir.name)

        elif (not has_t1) and has_t2:
            skipped_only_t2.append(subj_dir.name)

        else:
            skipped_empty_or_other.append(subj_dir.name)

    # ===================== 打印总结 =====================

    print("\n==================== 处理完成 ====================")
    print(f"来源目录：{source_dir}")
    print(f"T1T2 输出目录：{out_t1t2_dir}")
    print(f"justT1 输出目录：{out_just_t1_dir}")
    print(f"DRY_RUN：{DRY_RUN}")
    print(f"OVERWRITE_EXISTING：{OVERWRITE_EXISTING}")

    print("\n==================== 数量统计 ====================")
    print(f"总 subject 文件夹数量：{len(subjects)}")
    print(f"T1 + T2 都有，已复制到 T1T2：{len(copied_t1t2)}")
    print(f"只有 T1，没有 T2，已复制到 justT1：{len(copied_just_t1)}")
    print(f"只有 T2，没有 T1，未复制：{len(skipped_only_t2)}")
    print(f"T1/T2 都没有，未复制：{len(skipped_empty_or_other)}")

    print("\n==================== T1 + T2 都有 ====================")
    if copied_t1t2:
        for name in sorted(copied_t1t2):
            print(name)
    else:
        print("无")

    print("\n==================== 只有 T1，没有 T2 ====================")
    if copied_just_t1:
        for name in sorted(copied_just_t1):
            print(name)
    else:
        print("无")

    print("\n==================== 只有 T2，没有 T1，未复制 ====================")
    if skipped_only_t2:
        for name in sorted(skipped_only_t2):
            print(name)
    else:
        print("无")

    print("\n==================== T1/T2 都没有，未复制 ====================")
    if skipped_empty_or_other:
        for name in sorted(skipped_empty_or_other):
            print(name)
    else:
        print("无")


if __name__ == "__main__":
    main()