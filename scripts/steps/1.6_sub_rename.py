# SHCH数据跑1.5后会少掉sub，这个脚本补上

from pathlib import Path

# 根目录
ROOT_DIR = Path(r"D:\University\master\QC2026\2026\0413_SHCH\0_rawdata")

# True = 只打印不执行
# False = 真正重命名
DRY_RUN = False


def main():
    if not ROOT_DIR.exists():
        raise FileNotFoundError(f"路径不存在: {ROOT_DIR}")

    subdirs = [p for p in ROOT_DIR.iterdir() if p.is_dir()]
    print(f"共找到 {len(subdirs)} 个子文件夹\n")

    for folder in subdirs:
        old_name = folder.name

        # 已经是 sub 开头的就跳过，防止变成 subsubXXX
        if old_name.startswith("sub"):
            print(f"[跳过] 已是 sub 开头: {old_name}")
            continue

        new_name = "sub" + old_name
        new_path = folder.parent / new_name

        if new_path.exists():
            print(f"[跳过] 目标已存在: {new_name}")
            continue

        if DRY_RUN:
            print(f"[DRY-RUN] {old_name} -> {new_name}")
        else:
            folder.rename(new_path)
            print(f"[完成] {old_name} -> {new_name}")


if __name__ == "__main__":
    main()