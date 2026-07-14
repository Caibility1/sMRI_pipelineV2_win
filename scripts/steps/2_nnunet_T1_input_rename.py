##获取到需处理的T1，T2原始数据后，进行第一步，将T1名称批量修改为nnunet可识别的“T523_X_0000.nii.gz”形式。

import os
import shutil

#root_folder = r'D:\University\master\QC2026\2026\0622_CBCP\0_rawdata'
#target_folder = r'D:\University\master\QC2026\2026\0622_CBCP\2_T1_nnunet_rename'

root_folder = r'D:\University\master\QC2026\2026\0604_CBCP\questionable'
target_folder = r'D:\University\master\QC2026\2026\0604_CBCP\questionable_T1_nnunet_rename'
os.makedirs(target_folder, exist_ok=True)

for folder_name in os.listdir(root_folder):
    folder_path = os.path.join(root_folder, folder_name)

    if os.path.isdir(folder_path):
        t1_file_path = os.path.join(folder_path, "T1.nii.gz")

        if os.path.exists(t1_file_path):
            # === 【核心万能重命名逻辑】 ===
            # 直接把原文件夹名字里的下划线去掉（HC_Nre101 变成 HCNre101）
            clean_name = folder_name.replace("_", "") 
                    
            # 拼接成 nnU-Net 专属格式
            new_file_name = f"T523_{clean_name}_0000.nii.gz"
        
            target_file_path = os.path.join(target_folder, new_file_name)

            # 复制并重命名
            shutil.copy(t1_file_path, target_file_path)
            print(f"✅ 成功提取并改名: {folder_name}/T1.nii.gz  --->  {new_file_name}")
        else:
            print(f"❌ 跳过 {folder_name}: 没有找到 T1.nii.gz 文件。")
    else:
        print(f"⏭️ 跳过 {folder_name}: 不是文件夹。")

print("所有数据处理完毕！")

'''
        if os.path.exists(t1_file_path):
            if len(folder_name) == 10 and folder_name.isdigit():
                new_file_name = f"T523_{folder_name}_0000.nii.gz"
            elif folder_name.startswith("N") and len(folder_name) == 15:
                # 移除开头的"N"和中间的下划线，再拼接
                new_part = folder_name[1:].replace("_", "") 
                new_file_name = f"T523_{new_part}_0000.nii.gz"
            else:
                print(f"Skipping folder {folder_name}: Invalid folder name format.")
                continue

            target_file_path = os.path.join(target_folder, new_file_name)
            shutil.copy(t1_file_path, target_file_path)
            print(f"Copied and renamed: {t1_file_path} to {target_file_path}")
        else:
            print(f"Skipping folder {folder_name}: T1.nii.gz file not found.")
    else:
        print(f"Skipping {folder_name}: Not a directory.")
'''