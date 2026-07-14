## 打印提取后所有T1文件名称，用以实时修改dataset.json文件内容。
import os

def list_files_in_folder(folder_path):
    try:
        # 获取文件夹中的所有文件
        file_names = os.listdir(folder_path)
        # 过滤掉文件夹，只保留文件
        file_names = [file for file in file_names if os.path.isfile(os.path.join(folder_path, file))]

        # 以特定格式打印文件名称
        for file_name in file_names:
            print(f'"./imagesTs/{file_name}",')

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # 设置文件夹路径
    folder_path = r'D:\University\master\QC2026\2026\0604_CBCP\questionable_T1_nnunet_rename'
    #2_T1_nnunet_renamed
    list_files_in_folder(folder_path)