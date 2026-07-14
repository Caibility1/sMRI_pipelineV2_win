import os

# 指定路径（与之前的脚本保持一致）
skullstrip_path = r"D:\University\master\QC2026\2026\0310_CBCP\3_skullstrip"

def recover_filenames(base_path):
    if not os.path.exists(base_path):
        print(f"Error: Path {base_path} does not exist.")
        return

    print(f"Starting recovery in: {base_path}")
    count = 0

    # 遍历路径下的所有文件夹
    for folder_name in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder_name)

        # 仅处理文件夹
        if os.path.isdir(folder_path):
            # 检查是否包含 '_mo' 特征（兼容之前的 .0mo 和整数 mo）
            if "_sh" not in folder_name and "mo" in folder_name and "_" in folder_name:
                # 使用 rsplit('_', 1) 确保只从最后一个下划线处分割
                # 这样可以保护像 'N001_12345678' 这种原始 ID 本身的下划线
                parts = folder_name.rsplit('_', 1)
                
                # 再次确认被切掉的部分是否包含 'mo'，避免误伤
                if "mo" in parts[1]:
                    new_folder_name = parts[0]
                    new_folder_path = os.path.join(base_path, new_folder_name)

                    try:
                        # 执行重命名
                        os.rename(folder_path, new_folder_path)
                        print(f"Recovered: {folder_name} -> {new_folder_name}")
                        count += 1
                    except FileExistsError:
                        print(f"Error: Cannot rename {folder_name}, {new_folder_name} already exists.")
                    except Exception as e:
                        print(f"Error processing {folder_name}: {e}")

    print(f"\nRecovery complete. Total folders restored: {count}")

if __name__ == "__main__":
    recover_filenames(skullstrip_path)