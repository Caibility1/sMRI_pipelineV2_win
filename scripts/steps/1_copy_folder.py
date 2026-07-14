## 将NAS中T1_T2_qc_pass的文件夹复制到本地后，本script重命名其中的文件为“T1.nii.gz”，“T2.nii.gz”。
## 这一步应该在完成QC后再运行

import os
import shutil

# 源路径和目标路径
# source_folder = r'D:\Software\nnUNet_uii\sMRI_new_pipeline\data\CBCP_0401\RAW'
#\\10.19.138.153\data2\SHCHInfant_YH
target_folder = r'D:\University\master\QC2026\2026\0622_CBCP\0_rawdata'
#target_folder = r'\\10.19.138.153\data2\SHCHInfant_YH'

# 确保目标路径存在
os.makedirs(target_folder, exist_ok=True)

# # 复制整个文件夹
# shutil.copytree(source_folder, target_folder, dirs_exist_ok=True)
# print(f"Copied entire folder from {source_folder} to {target_folder}")

# 遍历目标文件夹中的所有子文件夹
for folder_name in os.listdir(target_folder):
    folder_path = os.path.join(target_folder, folder_name)

    # 检查是否是文件夹
    if os.path.isdir(folder_path):
        t1_found = False
        t2_found = False

        # 遍历子文件夹中的所有文件
        for file_name in os.listdir(folder_path):
            if file_name.startswith(("t1", "T1")) and file_name.endswith(".nii.gz"):
                # 重命名为 T1.nii.gz
                new_file_name = "T1.nii.gz"
                os.rename(os.path.join(folder_path, file_name), os.path.join(folder_path, new_file_name))
                t1_found = True
                print(f"Renamed {file_name} to {new_file_name} in folder {folder_name}")

            if file_name.startswith(("t2", "T2")) and file_name.endswith(".nii.gz"):
                # 重命名为 T2.nii.gz
                new_file_name = "T2.nii.gz"
                os.rename(os.path.join(folder_path, file_name), os.path.join(folder_path, new_file_name))
                t2_found = True
                print(f"Renamed {file_name} to {new_file_name} in folder {folder_name}")

        # 检查是否缺少文件
        if not t1_found:
            print(f"Folder {folder_name} is missing a 't1' file.")
        if not t2_found:
            print(f"Folder {folder_name} is missing a 't2' file.")