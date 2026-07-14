import os
import shutil

#本脚本用于数据的T1 T2子文件夹文件剪切到数据根目录下，方便QC

def clean_and_flatten_mri_data(root_dir):
    # 遍历根目录下的所有被试文件夹
    for subject_folder in os.listdir(root_dir):
        subject_path = os.path.join(root_dir, subject_folder)

        # 确保当前项是文件夹，跳过独立的文件
        if not os.path.isdir(subject_path):
            continue

        print(f"Processing subject: {subject_folder}")

        # 需要处理的子文件夹列表
        sub_folders = ['T1', 'T2']

        for mod in sub_folders:
            mod_path = os.path.join(subject_path, mod)

            # 检查文件夹是否存在
            if not os.path.exists(mod_path):
                if mod == 'T2':
                    print(f"Notice: T2 folder not found in {subject_folder}. Skipping T2.")
                continue

            # 遍历 T1 或 T2 文件夹内的所有内容
            for item in os.listdir(mod_path):
                item_path = os.path.join(mod_path, item)

                # 确保当前处理的是文件
                if os.path.isfile(item_path):
                    # 条件 1：如果是 .json 文件，删除
                    if item.endswith('.json'):
                        os.remove(item_path)
                        print(f"Deleted JSON: {item_path}")
                    
                    # 条件 2：如果名字包含 "NDC"，删除
                    elif "NDC" in item:
                        os.remove(item_path)
                        print(f"Deleted NDC file: {item_path}")
                    
                    # 条件 3：剩下的文件，剪切到上一级目录（被试文件夹）
                    else:
                        target_file_path = os.path.join(subject_path, item)
                        
                        # 发散性思维防错处理：检查目标位置是否已有同名文件
                        if os.path.exists(target_file_path):
                            print(f"Warning: File {item} already exists in {subject_path}. Overwriting.")
                            
                        shutil.move(item_path, target_file_path)
                        print(f"Moved: {item} -> {subject_path}")

            # 遍历并处理完文件后，删除此时应为空的 T1 或 T2 文件夹
            try:
                os.rmdir(mod_path)
                print(f"Removed empty directory: {mod_path}")
            except OSError as e:
                # 严格控制删除权限：如果文件夹里还有其他子文件夹或无法识别的残留，避免误删
                print(f"Error: Could not remove {mod_path}. Directory might not be empty. Details: {e}")

if __name__ == "__main__":
    # 将此路径替换为你的实际数据根目录
    data_directory = r"D:\University\master\QC2026\2026\0622_CBCP\0_rawdata"
    clean_and_flatten_mri_data(data_directory)
    print("Data cleaning and flattening completed.")