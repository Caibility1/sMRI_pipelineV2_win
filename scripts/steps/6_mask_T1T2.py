## 在skullstrip文件夹中生成T1_mask和T2_mask文件，删除原T1T2文件
## 并将T1_mask重命名为T1，并将T2_mask重命名为T2.为preprocess步骤做准备。

import os
import nibabel as nib
import numpy as np

# 指定路径
skullstrip_path = r"D:\University\master\QC2026\2026\0309_SMGH+CBCP\3_skullstrip"

# 遍历 skullstrip 目录下的所有文件夹
for folder_name in os.listdir(skullstrip_path):
    folder_path = os.path.join(skullstrip_path, folder_name)

    # 检查是否是文件夹
    if os.path.isdir(folder_path):
        print(f"Processing folder: {folder_path}")

        # 构造文件路径
        t1_path = os.path.join(folder_path, "T1.nii.gz")
        t2_path = os.path.join(folder_path, "T2.nii.gz")
        mask_path = os.path.join(folder_path, "mask.nii.gz")

        # 检查文件是否存在
        if not os.path.exists(t1_path) or not os.path.exists(t2_path) or not os.path.exists(mask_path):
            print(f"Skipping folder {folder_path}: Missing required files.")
            continue

        # 加载 T1, T2 和 mask 文件
        t1_img = nib.load(t1_path)
        t2_img = nib.load(t2_path)
        mask_img = nib.load(mask_path)

        # 获取数据
        t1_data = t1_img.get_fdata()
        t2_data = t2_img.get_fdata()
        mask_data = mask_img.get_fdata()

        # 执行卷积操作
        t1_mask_data = t1_data * mask_data
        t2_mask_data = t2_data * mask_data

        # 保存结果
        t1_mask_img = nib.Nifti1Image(t1_mask_data, t1_img.affine, t1_img.header)
        t2_mask_img = nib.Nifti1Image(t2_mask_data, t2_img.affine, t2_img.header)

        t1_mask_path = os.path.join(folder_path, "T1_mask.nii.gz")
        t2_mask_path = os.path.join(folder_path, "T2_mask.nii.gz")

        nib.save(t1_mask_img, t1_mask_path)
        nib.save(t2_mask_img, t2_mask_path)

        print(f"Saved: {t1_mask_path} and {t2_mask_path}")

        # 删除原始 T1 和 T2 文件
        os.remove(t1_path)
        os.remove(t2_path)
        print(f"Deleted: {t1_path} and {t2_path}")

        # 重命名生成的文件
        os.rename(t1_mask_path, t1_path)
        os.rename(t2_mask_path, t2_path)
        print(f"Renamed: {t1_mask_path} to {t1_path}")
        print(f"Renamed: {t2_mask_path} to {t2_path}")