from pathlib import Path
import shutil
import re
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

import pandas as pd


# =========================
# 配置区
# =========================

BASE_DIR = Path(r"D:\University\master\QC2026\2026")

DATASET = "CBCP"   # 可选: "CBCP" / "ASD" / "SHCH"

if DATASET == "CBCP":
    EXCEL_PATH = BASE_DIR / "CBCP_QC.xlsx"
    DATA_ROOT = BASE_DIR / r"0604_CBCP\3_skullstrip"
    QUESTIONABLE_DIR = BASE_DIR / r"0604_CBCP\questionable"

elif DATASET == "ASD":
    EXCEL_PATH = BASE_DIR / "ASD_QC.xlsx"
    DATA_ROOT = BASE_DIR / r"ASD\3_skullstrip"          # 跑 ASD 时按实际路径改这里
    QUESTIONABLE_DIR = BASE_DIR / r"ASD\questionable"   # 跑 ASD 时按实际路径改这里

elif DATASET == "SHCH":
    EXCEL_PATH = BASE_DIR / r"0413_SHCH\info.xlsx"
    DATA_ROOT = BASE_DIR / r"0413_SHCH\3_skullstrip"
    QUESTIONABLE_DIR = BASE_DIR / r"0413_SHCH\questionable"

else:
    raise ValueError(f"未知 DATASET: {DATASET}")

# True = 只打印不执行；False = 真正删除/移动
DRY_RUN = False

# questionable 下已存在同名目标时：True=跳过；False=记失败
SKIP_IF_QUESTIONABLE_EXISTS = True


# =========================
# 读取 Excel：兼容坏样式
# =========================

def read_excel_ignore_broken_styles(excel_path: Path, **kwargs):
    """
    读取样式损坏的 xlsx。
    如果 openpyxl 因 styles.xml 损坏而报错，就临时去掉 styles.xml 再读取。
    不修改原 Excel。
    """
    try:
        return pd.read_excel(excel_path, dtype=str, **kwargs)
    except Exception as e:
        msg = str(e)

        style_error_keywords = [
            "openpyxl.styles.fills.Fill",
            "expected <class",
            "Fill",
        ]

        if not any(k in msg for k in style_error_keywords):
            raise

        print("[WARN] Excel 样式损坏，正在临时去除 styles.xml 后读取数据。")

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


# =========================
# 基础工具
# =========================

def normalize_status(x):
    if pd.isna(x):
        return ""

    s = str(x).strip().lower()

    if s == "":
        return ""

    if "pass" in s:
        return "pass"

    if "fail" in s:
        return "fail"

    if "question" in s or "ques" in s:
        return "questionable"

    return s


def strip_age_suffix(name: str) -> str:
    """
    去掉末尾月龄：
    0101010265_13mo -> 0101010265
    N1062_0301010602_0mo -> N1062_0301010602
    sub0103010223_118mo -> sub0103010223
    """
    s = str(name).strip()
    s = re.sub(r"[_\-\s]*\d+(?:\.\d+)?\s*mo$", "", s, flags=re.IGNORECASE)
    return s


def normalize_key(value):
    """
    用于跨 Excel / 文件夹匹配 ID。

    纯数字：
      0101010265 -> 101010265
      0401010003 -> 401010003

    N 类：
      N1062_0301010602 -> N10620301010602

    SHCH 类：
      sub0103010223 -> SUB0103010223
    """
    if value is None or pd.isna(value):
        return None

    s = strip_age_suffix(str(value).strip())

    if s == "" or s.lower() == "nan":
        return None

    if re.search(r"[A-Za-z]", s):
        key = re.sub(r"[^A-Za-z0-9]", "", s).upper()
        return key if key else None

    digits = re.sub(r"\D", "", s)
    if not digits:
        return None

    digits = digits.lstrip("0")
    return digits if digits else "0"


def normalize_sheet_name(name):
    s = str(name).strip().lower()
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", s)
    return s


def extract_subject_id(folder_name: str):
    """
    SHCH:
      sub0103010223_118mo -> sub0103010223

    CBCP/ASD:
      0101010265_13mo -> 0101010265
      N1062_0301010602_0mo -> N1062_0301010602
    """
    name = strip_age_suffix(folder_name)

    m = re.match(r"^(sub[^_\\/]*)", name, flags=re.IGNORECASE)
    if m:
        return m.group(1)

    return name


def classify_cbcp_site(folder_id_raw: str):
    """
    CBCP 来源判断：
      Nxxxx_yyyy -> xm
      010...     -> stu / skd
      040...     -> cz
    """
    s = strip_age_suffix(folder_id_raw).strip()

    if re.match(r"^N\d+", s, flags=re.IGNORECASE):
        return "xm"

    if re.search(r"[A-Za-z]", s):
        return None

    digits = re.sub(r"\D", "", s)

    if digits.startswith("01"):
        return "stu"

    if digits.startswith("04"):
        return "cz"

    return None


def get_cbcp_match_keys(folder_id_raw: str, site_key: str):
    """
    CBCP 匹配 key。
    xm 的 Nxxxx_yyyy 额外尝试 yyyy。
    """
    keys = []

    def add(x):
        k = normalize_key(x)
        if k is not None and k not in keys:
            keys.append(k)

    folder_id_raw = strip_age_suffix(folder_id_raw)
    add(folder_id_raw)

    if site_key == "xm" and "_" in folder_id_raw:
        add(folder_id_raw.split("_", 1)[1])

    return keys


def safe_delete_dir(path: Path):
    if not DRY_RUN:
        shutil.rmtree(path)


def safe_move_dir(src: Path, dst: Path):
    if not DRY_RUN:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))


# =========================
# Excel 列识别
# =========================

def normalize_colname(col):
    s = str(col).strip().lower()
    s = re.sub(r"[\s_\-]+", "", s)
    return s


def find_column(df, aliases, contains_aliases=None):
    contains_aliases = contains_aliases or []
    norm_map = {col: normalize_colname(col) for col in df.columns}

    for col, norm in norm_map.items():
        if norm in aliases:
            return col

    for col, norm in norm_map.items():
        for x in contains_aliases:
            if x in norm:
                return col

    return None


def detect_id_t1_t2_columns(df, context_name=""):
    """
    自动识别 ID / T1w / T2w。
    当前脚本只依据 T1w 操作，所以 T2w 找不到也不报错。
    """
    id_col = find_column(
        df,
        aliases={"subjectid", "subnum", "subid", "subject", "id", "caseid", "subname"},
        contains_aliases=["subjectid", "subnum", "subid", "caseid", "subname"]
    )

    t1_col = find_column(
        df,
        aliases={"t1w", "t1", "t1qc", "t1status"},
        contains_aliases=["t1w", "t1qc", "t1status"]
    )

    t2_col = find_column(
        df,
        aliases={"t2w", "t2", "t2qc", "t2status"},
        contains_aliases=["t2w", "t2qc", "t2status"]
    )

    if id_col is None or t1_col is None:
        raise ValueError(
            f"{context_name} 未能识别 ID列/T1w列。\n"
            f"当前列名: {list(df.columns)}\n"
            "需要至少包含类似 SubjectID/subnum/id 和 T1w/T1/T1QC。"
        )

    return id_col, t1_col, t2_col


# =========================
# 单 sheet：SHCH / ASD
# =========================

def load_single_sheet_status_table(excel_path: Path):
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel 不存在: {excel_path}")

    df = read_excel_ignore_broken_styles(excel_path)
    id_col, t1_col, t2_col = detect_id_t1_t2_columns(df, context_name=str(excel_path))

    info_dict = {}

    for _, row in df.iterrows():
        raw_id = row[id_col]

        if pd.isna(raw_id):
            continue

        sid = str(raw_id).strip()
        if not sid:
            continue

        key = normalize_key(sid)

        if key is None:
            continue

        if key not in info_dict:
            t1_raw = row[t1_col]
            t2_raw = row[t2_col] if t2_col is not None else ""

            info_dict[key] = {
                "raw_id": sid,
                "T1w": t1_raw,
                "T2w": t2_raw,
                "T1w_norm": normalize_status(t1_raw),
                "T2w_norm": normalize_status(t2_raw),
                "source_sheet": None,
            }

    return info_dict


# =========================
# CBCP 多 sheet
# =========================

CBCP_SITE_SHEET_ALIASES = {
    "xm": [
        "xm_Allqc",
        "xmh_Allqc",
        "site2_xmh",
        "site2xmh",
    ],
    "stu": [
        "skd_Allqc",
        "stu_Allqc",
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
    available = list(all_sheets.keys())
    norm_to_real = {normalize_sheet_name(x): x for x in available}

    for alias in CBCP_SITE_SHEET_ALIASES[site_key]:
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


def load_cbcp_status_tables(excel_path: Path):
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel 不存在: {excel_path}")

    all_sheets = read_excel_ignore_broken_styles(excel_path, sheet_name=None)

    site_maps = {}

    for site_key in ["xm", "stu", "cz"]:
        sheet_name = find_sheet_for_site(all_sheets, site_key)

        if sheet_name is None:
            site_maps[site_key] = {}
            continue

        df = all_sheets[sheet_name]
        id_col, t1_col, t2_col = detect_id_t1_t2_columns(
            df,
            context_name=f"{site_key}:{sheet_name}"
        )

        mapping = {}

        for _, row in df.iterrows():
            raw_id = row[id_col]

            if pd.isna(raw_id):
                continue

            raw_id = str(raw_id).strip()
            if not raw_id:
                continue

            keys = []

            def add_key(x):
                k = normalize_key(x)
                if k is not None and k not in keys:
                    keys.append(k)

            add_key(raw_id)

            if site_key == "xm" and "_" in raw_id:
                add_key(raw_id.split("_", 1)[1])

            t1_raw = row[t1_col]
            t2_raw = row[t2_col] if t2_col is not None else ""

            item = {
                "raw_id": raw_id,
                "T1w": t1_raw,
                "T2w": t2_raw,
                "T1w_norm": normalize_status(t1_raw),
                "T2w_norm": normalize_status(t2_raw),
                "source_sheet": sheet_name,
            }

            for k in keys:
                if k not in mapping:
                    mapping[k] = item

        site_maps[site_key] = mapping

    return site_maps


# =========================
# 文件夹收集
# =========================

def is_cbcp_id_folder(folder_name: str):
    sid = extract_subject_id(folder_name)
    return classify_cbcp_site(sid) is not None


def collect_subject_folders(data_root: Path, cbcp_mode: bool):
    """
    SHCH / ASD：
      默认扫描 DATA_ROOT 下一层。

    CBCP：
      支持两种结构：
      1. DATA_ROOT/010... 或 DATA_ROOT/N...
      2. DATA_ROOT/Site1_STU/010... 或 DATA_ROOT/Site2_XMH/N...
    """
    folders = []

    for p in sorted(data_root.iterdir()):
        if not p.is_dir():
            continue

        if p.name.lower() == "questionable":
            continue

        if not cbcp_mode:
            folders.append(p)
            continue

        if is_cbcp_id_folder(p.name):
            folders.append(p)
            continue

        for q in sorted(p.iterdir()):
            if q.is_dir() and is_cbcp_id_folder(q.name):
                folders.append(q)

    return folders


def get_questionable_dst(folder: Path):
    """
    保留相对结构：
      DATA_ROOT/Site2_XMH/Nxxx -> QUESTIONABLE_DIR/Site2_XMH/Nxxx
      DATA_ROOT/Nxxx          -> QUESTIONABLE_DIR/Nxxx
    """
    rel = folder.relative_to(DATA_ROOT)
    return QUESTIONABLE_DIR / rel


# =========================
# 查状态
# =========================

def lookup_status_for_folder(folder_name: str, cbcp_mode: bool, single_map=None, site_maps=None):
    sid_raw = extract_subject_id(folder_name)

    if cbcp_mode:
        site_key = classify_cbcp_site(sid_raw)

        if site_key is None:
            return None, sid_raw, None, "无法根据ID判断CBCP来源"

        keys = get_cbcp_match_keys(sid_raw, site_key)

        for k in keys:
            if k in site_maps.get(site_key, {}):
                return site_maps[site_key][k], sid_raw, site_key, f"matched key={k}"

        return None, sid_raw, site_key, f"对应sheet未找到ID，尝试keys={keys}"

    key = normalize_key(sid_raw)

    if key in single_map:
        return single_map[key], sid_raw, None, f"matched key={key}"

    return None, sid_raw, None, f"Excel未找到ID，key={key}"


# =========================
# 主流程
# =========================

def main():
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel 不存在: {EXCEL_PATH}")

    if not DATA_ROOT.exists():
        raise FileNotFoundError(f"数据目录不存在: {DATA_ROOT}")

    cbcp_mode = DATASET == "CBCP"

    if cbcp_mode:
        site_maps = load_cbcp_status_tables(EXCEL_PATH)
        single_map = None
    else:
        single_map = load_single_sheet_status_table(EXCEL_PATH)
        site_maps = None

    folders = collect_subject_folders(DATA_ROOT, cbcp_mode=cbcp_mode)

    total_subject_folders = 0
    matched_count = 0
    unmatched_count = 0

    t1w_pass_count = 0
    t1w_fail_count = 0
    t1w_questionable_count = 0
    t1w_unknown_count = 0

    skipped_pass = []
    deleted_fail = []
    moved_questionable = []
    unmatched_folders = []
    unknown_status_folders = []
    questionable_exists_skipped = []
    op_failed = []

    fail_subject_ids = []

    for folder in folders:
        total_subject_folders += 1
        folder_name = folder.name

        item, sid, site_key, match_msg = lookup_status_for_folder(
            folder_name,
            cbcp_mode=cbcp_mode,
            single_map=single_map,
            site_maps=site_maps,
        )

        if item is None:
            unmatched_count += 1
            unmatched_folders.append({
                "folder": folder_name,
                "sid": sid,
                "site": site_key,
                "reason": match_msg,
            })
            continue

        matched_count += 1
        t1w = item["T1w_norm"]

        if t1w == "pass":
            t1w_pass_count += 1
            skipped_pass.append(folder_name)

        elif t1w == "fail":
            t1w_fail_count += 1
            deleted_fail.append(folder_name)
            fail_subject_ids.append(sid)

            try:
                safe_delete_dir(folder)
            except Exception as e:
                op_failed.append({
                    "folder": folder_name,
                    "action": "delete",
                    "reason": str(e),
                })

        elif t1w == "questionable":
            t1w_questionable_count += 1
            dst = get_questionable_dst(folder)

            if dst.exists():
                if SKIP_IF_QUESTIONABLE_EXISTS:
                    questionable_exists_skipped.append(folder_name)
                    continue
                else:
                    op_failed.append({
                        "folder": folder_name,
                        "action": "move",
                        "reason": f"目标已存在: {dst}",
                    })
                    continue

            try:
                moved_questionable.append(folder_name)
                safe_move_dir(folder, dst)
            except Exception as e:
                op_failed.append({
                    "folder": folder_name,
                    "action": "move",
                    "reason": str(e),
                })

        else:
            t1w_unknown_count += 1
            unknown_status_folders.append({
                "folder": folder_name,
                "sid": sid,
                "site": site_key,
                "t1w": item["T1w"],
            })

    fail_subject_ids = sorted(set(fail_subject_ids))

    print("=" * 80)
    print("运行完成")
    print("=" * 80)
    print(f"DATASET: {DATASET}")
    print(f"Excel: {EXCEL_PATH}")
    print(f"数据目录: {DATA_ROOT}")
    print(f"questionable目录: {QUESTIONABLE_DIR}")
    print(f"DRY_RUN: {DRY_RUN}")
    print("-" * 80)
    print(f"3_skullstrip 下数据文件夹总数: {total_subject_folders}")
    print(f"成功匹配 Excel 的文件夹数: {matched_count}")
    print(f"未匹配 Excel 的文件夹数: {unmatched_count}")
    print("")
    print(f"T1w = pass: {t1w_pass_count}（跳过不动）")
    print(f"T1w = fail: {t1w_fail_count}（删除）")
    print(f"T1w = questionable: {t1w_questionable_count}（剪切到 questionable）")
    print(f"T1w = 其他/未知: {t1w_unknown_count}（未操作）")
    print(f"操作失败数: {len(op_failed)}")
    print("=" * 80)

    print("\n[fail SubjectID]")
    if fail_subject_ids:
        for sid in fail_subject_ids:
            print(f"  {sid}")
    else:
        print("  无")

    print("\n[未匹配 Excel 的文件夹]")
    if unmatched_folders:
        for x in unmatched_folders:
            site_text = f"site={x['site']} | " if cbcp_mode else ""
            print(f"  {site_text}{x['folder']} | sid={x['sid']} | {x['reason']}")
    else:
        print("  无")

    print("\n[T1w 状态未知、未处理的文件夹]")
    if unknown_status_folders:
        for x in unknown_status_folders:
            site_text = f"site={x['site']} | " if cbcp_mode else ""
            print(f"  {site_text}{x['folder']} | sid={x['sid']} | T1w={x['t1w']}")
    else:
        print("  无")

    print("\n[questionable 中已存在同名而跳过]")
    if questionable_exists_skipped:
        for x in questionable_exists_skipped:
            print(f"  {x}")
    else:
        print("  无")

    print("\n[删除/剪切操作失败]")
    if op_failed:
        for x in op_failed:
            print(f"  {x['action']} | {x['folder']} | {x['reason']}")
    else:
        print("  无")

    print("\n操作清单摘要：")
    print(f"  pass 跳过: {len(skipped_pass)}")
    print(f"  fail 删除: {len(deleted_fail)}")
    print(f"  questionable 剪切: {len(moved_questionable)}")
    print(f"  未匹配: {len(unmatched_folders)}")
    print(f"  未知状态: {len(unknown_status_folders)}")
    print(f"  操作失败: {len(op_failed)}")
    print(f"  DRY_RUN: {DRY_RUN}")


if __name__ == "__main__":
    main()