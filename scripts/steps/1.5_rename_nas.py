import posixpath
import re
import stat
import sys

try:
    import pandas as pd
    import paramiko
except ImportError:
    print("缺少依赖。请先安装：python -m pip install pandas openpyxl paramiko")
    sys.exit(1)


# =========================================================
# 配置
# =========================================================
EXCEL_PATH = r"D:\University\master\QC2026\2026\修正后\CBCP_subinfo.xlsx"

HOST = "10.15.49.7"
PORT = 22112
USERNAME = "linmo2025"
PASSWORD = r"E>vq2fgPr9"

ROOT = "/public_bme2/bme-zhanghan/linmo2025/2026/0506_CBCP/0_rawdata"

DRY_RUN = False   # True = 只预览；False = 真正改名
# =========================================================


def normalize_id(value):
    """
    将 Excel / 文件夹中的 ID 统一成用于匹配的形式。
    兼容两类 ID：

    1) 纯数字 ID：
       '0104020003' -> '104020003'
       104020003    -> '104020003'

    2) 字母+数字 ID：
       'N1024_0301020447'   -> 'N10240301020447'
       'n1024-0301020447'   -> 'N10240301020447'
       'N1024 0301020447'   -> 'N10240301020447'

    规则：
    - 若 ID 中含字母：保留字母和数字，去掉分隔符，统一转大写
    - 若 ID 中不含字母：仅保留数字，并去掉前导 0（兼容 Excel 吃掉前导 0）
    """
    if value is None:
        return None

    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return None

    if re.search(r"[A-Za-z]", s):
        alnum = re.sub(r"[^A-Za-z0-9]", "", s).upper()
        return alnum if alnum else None

    digits = re.sub(r"\D", "", s)
    if digits == "":
        return None

    digits_no_leading_zero = digits.lstrip("0")
    return digits_no_leading_zero if digits_no_leading_zero != "" else "0"


def clean_folder_id(folder_name):
    """
    从文件夹名提取原始 ID 部分，去掉末尾已有的 _xxmo 后缀。
    这样可以防止重复跑时变成 ID_1mo_1mo。
    """
    s = folder_name.strip()
    s = re.sub(r"_(\d+(?:\.\d+)?)mo$", "", s, flags=re.IGNORECASE)
    return s


def normalize_age(age_value):
    """
    把 month 统一成用于命名的字符串：
    4 -> '4mo'
    4.0 -> '4mo'
    4.5 -> '4.5mo'
    '4月' -> '4mo'
    """
    if age_value is None:
        raise ValueError("age 为空")

    s = str(age_value).strip()
    if s == "" or s.lower() == "nan":
        raise ValueError("age 为空")

    m = re.search(r"\d+(?:\.\d+)?", s.lower())
    if not m:
        raise ValueError(f"无法解析 age/month: {age_value}")

    num = float(m.group(0))
    if num.is_integer():
        num_out = str(int(num))
    else:
        num_out = str(num).rstrip("0").rstrip(".")

    return f"{num_out}mo"


def load_id_age_map_from_all_sheets(excel_path):
    """
    读取 3 个 sheet。
    每个 sheet:
    - 第 1 列 = ID
    - 第 3 列 = month

    返回：
    - mapping: norm_id -> age_str
    - duplicate_conflicts: 同一个 norm_id 在多个 sheet 中出现且 month 不一致
    - parse_errors: Excel 中无法解析的行
    """
    workbook = pd.read_excel(excel_path, sheet_name=None, dtype=str)

    if not workbook:
        raise ValueError("Excel 没有 sheet。")

    mapping = {}
    duplicate_conflicts = []
    parse_errors = []

    for sheet_name, df in workbook.items():
        if df.empty:
            continue

        if df.shape[1] < 3:
            raise ValueError(f"sheet '{sheet_name}' 列数不足 3 列，无法读取第 1 列 ID 和第 3 列 month。")

        id_series = df.iloc[:, 0]
        month_series = df.iloc[:, 2]

        for i, (raw_id, raw_month) in enumerate(zip(id_series, month_series), start=2):
            norm_id = normalize_id(raw_id)
            if norm_id is None:
                continue

            try:
                age_str = normalize_age(raw_month)
            except Exception as e:
                parse_errors.append((sheet_name, i, raw_id, raw_month, str(e)))
                continue

            if norm_id in mapping:
                old_age = mapping[norm_id]
                if old_age != age_str:
                    duplicate_conflicts.append((sheet_name, i, raw_id, norm_id, old_age, age_str))
            else:
                mapping[norm_id] = age_str

    return mapping, duplicate_conflicts, parse_errors


def is_dir_attr(attr):
    return stat.S_ISDIR(attr.st_mode)


def main():
    try:
        id_age_map, duplicate_conflicts, parse_errors = load_id_age_map_from_all_sheets(EXCEL_PATH)
    except Exception as e:
        print(f"读取 Excel 失败：{e}")
        return

    transport = None
    sftp = None

    renamed = []
    already_ok = []
    not_found_age = []
    rename_failed = []

    try:
        transport = paramiko.Transport((HOST, PORT))
        transport.connect(username=USERNAME, password=PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        root_stat = sftp.stat(ROOT)
        if not stat.S_ISDIR(root_stat.st_mode):
            print(f"远端路径不是文件夹：{ROOT}")
            return

        folders = [attr for attr in sftp.listdir_attr(ROOT) if is_dir_attr(attr)]

        for attr in folders:
            old_name = attr.filename
            folder_id_raw = clean_folder_id(old_name)
            folder_id_norm = normalize_id(folder_id_raw)

            if folder_id_norm is None or folder_id_norm not in id_age_map:
                not_found_age.append(old_name)
                continue

            age_str = id_age_map[folder_id_norm]
            new_name = f"{folder_id_raw}_{age_str}"

            # 已经是目标名字，跳过
            if old_name == new_name:
                already_ok.append(old_name)
                continue

            old_path = posixpath.join(ROOT, old_name)
            new_path = posixpath.join(ROOT, new_name)

            # 若目标目录已存在且不是自己，避免覆盖
            try:
                sftp.stat(new_path)
                rename_failed.append((old_name, new_name, "目标文件夹已存在"))
                continue
            except IOError:
                pass

            try:
                if not DRY_RUN:
                    sftp.rename(old_path, new_path)
                renamed.append((old_name, new_name))
            except Exception as e:
                rename_failed.append((old_name, new_name, str(e)))

        print("=" * 80)
        print("处理完成")
        print("=" * 80)
        print(f"Excel: {EXCEL_PATH}")
        print(f"远端目录: {ROOT}")
        print(f"模式: {'预览(DRY_RUN=True)' if DRY_RUN else '实际改名(DRY_RUN=False)'}")
        print(f"Excel 可用映射数: {len(id_age_map)}")
        print(f"远端文件夹数: {len(folders)}")
        print()

        print(f"[1] 成功改名/将改名: {len(renamed)}")
        print()

        print(f"[2] 已经符合要求，无需处理: {len(already_ok)}")
        print()

        print(f"[3] 没找到 age 的 ID/文件夹: {len(not_found_age)}")
        for name in not_found_age:
            print(f"  {name}")
        print()

        print(f"[4] 重命名失败: {len(rename_failed)}")
        for old_name, new_name, reason in rename_failed:
            print(f"  {old_name}  ->  {new_name}   [失败原因: {reason}]")
        print()

        print(f"[5] Excel 中同一规范化 ID 的 month 冲突: {len(duplicate_conflicts)}")
        for sheet_name, row_no, raw_id, norm_id, old_age, new_age in duplicate_conflicts:
            print(
                f"  sheet={sheet_name}, 行={row_no}, raw_id={raw_id}, norm_id={norm_id}, "
                f"已有={old_age}, 新值={new_age}"
            )
        print()

        print(f"[6] Excel 中 month 解析失败: {len(parse_errors)}")
        for sheet_name, row_no, raw_id, raw_month, err in parse_errors:
            print(
                f"  sheet={sheet_name}, 行={row_no}, ID={raw_id}, month={raw_month}, 错误={err}"
            )
        print()

        print("结束。")

    finally:
        if sftp is not None:
            sftp.close()
        if transport is not None:
            transport.close()


if __name__ == "__main__":
    main()