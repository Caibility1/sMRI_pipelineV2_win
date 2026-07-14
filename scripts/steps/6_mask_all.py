import os
import shutil  # 新增：用于复制文件
import nibabel as nib

# 1. 指定工作基准目录 (同级目录的父文件夹)
base_dir = r"D:\University\master\QC2026\2026\0604_CBCP"

# 2. 定义输入和输出的绝对路径
#skullstrip_path = os.path.join(base_dir, "3_skullstrip")
#just_t1_path = os.path.join(base_dir, "justT1")
#t1_t2_path = os.path.join(base_dir, "T1T2")
skullstrip_path = os.path.join(base_dir, "questionable")
just_t1_path = os.path.join(base_dir, "q_justT1")
t1_t2_path = os.path.join(base_dir, "q_T1T2")

# 确保输出总文件夹存在
os.makedirs(just_t1_path, exist_ok=True)
os.makedirs(t1_t2_path, exist_ok=True)

# 3. 遍历 skullstrip 目录下的所有被试文件夹
for folder_name in os.listdir(skullstrip_path):
    folder_path = os.path.join(skullstrip_path, folder_name)

    if not os.path.isdir(folder_path):
        continue

    print(f"正在处理: {folder_name} ...")

    # 构造文件路径
    t1_path = os.path.join(folder_path, "T1.nii.gz")
    t2_path = os.path.join(folder_path, "T2.nii.gz")
    mask_path = os.path.join(folder_path, "mask.nii.gz")

    # 基础安全检查：如果没有 T1 或没有 mask，直接跳过
    if not os.path.exists(t1_path) or not os.path.exists(mask_path):
        print(f"跳过 {folder_name}: 缺少核心文件 (T1 或 mask)！")
        continue

    # 载入 T1 和 Mask 数据
    t1_img = nib.load(t1_path)
    mask_img = nib.load(mask_path)
    t1_data = t1_img.get_fdata()
    mask_data = mask_img.get_fdata()

    # 核心操作：掩膜提取 (Masking)
    t1_masked_data = t1_data * mask_data
    t1_masked_img = nib.Nifti1Image(t1_masked_data, t1_img.affine, t1_img.header)

    # === 分流逻辑：判断有没有 T2 ===
    has_t2 = os.path.exists(t2_path)

    if has_t2:
        # 【路线 A：包含 T2】
        # 建立对应的新家
        target_folder = os.path.join(t1_t2_path, folder_name)
        os.makedirs(target_folder, exist_ok=True)

        # 载入并处理 T2
        t2_img = nib.load(t2_path)
        t2_masked_data = t2_img.get_fdata() * mask_data
        t2_masked_img = nib.Nifti1Image(t2_masked_data, t2_img.affine, t2_img.header)

        # 直接保存剥离后的脑图到新家
        nib.save(t1_masked_img, os.path.join(target_folder, "T1.nii.gz"))
        nib.save(t2_masked_img, os.path.join(target_folder, "T2.nii.gz"))
        
        # 🌟 新增核心逻辑：将 mask.nii.gz 原封不动地搬运过去
        shutil.copy(mask_path, os.path.join(target_folder, "mask.nii.gz"))
        
        print(f"[双模态] 处理完毕！T1, T2 及 mask 已安全分流至 ---> T1T2/{folder_name}")

    else:
        # 【路线 B：只有 T1】
        target_folder = os.path.join(just_t1_path, folder_name)
        os.makedirs(target_folder, exist_ok=True)

        # 直接保存剥离后的脑图到新家
        nib.save(t1_masked_img, os.path.join(target_folder, "T1.nii.gz"))
        
        # 🌟 新增核心逻辑：将 mask.nii.gz 原封不动地搬运过去
        shutil.copy(mask_path, os.path.join(target_folder, "mask.nii.gz"))
        
        print(f"[单模态] 处理完毕！T1 及 mask 已安全分流至 ---> justT1/{folder_name}")

print("\n所有数据集 Mask 提取、打包搬运与智能分流全部完成！")