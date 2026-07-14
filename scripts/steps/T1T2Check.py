from pathlib import Path

# =========================
# 配置区
# =========================
ROOT_DIR = Path(r"D:\University\master\QC2026\2026\0409_XUXIU\7_data")

#本脚本用于检查送分割之前的数据T1/T2缺失情况

# 是否递归搜索子文件夹里的文件
RECURSIVE = True

# 是否把结果保存到 txt
SAVE_TXT = False
OUTPUT_TXT = ROOT_DIR / "t1_t2_check_result.txt"


def contains_t1(filename: str) -> bool:
    return "t1" in filename.lower()


def contains_t2(filename: str) -> bool:
    return "t2" in filename.lower()


def get_all_files(subject_dir: Path):
    if RECURSIVE:
        return [p for p in subject_dir.rglob("*") if p.is_file()]
    else:
        return [p for p in subject_dir.iterdir() if p.is_file()]


def check_subject(subject_dir: Path):
    files = get_all_files(subject_dir)

    has_t1 = False
    has_t2 = False

    for f in files:
        name = f.name.lower()
        if contains_t1(name):
            has_t1 = True
        if contains_t2(name):
            has_t2 = True

        if has_t1 and has_t2:
            break

    if has_t1 and has_t2:
        status = "T1T2都有"
    elif has_t1 and not has_t2:
        status = "只有T1"
    elif has_t2 and not has_t1:
        status = "只有T2"
    else:
        status = "T1T2都没有"

    return status


def main():
    if not ROOT_DIR.exists():
        raise FileNotFoundError(f"根目录不存在: {ROOT_DIR}")

    subject_dirs = sorted([p for p in ROOT_DIR.iterdir() if p.is_dir()])

    both_list = []
    only_t1_list = []
    only_t2_list = []
    neither_list = []

    for subject_dir in subject_dirs:
        status = check_subject(subject_dir)

        if status == "T1T2都有":
            both_list.append(subject_dir.name)
        elif status == "只有T1":
            only_t1_list.append(subject_dir.name)
        elif status == "只有T2":
            only_t2_list.append(subject_dir.name)
        else:
            neither_list.append(subject_dir.name)

    lines = []
    lines.append(f"检查根目录: {ROOT_DIR}")
    lines.append(f"数据子文件夹总数: {len(subject_dirs)}")
    lines.append("")
    lines.append("统计结果：")
    lines.append(f"1. T1T2都有: {len(both_list)}")
    lines.append(f"2. 只有T1:   {len(only_t1_list)}")
    lines.append(f"3. 只有T2:   {len(only_t2_list)}")
    lines.append(f"4. T1T2都没有: {len(neither_list)}")
    lines.append("")

    lines.append("只有T1的文件夹：")
    if only_t1_list:
        lines.extend(only_t1_list)
    else:
        lines.append("无")
    lines.append("")

    lines.append("只有T2的文件夹：")
    if only_t2_list:
        lines.extend(only_t2_list)
    else:
        lines.append("无")
    lines.append("")

    lines.append("T1T2都没有的文件夹：")
    if neither_list:
        lines.extend(neither_list)
    else:
        lines.append("无")
    lines.append("")

    result_text = "\n".join(lines)
    print(result_text)

    if SAVE_TXT:
        with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
            f.write(result_text)
        print(f"\n结果已保存到: {OUTPUT_TXT}")


if __name__ == "__main__":
    main()