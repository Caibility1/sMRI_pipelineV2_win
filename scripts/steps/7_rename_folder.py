import os
import pandas as pd

# 指定路径
skullstrip_path = r"D:\University\master\QC2026\2026\0310_CBCP\T1T2"
excel_path = r"D:\University\master\QC2026\2026\0310_CBCP\month.xlsx"

# 1. 读取 Excel 文件中的所有 Sheet
all_sheets_df = pd.read_excel(excel_path, sheet_name=None)

id_age_dict = {}

# 2. 构造大字典
for sheet_name, df in all_sheets_df.items():
    df.columns = [str(col).strip() for col in df.columns]
    
    target_id_col = next((c for c in df.columns if c.upper() == 'MRI_ID'), None)
    target_month_col = next((c for c in df.columns if c.upper() == 'MONTHS'), None)

    if target_id_col and target_month_col:
        for index, row in df.iterrows():
            val = row[target_id_col]
            if pd.isna(val):
                continue
            
            # 处理 ID：转为字符串并处理数字后缀 .0
            raw_id = str(val).split('.')[0].strip()
            
            # 关键改进：如果是 10 位以下的纯数字，补齐前导零到 10 位
            # 这样就能匹配 0101010265 这种文件夹了
            if raw_id.isdigit() and len(raw_id) <= 10:
                raw_id = raw_id.zfill(10)
            
            try:
                # 确保月份转为整数，避免出现 .0mo
                age_val = int(float(row[target_month_col]))
                id_age_dict[raw_id] = age_val
            except (ValueError, TypeError):
                continue

# 打印一下总共找到了多少个唯一 ID，方便你核对
print(f"Total unique IDs found in Excel: {len(id_age_dict)}")

# 3. 遍历文件夹并改名
for folder_name in os.listdir(skullstrip_path):
    folder_path = os.path.join(skullstrip_path, folder_name)

    if os.path.isdir(folder_path):
        # 提取 ID 逻辑
        if folder_name.isdigit() and len(folder_name) == 10:
            id_part = folder_name
        elif folder_name.startswith("N") and "_" in folder_name:
            id_part = folder_name
        else:
            continue

        if id_part in id_age_dict:
            age_val = id_age_dict[id_part]
            new_folder_name = f"{folder_name}_{age_val}mo"
            new_folder_path = os.path.join(skullstrip_path, new_folder_name)

            if folder_name.endswith(f"_{age_val}mo"):
                continue

            try:
                os.rename(folder_path, new_folder_path)
                print(f"Renamed: {folder_name} -> {new_folder_name}")
            except Exception as e:
                print(f"Error renaming {folder_name}: {e}")
        else:
            print(f"ID {id_part} not found in Excel.")