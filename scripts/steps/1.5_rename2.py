from pathlib import Path
import re
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from contextlib import redirect_stdout
from io import StringIO

try:
    import pandas as pd
except ImportError:
    print("缺少 pandas。请先安装：python -m pip install pandas openpyxl")
    sys.exit(1)

# 本脚本用于修改数据文件夹名，使月龄体现在文件夹命名中。
# ASD_QC：单 sheet 逻辑
# CBCP_QC：多 sheet 逻辑，根据文件夹 ID 判断 site 后去对应 Allqc sheet 找 age
#
# 重要更新：
# 每次运行都会先把文件夹名末尾已有的 _xxmo 剥离，再根据最新 Excel 重新生成 _xxmo。
# 例如：
# N1033_0301030197_21mo，如果 Excel 更新为 22mo，则改成 N1033_0301030197_22mo
# 0101010265_13mo，如果 Excel 更新为 14mo，则改成 0101010265_14mo

# ========= 可修改配置 =========

EXCEL_PATH = r"D:\University\master\QC2026\2026\CBCP_QC.xlsx"
# EXCEL_PATH = r"D:\University\master\QC2026\2026\ASD_QC.xlsx"

ROOT_DIR = r"D:\University\master\QC2026\2026\0622_CBCP\0_rawdata"

# 安全锁：
# True  = 只预览，不真正改名
# False = 真正改名
DRY_RUN = False

# 如果目标文件夹已存在：
# True  = 跳过并记为失败
# False = 也会记为失败；这里不做覆盖、不合并，避免误伤
SKIP_IF_TARGET_EXISTS = True

# 是否强制刷新已有 _xxmo 后缀。
# 建议保持 True。
REFRESH_EXISTING_AGE_SUFFIX = True

# ============================


def read_excel_ignore_broken_styles(excel_path, **kwargs):
    """
    读取样式损坏的 xlsx。
    原理：复制 xlsx 到临时文件时跳过 xl/styles.xml，只保留数据内容。
    不修改原 Excel，不转 csv。
    """
    try:
        return pd.read_excel(excel_path, dtype=str, **kwargs)
    except Exception as e:
        msg = str(e)
        if "openpyxl.styles.fills.Fill" not in msg and "expected <class" not in msg:
            raise

        print("[WARN] openpyxl 读取 Excel 样式失败，尝试临时去除 styles.xml 后读取数据。")
        excel_path = Path(excel_path)

        with tempfile.TemporaryDirectory() as td:
            fixed_path = Path(td) / (excel_path.stem + "_no_styles.xlsx")

            with ZipFile(excel_path, "r") as zin:
                with ZipFile(fixed_path, "w", ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        if item.filename == "xl/styles.xml":
                            continue
                        zout.writestr(item, zin.read(item.filename))

            return pd.read_excel(fixed_path, dtype=str, **kwargs)


def has_age_suffix(name):
    """
    判断文件夹名末尾是否已有 _xxmo / -xxmo / 空格xxmo。
    """
    s = str(name).strip()
    return re.search(r"[_\-\s]*\d+(?:\.\d+)?\s*mo$", s, flags=re.IGNORECASE) is not None


def clean_folder_id(folder_name):
    """
    从文件夹名提取原始 ID 部分。

    兼容：
    - 0104020003
    - 0104020003_4mo
    - N1024_0301020447
    - N1024_0301020447_4mo

    注意：
    N1024_0301020447 这种不能按第一个下划线切。
    这里只去掉末尾的 _xxmo / -xxmo / 空格xxmo。
    """
    s = str(folder_name).strip()
    s = re.sub(r"[_\-\s]*\d+(?:\.\d+)?\s*mo$", "", s, flags=re.IGNORECASE)
    return s.strip()


def normalize_id(value):
    """
    将 Excel / 文件夹中的 ID 统一成用于匹配的形式。

    1) 纯数字 ID：
       '0104020003' -> '104020003'
       104020003    -> '104020003'

    2) 字母+数字 ID：
       'N1024_0301020447' -> 'N10240301020447'
       'n1024-0301020447' -> 'N10240301020447'

    规则：
    - 若 ID 中含字母：保留字母和数字，去掉分隔符，统一转大写
    - 若 ID 中不含字母：仅保留数字，并去掉前导 0
    """
    if value is None:
        return None

    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return None

    s = clean_folder_id(s)

    if re.search(r"[A-Za-z]", s):
        alnum = re.sub(r"[^A-Za-z0-9]", "", s).upper()
        return alnum if alnum else None

    digits = re.sub(r"\D", "", s)
    if digits == "":
        return None

    digits_no_leading_zero = digits.lstrip("0")
    return digits_no_leading_zero if digits_no_leading_zero != "" else "0"


def normalize_age(age_value):
    """
    把 age 统一成用于命名的字符串，比如:
    4 -> '4mo'
    4.0 -> '4mo'
    '4' -> '4mo'
    '4mo' -> '4mo'
    '4 月' / '4月' / '4 months' -> '4mo'
    """
    if age_value is None:
        raise ValueError("age 为空")

    s = str(age_value).strip()
    if s == "" or s.lower() == "nan":
        raise ValueError("age 为空")

    s_lower = s.lower()

    m = re.search(r"\d+(\.\d+)?", s_lower)
    if not m:
        raise ValueError(f"无法解析 age: {age_value}")

    num_str = m.group(0)
    num = float(num_str)

    if num.is_integer():
        num_out = str(int(num))
    else:
        num_out = str(num).rstrip("0").rstrip(".")

    return f"{num_out}mo"


def normalize_colname(col):
    s = str(col).strip().lower()
    s = re.sub(r"[\s_\-]+", "", s)
    return s


def detect_id_age_columns(df, context_name=""):
    """
    自动识别 ID 列和 age 列。
    """
    if df.empty:
        raise ValueError(f"{context_name} 为空，没法读取 ID-age 对照。")

    cols = list(df.columns)
    norm_map = {col: normalize_colname(col) for col in cols}

    id_col = None
    age_col = None

    id_aliases = {
        "subnum", "subjectid", "subject", "id", "caseid", "subid", "subname"
    }
    age_aliases = {
        "month", "months", "age", "mo", "monthold", "monthsold", "月龄"
    }

    for col, norm in norm_map.items():
        if id_col is None and norm in id_aliases:
            id_col = col
        if age_col is None and norm in age_aliases:
            age_col = col

    if id_col is None:
        for col, norm in norm_map.items():
            if (
                "subnum" in norm
                or "subjectid" in norm
                or norm == "id"
                or "caseid" in norm
                or "subid" in norm
                or "subname" in norm
            ):
                id_col = col
                break

    if age_col is None:
        for col, norm in norm_map.items():
            if (
                "month" in norm
                or norm == "age"
                or norm == "mo"
                or "月龄" in norm
            ):
                age_col = col
                break

    if id_col is None or age_col is None:
        raise ValueError(
            f"未能自动识别 {context_name} 中的 ID 列和年龄列。\n"
            f"当前列名为: {cols}\n"
            "请确认表头中包含类似：sub_num / subnum / ID / subjectID，以及 month / age 这类字段。"
        )

    return id_col, age_col


def load_id_age_map_from_df(df, context_name="", site_key=None):
    """
    从 dataframe 读取 ID-age 映射。
    site_key='xm' 时，额外支持 Nxxxx_yyyy 和 yyyy 两种形式匹配。

    健壮性：
    - ID 为空：跳过
    - age 为空 / nan / 无法解析：不报错中断，记录 invalid_age_rows 后跳过该行
    - 重复 ID：保留第一次，不覆盖
    """
    id_col, age_col = detect_id_age_columns(df, context_name=context_name)

    mapping = {}
    duplicate_ids = []
    invalid_age_rows = []

    for idx, row in df.iterrows():
        raw_id = row[id_col]
        raw_age = row[age_col]

        norm_id = normalize_id(raw_id)
        if norm_id is None:
            continue

        try:
            age_str = normalize_age(raw_age)
        except Exception as e:
            invalid_age_rows.append({
                "context": context_name,
                "excel_row": idx + 2,
                "raw_id": str(raw_id),
                "norm_id": norm_id,
                "raw_age": str(raw_age),
                "reason": str(e),
            })
            continue

        if norm_id in mapping:
            duplicate_ids.append(str(raw_id))
        else:
            mapping[norm_id] = age_str

        # xm/XMH 的 ID 可能有 Nxxxx_yyyy，也可能表里或文件夹里只出现 yyyy。
        # 这里只额外加一个匹配键，不删除、不修改原始 ID。
        if site_key == "xm":
            raw_id_str = str(raw_id).strip()
            if "_" in raw_id_str:
                suffix_id = raw_id_str.split("_", 1)[1]
                suffix_norm = normalize_id(suffix_id)
                if suffix_norm is not None and suffix_norm not in mapping:
                    mapping[suffix_norm] = age_str

    return mapping, duplicate_ids, invalid_age_rows, id_col, age_col


def is_cbcp_excel(excel_path):
    return "cbcp" in Path(excel_path).name.lower()


def normalize_sheet_name(name):
    s = str(name).strip().lower()
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", s)
    return s


CBCP_SITE_SHEET_ALIASES = {
    "xm": [
        "xm_Allqc",
        "xmh_Allqc",
        "site2_xmh",
        "site2xmh",
    ],
    "stu": [
        "stu_Allqc",
        "skd_Allqc",
        "site1_stu",
        "site1stu",
    ],
    "cz": [
        "cz_Allqc",
        "czh_Allqc",
        "site3_czh",
        "site3czh",
    ],
}


def find_sheet_for_site(all_sheets, site_key):
    """
    在 CBCP_QC 的多 sheet 里，为某个 site 找对应 Allqc sheet。
    """
    available = list(all_sheets.keys())
    norm_to_real = {normalize_sheet_name(x): x for x in available}

    aliases = CBCP_SITE_SHEET_ALIASES[site_key]

    for alias in aliases:
        norm_alias = normalize_sheet_name(alias)
        if norm_alias in norm_to_real:
            return norm_to_real[norm_alias]

    for sheet_name in available:
        ns = normalize_sheet_name(sheet_name)
        if site_key == "xm":
            if "xm" in ns and "allqc" in ns:
                return sheet_name
        elif site_key == "stu":
            if ("stu" in ns or "skd" in ns) and "allqc" in ns:
                return sheet_name
        elif site_key == "cz":
            if ("cz" in ns or "czh" in ns) and "allqc" in ns:
                return sheet_name

    return None


def load_asd_id_age_map(excel_path):
    """
    ASD_QC：单表逻辑。
    """
    df = read_excel_ignore_broken_styles(excel_path)
    mapping, duplicate_ids, invalid_age_rows, id_col, age_col = load_id_age_map_from_df(
        df,
        context_name="ASD_QC",
        site_key=None
    )

    return mapping, duplicate_ids, invalid_age_rows, id_col, age_col


def load_cbcp_id_age_maps(excel_path):
    """
    CBCP_QC：多 sheet 逻辑。
    根据 site 分别读取 xm_Allqc / skd_Allqc / cz_Allqc。
    """
    all_sheets = read_excel_ignore_broken_styles(excel_path, sheet_name=None)

    site_maps = {}
    site_info = {}
    all_duplicate_ids = []
    all_invalid_age_rows = []

    for site_key in ["xm", "stu", "cz"]:
        sheet_name = find_sheet_for_site(all_sheets, site_key)

        if sheet_name is None:
            site_maps[site_key] = {}
            site_info[site_key] = {
                "sheet": None,
                "id_col": None,
                "age_col": None,
                "count": 0,
                "invalid_age_count": 0,
            }
            continue

        df = all_sheets[sheet_name]

        mapping, duplicate_ids, invalid_age_rows, id_col, age_col = load_id_age_map_from_df(
            df,
            context_name=f"CBCP {site_key} sheet={sheet_name}",
            site_key=site_key
        )

        site_maps[site_key] = mapping
        site_info[site_key] = {
            "sheet": sheet_name,
            "id_col": id_col,
            "age_col": age_col,
            "count": len(mapping),
            "invalid_age_count": len(invalid_age_rows),
        }

        all_duplicate_ids.extend(duplicate_ids)
        all_invalid_age_rows.extend(invalid_age_rows)

    return site_maps, all_duplicate_ids, all_invalid_age_rows, site_info


def classify_cbcp_site(folder_id_raw):
    """
    根据文件夹 ID 判断 CBCP site。

    Nxxxx_yyyy       -> xm
    010...           -> stu
    040...           -> cz
    """
    s = clean_folder_id(folder_id_raw).strip()

    if re.match(r"^N\d+[_\- ]?\d+", s, flags=re.IGNORECASE):
        return "xm"

    if re.search(r"[A-Za-z]", s):
        return None

    digits = re.sub(r"\D", "", s)

    if digits.startswith("04"):
        return "cz"

    if digits.startswith("01"):
        return "stu"

    return None


def get_cbcp_match_keys(folder_id_raw, site_key):
    """
    生成 CBCP 文件夹用于匹配 Excel 的 key。
    """
    keys = []

    def add(v):
        nv = normalize_id(v)
        if nv is not None and nv not in keys:
            keys.append(nv)

    folder_id_raw = clean_folder_id(folder_id_raw)

    add(folder_id_raw)

    if site_key == "xm" and "_" in folder_id_raw:
        add(folder_id_raw.split("_", 1)[1])

    return keys


def collect_target_folders(root_dir, cbcp_mode):
    """
    收集真正要加/刷新月龄的 ID 文件夹。

    ASD：
    - 扫描 ROOT_DIR 下一级文件夹。

    CBCP：
    - 如果 ROOT_DIR 下直接就是 ID 文件夹，则收集。
    - 如果 ROOT_DIR 下是 Site1_STU / Site2_XMH / Site3_CZH 这种容器目录，
      则继续扫描它们下一层 ID 文件夹。
    """
    root_dir = Path(root_dir)
    folders = []

    if not cbcp_mode:
        return [p for p in root_dir.iterdir() if p.is_dir()]

    for p in root_dir.iterdir():
        if not p.is_dir():
            continue

        p_id = clean_folder_id(p.name)
        p_site = classify_cbcp_site(p_id)

        if p_site is not None:
            folders.append(p)
            continue

        try:
            for q in p.iterdir():
                if not q.is_dir():
                    continue

                q_id = clean_folder_id(q.name)
                q_site = classify_cbcp_site(q_id)

                if q_site is not None:
                    folders.append(q)
        except PermissionError:
            print(f"[WARN] 无权限访问目录，跳过：{p}")

    return folders


def find_age_for_folder_asd(folder_id_raw, id_age_map):
    folder_id_norm = normalize_id(folder_id_raw)

    if folder_id_norm is None:
        return None, "ID 解析失败"

    if folder_id_norm not in id_age_map:
        return None, "ASD_QC 中未匹配到 ID"

    return id_age_map[folder_id_norm], "matched"


def find_age_for_folder_cbcp(folder_id_raw, site_maps):
    site_key = classify_cbcp_site(folder_id_raw)

    if site_key is None:
        return None, None, "无法根据 ID 判断 CBCP site"

    if site_key not in site_maps or not site_maps[site_key]:
        return None, site_key, f"site={site_key} 对应 sheet 未加载或映射为空"

    keys = get_cbcp_match_keys(folder_id_raw, site_key)

    for k in keys:
        if k in site_maps[site_key]:
            return site_maps[site_key][k], site_key, f"matched by key={k}"

    return None, site_key, f"在 site={site_key} 对应 sheet 中未匹配到 ID，尝试 keys={keys}"


def main():
    excel_path = Path(EXCEL_PATH)
    root_dir = Path(ROOT_DIR)

    if not excel_path.exists():
        print(f"Excel 不存在：{excel_path}")
        return

    if not root_dir.exists():
        print(f"目录不存在：{root_dir}")
        return

    cbcp_mode = is_cbcp_excel(excel_path)

    try:
        with redirect_stdout(StringIO()):
            if cbcp_mode:
                site_maps, duplicate_ids, invalid_age_rows, site_info = load_cbcp_id_age_maps(excel_path)
                id_age_map = None
            else:
                id_age_map, duplicate_ids, invalid_age_rows, id_col, age_col = load_asd_id_age_map(excel_path)
                site_maps = None
                site_info = None
    except Exception as e:
        print(f"读取 Excel 失败：{e}")
        return

    invalid_age_lookup = {}

    for item in invalid_age_rows:
        raw_id = str(item.get("raw_id", "")).strip()
        norm_id = item.get("norm_id")
        excel_row = item.get("excel_row")
        raw_age = item.get("raw_age")
        reason = item.get("reason")

        keys = []

        if norm_id:
            keys.append(str(norm_id))

        raw_norm = normalize_id(raw_id)
        if raw_norm:
            keys.append(raw_norm)

        if "_" in raw_id:
            suffix = raw_id.split("_", 1)[1]
            suffix_norm = normalize_id(suffix)
            if suffix_norm:
                keys.append(suffix_norm)

        msg = f"Excel中有该ID但age为空/无法解析：Excel行={excel_row}, age={raw_age}, 原因={reason}"

        for k in keys:
            if k and k not in invalid_age_lookup:
                invalid_age_lookup[k] = msg

    folders = collect_target_folders(root_dir, cbcp_mode=cbcp_mode)

    matched_and_renamed = []
    failed = []
    rename_failed = []
    already_correct = []
    age_updated = []

    for folder in folders:
        old_name = folder.name

        # 关键：每次都先剥离旧 _xxmo，再用最新 Excel age 重新拼新名字
        folder_id_raw = clean_folder_id(old_name)
        old_had_age = has_age_suffix(old_name)

        if cbcp_mode:
            age_str, site_key, match_msg = find_age_for_folder_cbcp(folder_id_raw, site_maps)

            if age_str is None:
                try_keys = get_cbcp_match_keys(folder_id_raw, site_key) if site_key else [normalize_id(folder_id_raw)]
                for k in try_keys:
                    if k in invalid_age_lookup:
                        match_msg = invalid_age_lookup[k]
                        break
        else:
            age_str, match_msg = find_age_for_folder_asd(folder_id_raw, id_age_map)
            site_key = None

            if age_str is None:
                k = normalize_id(folder_id_raw)
                if k in invalid_age_lookup:
                    match_msg = invalid_age_lookup[k]

        if age_str is None:
            failed.append({
                "folder": old_name,
                "folder_path": str(folder),
                "folder_id": folder_id_raw,
                "site": site_key,
                "reason": match_msg,
            })
            continue

        new_name = f"{folder_id_raw}_{age_str}"
        new_path = folder.parent / new_name

        if old_name == new_name:
            already_correct.append({
                "old_name": old_name,
                "new_name": new_name,
                "folder_path": str(folder),
                "site": site_key,
            })
            matched_and_renamed.append({
                "old_name": old_name,
                "new_name": new_name,
                "folder_path": str(folder),
                "site": site_key,
                "status": "已是最新目标名",
            })
            continue

        if new_path.exists():
            rename_failed.append({
                "old_name": old_name,
                "new_name": new_name,
                "folder_path": str(folder),
                "site": site_key,
                "reason": "目标文件夹已存在",
            })
            continue

        try:
            if not DRY_RUN:
                folder.rename(new_path)

            status = "预览成功" if DRY_RUN else "成功"

            if old_had_age:
                age_updated.append({
                    "old_name": old_name,
                    "new_name": new_name,
                    "folder_path": str(folder),
                    "site": site_key,
                })

            matched_and_renamed.append({
                "old_name": old_name,
                "new_name": new_name,
                "folder_path": str(folder),
                "site": site_key,
                "status": status,
            })

        except Exception as e:
            rename_failed.append({
                "old_name": old_name,
                "new_name": new_name,
                "folder_path": str(folder),
                "site": site_key,
                "reason": str(e),
            })

    total_folders = len(folders)
    success_count = len(matched_and_renamed)
    match_failed_count = len(failed)
    rename_failed_count = len(rename_failed)
    fail_count = match_failed_count + rename_failed_count
    changed_count = len([x for x in matched_and_renamed if x["old_name"] != x["new_name"]])
    already_correct_count = len(already_correct)
    age_updated_count = len(age_updated)

    print("=" * 80)
    print("处理完成")
    print("=" * 80)
    print(f"Excel: {excel_path}")
    print(f"数据目录: {root_dir}")
    print(f"模式: {'DRY_RUN 预览，不实际改名' if DRY_RUN else '实际改名'}")
    print(f"Excel类型: {'CBCP 多sheet' if cbcp_mode else 'ASD 单sheet'}")
    print(f"刷新已有月龄后缀: {REFRESH_EXISTING_AGE_SUFFIX}")
    print("-" * 80)
    print(f"一共扫描到文件夹: {total_folders}")
    print(f"成功处理: {success_count}")
    print(f"  - 已经是最新名字: {already_correct_count}")
    print(f"  - 需要改名/已改名: {changed_count}")
    print(f"  - 其中属于旧月龄刷新: {age_updated_count}")
    print(f"失败总数: {fail_count}")
    print(f"  - 匹配失败: {match_failed_count}")
    print(f"  - 重命名失败: {rename_failed_count}")
    print("=" * 80)

    print()
    print("[失败ID]")
    if fail_count == 0:
        print("无")
    else:
        for item in failed:
            site_text = f"site={item['site']} | " if cbcp_mode else ""
            print(
                f"{site_text}{item['folder_id']} | "
                f"folder={item['folder']} | "
                f"原因={item['reason']}"
            )

        for item in rename_failed:
            site_text = f"site={item['site']} | " if cbcp_mode else ""
            print(
                f"{site_text}{item['old_name']} -> {item['new_name']} | "
                f"原因={item['reason']}"
            )

    print()
    print("结束。")


if __name__ == "__main__":
    main()