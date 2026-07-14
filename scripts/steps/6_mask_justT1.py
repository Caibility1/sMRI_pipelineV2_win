import os
import nibabel as nib
import numpy as np

# 指定路径
base_path = r"D:\University\master\QC2026\2026\0309_SMGH+CBCP\3_skullstrip"

# 遍历 base_path 下的所有文件夹
for folder_name in os.listdir(base_path):
    folder_path = os.path.join(base_path, folder_name)

    # 检查是否是文件夹
    if os.path.isdir(folder_path):
        print(f"Processing folder: {folder_path}")

        # 构造文件路径
        t1_path = os.path.join(folder_path, "T1.nii.gz")
        mask_path = os.path.join(folder_path, "mask.nii.gz")

        # 检查文件是否存在
        if not os.path.exists(t1_path) or not os.path.exists(mask_path):
            print(f"Skipping folder {folder_path}: Missing 'T1.nii.gz' or 'mask.nii.gz'.")
            continue

        # 加载 T1 和 mask 文件
        t1_image = nib.load(t1_path)
        mask_image = nib.load(mask_path)

        # 获取数据
        t1_data = t1_image.get_fdata()
        mask_data = mask_image.get_fdata()

        # 执行逐元素乘法操作
        multiplied_data = t1_data * mask_data

        # 创建新的 NIfTI 文件
        output_image = nib.Nifti1Image(multiplied_data, t1_image.affine, t1_image.header)

        # 保存结果为 T1_mask.nii.gz
        output_path = os.path.join(folder_path, "T1_mask.nii.gz")
        nib.save(output_image, output_path)
        print(f"Saved: {output_path}")

        # 删除原始 T1.nii.gz 文件
        os.remove(t1_path)
        print(f"Deleted: {t1_path}")

        # 将 T1_mask.nii.gz 重命名为 T1.nii.gz
        new_t1_path = os.path.join(folder_path, "T1.nii.gz")
        os.rename(output_path, new_t1_path)
        print(f"Renamed: {output_path} to {new_t1_path}")
