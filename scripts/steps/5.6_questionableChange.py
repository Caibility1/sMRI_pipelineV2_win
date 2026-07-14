from pathlib import Path

root = Path(r"D:\University\master\QC2026\2026\修正后\0422_questionable")

required_files = {"T1.nii.gz", "mask.nii.gz", "T1_age.nii.gz"}
optional_files = {"T2.nii.gz"}
allowed_files = required_files | optional_files

problem_folders = []
processed_count = 0

for case_dir in root.iterdir():
    if not case_dir.is_dir():
        continue

    # 只统计当前文件夹下的 .nii.gz 文件，不递归
    nii_files = [f for f in case_dir.iterdir() if f.is_file() and f.name.endswith(".nii.gz")]
    file_names = {f.name for f in nii_files}

    missing_required = required_files - file_names
    extra_files = file_names - allowed_files

    # 条件1：文件数必须是3或4
    # 条件2：必须包含 T1 / mask / T1_age
    # 条件3：不能有额外的 .nii.gz 文件
    if len(nii_files) not in (3, 4) or missing_required or extra_files:
        print(f"[有问题] {case_dir.name}")
        print(f"  当前 nii.gz 文件: {sorted(file_names)}")

        if len(nii_files) not in (3, 4):
            print(f"  文件数量异常: {len(nii_files)}（应为3或4）")
        if missing_required:
            print(f"  缺少必须文件: {sorted(missing_required)}")
        if extra_files:
            print(f"  存在额外文件: {sorted(extra_files)}")

        problem_folders.append(case_dir.name)
        continue

    # 没问题：删除 T1，再把 T1_age 改名为 T1
    t1_path = case_dir / "T1.nii.gz"
    t1_age_path = case_dir / "T1_age.nii.gz"
    new_t1_path = case_dir / "T1.nii.gz"

    try:
        t1_path.unlink()  # 删除原 T1
        t1_age_path.rename(new_t1_path)  # T1_age -> T1
        print(f"[已处理] {case_dir.name}")
        processed_count += 1
    except Exception as e:
        print(f"[处理失败] {case_dir.name}: {e}")
        problem_folders.append(case_dir.name)

print("\n===== 处理完成 =====")
print(f"成功处理: {processed_count} 个文件夹")
print(f"有问题/失败: {len(problem_folders)} 个文件夹")

if problem_folders:
    print("问题文件夹如下：")
    for name in problem_folders:
        print(f"  - {name}")