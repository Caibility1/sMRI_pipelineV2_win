import os
import shutil
import re

# 源路径和目标路径
source_path = r"D:\Software\nnUNet_uii\train_seg\data_new_pipeline\5_skullstrip_preprocess_output\5_skullstrip_preprocess_output_abnormal"
target_path = r"D:\Software\nnUnet_uii\train_seg\data_new_pipeline\6_T1_acpc"

# 创建目标路径（如果不存在）
os.makedirs(target_path, exist_ok=True)

# 遍历源路径下的所有文件夹
for folder_name in os.listdir(source_path):
    folder_path = os.path.join(source_path, folder_name)

    # 检查是否是文件夹
    if os.path.isdir(folder_path):
        print(f"Processing folder: {folder_path}")

        # 构造 T1_acpc.nii.gz 文件的路径
        t1_acpc_path = os.path.join(folder_path, "T1_acpc.nii.gz")

        # 检查文件是否存在
        if not os.path.exists(t1_acpc_path):
            print(f"Skipping folder {folder_path}: Missing T1_acpc.nii.gz.")
            continue

        # 根据文件夹命名规则提取信息并生成新文件名
        if re.match(r"^\d{10}_\d{1,2}mo$", folder_name):  # 第一种命名方式：a_xmo
            new_file_name = f"T525_{folder_name.split('_')[0]}_0000.nii.gz"
        elif re.match(r"^N\d{3}_\d{10}_\d{1,2}mo$", folder_name):  # 第二种命名方式：Nb_c_xmo
            parts = folder_name.split('_')
            new_file_name = f"T525_{parts[0]}{parts[1]}_0000.nii.gz"
        else:
            print(f"Skipping folder {folder_path}: Unknown naming pattern.")
            continue

        # 构造目标文件路径
        target_file_path = os.path.join(target_path, new_file_name)

        # 复制文件到目标路径
        shutil.copy(t1_acpc_path, target_file_path)
        print(f"Copied and renamed: {t1_acpc_path} -> {target_file_path}")