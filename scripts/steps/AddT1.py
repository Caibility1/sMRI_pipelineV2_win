from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import numpy as np
    import nibabel as nib
except ImportError:
    np = None
    nib = None


# ============================================================
# 一键配置区
# ============================================================

LOCAL_MIX_ROOT = Path(r"D:\University\master\QC2026\2026\0528_mix2")

NAS231_USERNAME = "linm"
NAS231_PASSWORD = r"l9cG5/g{"

SRC_T1_NAME = "T1_acpc.nii.gz"
DST_FILE_NAME = "brain.nii.gz"

# True：只预演，不真正重命名/复制
# False：真正执行
DRY_RUN = True

OVERWRITE_EXISTING = False
PROCESS_ALREADY_RENAMED_DIRS = True

# 正确路径关系：
# 分割前输入池：
#   \\...\toBeSegmented\justT1
#   \\...\toBeSegmented\T1T2
#
# 已知 ID 分割结果：
#   \\...\toBeSegmented\20260521_results\20260521_results\justT1
#   \\...\toBeSegmented\20260521_results\20260521_results\T1T2
#
# 未知 ID 结果：
#   \\...\toBeSegmented\20260521_results\20260521_results\T1T2_v2
#
# 最终候选 = 分割前 T1T2 - 已知结果 T1T2

TOBESEG_ROOT = Path(r"\\10.19.136.231\002\CBCP\CBCP_MRI\toBeSegmented")
RESULTS_ROOT = TOBESEG_ROOT / "20260521_results" / "20260521_results"

PRE_INPUT_ROOTS = {
    "PRE_justT1": TOBESEG_ROOT / "justT1",
    "PRE_T1T2": TOBESEG_ROOT / "T1T2",
}

KNOWN_RESULT_ROOTS = {
    "justT1": RESULTS_ROOT / "justT1",
    "T1T2": RESULTS_ROOT / "T1T2",
}

PRE_TO_POST_BUCKET = {
    "PRE_justT1": "justT1",
    "PRE_T1T2": "T1T2",
}

# 只有 PRE_T1T2 的剩余项才作为 T1T2_v2 的候选
CANDIDATE_PRE_SOURCE_NAMES = {"PRE_T1T2"}

UNKNOWN_RESULT_ROOT = RESULTS_ROOT / "T1T2_v2"

MAX_T1_SEARCH_DEPTH = 6
MAX_POST_RESULT_SCAN_DEPTH = 6

USE_EXACT_AGE_FILTER = True

# T1 foreground 提取方法
USE_TOPK_VOLUME_MATCH = True
USE_FIXED_THRESHOLD_CANDIDATES = True
FIXED_T1_THRESHOLDS = (10.0, 20.0, 30.0, 40.0)

# 多候选时的严格自动接受阈值
ACCEPT_MIN_DICE = 0.985
ACCEPT_MIN_SCORE = 2100.0
ACCEPT_MIN_MARGIN = 25.0

# 如果某个月龄经过 “T1T2 - results/T1T2” 后只剩一个候选，则放宽接受
ACCEPT_UNIQUE_REMAINING_BY_AGE = True
UNIQUE_REMAINING_MIN_DICE = 0.90

TOP_K = 15

LOG_CSV = "lost_id_diff_t1t2_topk_match_report.csv"
UNMATCHED_TXT = "lost_id_unmatched_or_ambiguous.txt"
DIFF_CSV = "pre_post_pool_diff_report.csv"

CLEAR_ALL_NET_USE_AT_START = True


# ============================================================
# 数据结构
# ============================================================

@dataclass(frozen=True)
class SourceConfig:
    name: str
    share: str
    pre_root: Path


SOURCES: List[SourceConfig] = [
    SourceConfig(
        name="PRE_justT1",
        share=r"\\10.19.136.231\002",
        pre_root=PRE_INPUT_ROOTS["PRE_justT1"],
    ),
    SourceConfig(
        name="PRE_T1T2",
        share=r"\\10.19.136.231\002",
        pre_root=PRE_INPUT_ROOTS["PRE_T1T2"],
    ),
]


@dataclass
class MaskPair:
    dk: Path
    tissue: Path


@dataclass
class BinaryFeature:
    label: str
    path: str
    binary: Any
    shape: Tuple[int, int, int]
    count: int
    bbox_min: Tuple[int, int, int]
    bbox_max: Tuple[int, int, int]
    com: Tuple[float, float, float]
    profiles: Tuple[Any, Any, Any]


@dataclass
class TargetCase:
    name: str
    case_dir: Path
    age: int
    mask_pair: MaskPair
    variants: Dict[str, BinaryFeature]


@dataclass
class T1Record:
    source: str
    case_id: str
    full_case_base: str
    age: int
    case_dir: Path
    t1_path: Path
    all_keys: Set[str]


@dataclass
class PostCase:
    primary_key: str
    all_keys: Set[str]
    path: Path
    source_bucket: str


@dataclass
class ShapeScore:
    variant: str
    method: str
    threshold: str
    score: float
    dice: float
    jaccard: float
    volume_ratio: float
    bbox_score: float
    com_score: float
    profile_score: float
    t1_count: int
    target_count: int
    reason: str


@dataclass
class Candidate:
    record: T1Record
    best: ShapeScore


# ============================================================
# 参数
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="先做分割前/分割后集合差，再用本地 dk/tissue 形状在剩余 T1 中反查 ID。"
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--target-root", default=None)
    parser.add_argument("--log-csv", default=LOG_CSV)
    parser.add_argument("--unmatched-txt", default=UNMATCHED_TXT)
    parser.add_argument("--diff-csv", default=DIFF_CSV)
    return parser.parse_args()


# ============================================================
# Windows / NAS
# ============================================================

def run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="ignore",
        shell=False,
    )


def clear_all_net_use_connections() -> None:
    print("[NAS] 清空当前 Windows 的所有 net use 连接，用于避免 1219 凭据冲突。")
    result = run_cmd(["net", "use", "*", "/delete", "/y"])
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if output:
        print(output)
    print("[NAS] net use 清理步骤完成。")


def delete_cmdkey(target: str) -> None:
    for key in [target, f"TERMSRV/{target}"]:
        result = run_cmd(["cmdkey", "/delete:" + key])
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if output:
            print(f"[CRED] cmdkey /delete:{key}")
            print(output)


def clear_cached_credentials() -> None:
    print("[NAS] 尝试清理 Windows 凭据缓存。")
    delete_cmdkey("10.19.136.231")


def net_use(share: str, username: str, password: str) -> subprocess.CompletedProcess:
    return run_cmd(["net", "use", share, password, f"/user:{username}", "/persistent:no"])


def connect_one_share(share: str, username: str, password: str) -> bool:
    print(f"[NAS] 正在连接 {share}")
    result = net_use(share, username, password)
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    output_lower = output.lower()

    if result.returncode == 0:
        print(f"[OK] NAS 已连接：{share}")
        return True

    if "命令成功完成" in output or "the command completed successfully" in output_lower:
        print(f"[OK] NAS 已连接：{share}")
        return True

    print(f"[FAIL] NAS 连接失败：{share}")
    if output:
        print(output)
    return False


def connect_required_nas_shares() -> None:
    if CLEAR_ALL_NET_USE_AT_START:
        clear_all_net_use_connections()
        clear_cached_credentials()

    ok = connect_one_share(r"\\10.19.136.231\002", NAS231_USERNAME, NAS231_PASSWORD)

    if not ok:
        print("\n[NAS] 当前 net use 状态如下：")
        result = run_cmd(["net", "use"])
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        print(output)
        raise RuntimeError("NAS 连接失败。")


# ============================================================
# ID / age / 文件识别
# ============================================================

def is_nifti_file(path: Path) -> bool:
    n = path.name.lower()
    return n.endswith(".nii") or n.endswith(".nii.gz")


def strip_known_ext(name: str) -> str:
    base = name.strip()
    lower = base.lower()
    for ext in [".nii.gz", ".nii", ".mgz", ".mgh", ".gz", ".txt", ".csv", ".json"]:
        if lower.endswith(ext):
            return base[: -len(ext)]
    return base


def remove_age_suffix(name: str) -> str:
    return re.sub(r"_\d{1,3}mo$", "", name.strip(), flags=re.IGNORECASE)


def parse_age_from_name(name: str) -> Optional[int]:
    m = re.search(r"(?<!\d)(\d{1,3})\s*mo", name, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))

    base = strip_known_ext(name)
    if re.fullmatch(r"\d{1,3}", base):
        return int(base)

    return None


def parse_age_mo_only_from_path(path: Path) -> Optional[int]:
    for part in reversed(path.parts):
        m = re.search(r"(?<!\d)(\d{1,3})\s*mo", part, flags=re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def normalize_case_id(name: str) -> str:
    return remove_age_suffix(strip_known_ext(name)).strip()


def is_age_only_name(name: str) -> bool:
    return re.fullmatch(r"\d{1,3}\s*mo", name.strip(), flags=re.IGNORECASE) is not None


def extract_case_id_from_name(name: str) -> str:
    base = normalize_case_id(name)

    m = re.match(r"^(N\d+)", base, flags=re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.match(r"^(sub\d+)", base, flags=re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.match(r"^(\d{6,})", base)
    if m:
        return m.group(1)

    return base


def primary_case_key_from_name(name: str) -> Optional[str]:
    if is_age_only_name(name):
        return None

    base = normalize_case_id(name)
    if not base:
        return None

    lower = base.lower()
    generic = {
        "justt1", "t1t2", "t1t2_v2", "t1t2v2",
        "t1", "t2", "nii", "nifti", "data",
        "20260521_results", "results",
    }
    if lower in generic:
        return None

    # N1002_0301010101 优先保留完整 N+长数字 ID
    m = re.match(r"^(N\d+_\d+)", base, flags=re.IGNORECASE)
    if m:
        return m.group(1).lower()

    m = re.match(r"^(N\d+)", base, flags=re.IGNORECASE)
    if m:
        return m.group(1).lower()

    m = re.match(r"^(sub\d+)", base, flags=re.IGNORECASE)
    if m:
        return m.group(1).lower()

    m = re.match(r"^(\d{6,})", base)
    if m:
        return m.group(1).lower()

    return None


def case_keys_from_name(name: str) -> Set[str]:
    keys: Set[str] = set()

    primary = primary_case_key_from_name(name)
    if primary:
        keys.add(primary.lower())

    base = normalize_case_id(name)
    if base and not is_age_only_name(base):
        keys.add(base.lower())

    short_id = extract_case_id_from_name(name)
    if short_id and not is_age_only_name(short_id):
        keys.add(short_id.lower())

    return {k for k in keys if k}


def namespace_case_keys(bucket: str, keys: Set[str]) -> Set[str]:
    return {f"{bucket}:{k.lower()}" for k in keys if k}


def looks_like_case_dir_name(name: str) -> bool:
    lower = name.lower()

    generic = {
        "t1", "t2", "t1t2", "t1t2_v2", "t1t2v2",
        "justt1", "nii", "nifti", "image", "images",
        "data", "raw", "preprocess", "preprocessing",
        "tobesegmented", "20260521_results", "results",
    }
    if lower in generic:
        return False

    if primary_case_key_from_name(name) is not None:
        return True

    if re.search(r"\d{1,3}mo", name, flags=re.IGNORECASE):
        return True

    return False


def choose_case_dir_for_t1(t1_path: Path, source_root: Path) -> Path:
    cur = t1_path.parent
    candidates: List[Path] = []

    while True:
        if str(cur).lower() == str(source_root).lower():
            break

        if looks_like_case_dir_name(cur.name):
            candidates.append(cur)

        if cur.parent == cur:
            break

        cur = cur.parent

    if candidates:
        return candidates[0]

    return t1_path.parent


def find_t1_files_recursive(root: Path, max_depth: int) -> List[Path]:
    out: List[Path] = []

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            items = list(d.iterdir())
        except Exception as e:
            print(f"[WARN] 无法访问目录：{d}: {repr(e)}")
            return

        for p in items:
            if p.is_file() and p.name.lower() == SRC_T1_NAME.lower():
                out.append(p)
            elif p.is_dir():
                walk(p, depth + 1)

    walk(root, 0)

    seen = set()
    uniq: List[Path] = []
    for p in out:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            uniq.append(p)

    return uniq


def final_target_dir_name(record: T1Record, target_age: int) -> str:
    return f"{record.full_case_base}_{target_age}mo"


def find_files_recursive_limited(case_dir: Path, max_depth: int = 2) -> List[Path]:
    files: List[Path] = []

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            items = list(d.iterdir())
        except Exception:
            return

        for p in items:
            if p.is_file() and is_nifti_file(p):
                files.append(p)
            elif p.is_dir():
                walk(p, depth + 1)

    walk(case_dir, 0)
    return files


def score_mask_name(path: Path, kind: str) -> int:
    stem = strip_known_ext(path.name).lower()

    if kind == "dk":
        score = 0
        if "dk" in stem:
            score += 5
        if "struct" in stem:
            score += 5
        if "dk-struct" in stem or "dk_struct" in stem or "dkstruct" in stem:
            score += 10
        if "tissue" in stem:
            score -= 30
        return score

    if kind == "tissue":
        score = 0
        if "tissue" in stem:
            score += 10
        if "dk" in stem or "struct" in stem:
            score -= 30
        return score

    return 0


def find_mask_pair(case_dir: Path) -> Optional[MaskPair]:
    files = find_files_recursive_limited(case_dir, max_depth=2)
    if not files:
        return None

    dk_candidates = sorted(
        [(score_mask_name(p, "dk"), p) for p in files],
        key=lambda x: x[0],
        reverse=True,
    )
    tissue_candidates = sorted(
        [(score_mask_name(p, "tissue"), p) for p in files],
        key=lambda x: x[0],
        reverse=True,
    )

    dk = dk_candidates[0][1] if dk_candidates and dk_candidates[0][0] > 0 else None
    tissue = tissue_candidates[0][1] if tissue_candidates and tissue_candidates[0][0] > 0 else None

    if dk is None or tissue is None:
        return None

    if str(dk).lower() == str(tissue).lower():
        return None

    return MaskPair(dk=dk, tissue=tissue)


# ============================================================
# 分割前 / 分割后集合差
# ============================================================

def build_t1_records_for_source(source: SourceConfig, target_ages: Set[int]) -> List[T1Record]:
    records: List[T1Record] = []

    if not source.pre_root.is_dir():
        print(f"[WARN] 分割前输入目录不存在或无法访问：{source.name}: {source.pre_root}")
        return records

    print(f"[PRE_SCAN_ROOT] {source.name}: {source.pre_root}")
    t1_files = find_t1_files_recursive(source.pre_root, MAX_T1_SEARCH_DEPTH)

    print(f"[T1_FOUND] {source.name}: 递归找到 {SRC_T1_NAME} 数量：{len(t1_files)}")

    age_matched = 0
    bucket = PRE_TO_POST_BUCKET.get(source.name, source.name)

    for t1_path in t1_files:
        case_dir = choose_case_dir_for_t1(t1_path, source.pre_root)
        age = parse_age_mo_only_from_path(t1_path)

        if USE_EXACT_AGE_FILTER:
            if age is None or age not in target_ages:
                continue

        age_matched += 1

        case_id = extract_case_id_from_name(case_dir.name)
        full_case_base = normalize_case_id(case_dir.name)

        raw_keys = case_keys_from_name(case_dir.name)
        raw_keys.add(full_case_base.lower())
        raw_keys.add(case_id.lower())

        keys = namespace_case_keys(bucket, raw_keys)

        records.append(
            T1Record(
                source=source.name,
                case_id=case_id,
                full_case_base=full_case_base,
                age=age if age is not None else -1,
                case_dir=case_dir,
                t1_path=t1_path,
                all_keys={k for k in keys if k},
            )
        )

    print(
        f"[T1_SCAN] {source.name}: found_T1={len(t1_files)}, "
        f"age_matched_T1={age_matched}, usable_records={len(records)}"
    )

    return records


def build_all_t1_records(target_ages: Set[int]) -> List[T1Record]:
    print("\n========== 建立分割前 T1_acpc 候选列表 ==========")
    print(f"[TARGET_AGES] {sorted(target_ages)}")
    print("[PRE_INPUT_ROOTS]")
    for name, p in PRE_INPUT_ROOTS.items():
        print(f"  {name}: {p}")
    print("[KNOWN_RESULT_ROOTS]")
    for name, p in KNOWN_RESULT_ROOTS.items():
        print(f"  {name}: {p}")

    all_records: List[T1Record] = []

    for source in SOURCES:
        records = build_t1_records_for_source(source, target_ages)
        all_records.extend(records)

    print(f"\n[PRE_T1_TOTAL] 分割前同月龄 T1_acpc 候选总数：{len(all_records)}")
    return all_records


def collect_post_result_cases() -> Dict[str, PostCase]:
    print("\n========== 扫描已知 ID 的分割后结果池 ==========")
    print(f"[RESULTS_ROOT] {RESULTS_ROOT}")
    print(f"[UNKNOWN_RESULT_ROOT] {UNKNOWN_RESULT_ROOT}")
    print("[NOTE] T1T2_v2 是未知 ID 结果池，不会加入已完成排除集。")

    post_cases: Dict[str, PostCase] = {}

    def add_post_case(bucket: str, p: Path) -> None:
        raw_primary = primary_case_key_from_name(p.name)
        if raw_primary is None:
            return

        raw_keys = case_keys_from_name(p.name)
        raw_keys.add(raw_primary)

        namespaced_primary = f"{bucket}:{raw_primary.lower()}"
        namespaced_keys = namespace_case_keys(bucket, raw_keys)

        old = post_cases.get(namespaced_primary)
        if old is None:
            post_cases[namespaced_primary] = PostCase(
                primary_key=namespaced_primary,
                all_keys=namespaced_keys,
                path=p,
                source_bucket=bucket,
            )
        else:
            old.all_keys.update(namespaced_keys)

    def walk(bucket: str, d: Path, depth: int) -> None:
        if depth > MAX_POST_RESULT_SCAN_DEPTH:
            return

        try:
            items = list(d.iterdir())
        except Exception as e:
            print(f"[WARN] 无法访问结果目录：{d}: {repr(e)}")
            return

        add_post_case(bucket, d)

        for p in items:
            if p.is_dir():
                walk(bucket, p, depth + 1)

    for bucket, root in KNOWN_RESULT_ROOTS.items():
        if not root.is_dir():
            print(f"[WARN] 已知结果目录不存在或无法访问：{bucket}: {root}")
            continue

        print(f"[KNOWN_POST_SCAN] {bucket}: {root}")
        walk(bucket, root, 0)

    print(f"[KNOWN_POST_CASES] 识别到已知分割后 case 数量：{len(post_cases)}")

    if len(post_cases) <= 120:
        for k, v in sorted(post_cases.items()):
            print(f"  [KNOWN_POST] {k}\t{v.source_bucket}\t{v.path}")

    return post_cases


def apply_pre_minus_post_filter(
    pre_records: List[T1Record],
    post_cases: Dict[str, PostCase],
) -> Tuple[List[T1Record], List[Tuple[T1Record, str]], List[PostCase]]:
    post_all_keys: Set[str] = set()
    for pc in post_cases.values():
        post_all_keys.update(k.lower() for k in pc.all_keys)
        post_all_keys.add(pc.primary_key.lower())

    remaining: List[T1Record] = []
    excluded: List[Tuple[T1Record, str]] = []
    pre_all_keys: Set[str] = set()

    for r in pre_records:
        pre_all_keys.update(k.lower() for k in r.all_keys)

        hit = sorted(k for k in r.all_keys if k.lower() in post_all_keys)

        if hit:
            excluded.append((r, "matched_known_post:" + ",".join(hit)))
            continue

        if r.source not in CANDIDATE_PRE_SOURCE_NAMES:
            excluded.append((r, "not_candidate_for_unknown_T1T2_v2:" + r.source))
            continue

        remaining.append(r)

    post_extra: List[PostCase] = []
    for pc in post_cases.values():
        if pc.primary_key.lower() not in pre_all_keys and not any(k.lower() in pre_all_keys for k in pc.all_keys):
            post_extra.append(pc)

    print("\n========== 分割前 - 已知分割后 集合差 ==========")
    print(f"分割前 T1 总候选数：{len(pre_records)}")
    print(f"已知分割后 case 数：{len(post_cases)}")
    print(f"被已知结果或非候选来源排除的 T1 数：{len(excluded)}")
    print(f"剩余可匹配 T1 数：{len(remaining)}")
    print(f"分割后有、分割前未找到的异常 case 数：{len(post_extra)}")

    by_source: Dict[str, int] = {}
    for r in pre_records:
        by_source[r.source] = by_source.get(r.source, 0) + 1

    print("\n[PRE_BY_SOURCE]")
    for source_name in sorted(by_source):
        print(f"  {source_name}: {by_source[source_name]}")

    by_age: Dict[int, int] = {}
    for r in remaining:
        by_age[r.age] = by_age.get(r.age, 0) + 1

    print("\n[REMAINING_BY_AGE] 只统计 PRE_T1T2 减去 results/T1T2 后剩下的候选")
    for age in sorted(by_age):
        print(f"  age={age}mo: {by_age[age]}")

    if len(remaining) <= 100:
        print("\n[REMAINING_PREVIEW]")
        for r in remaining:
            print(f"  age={r.age}\tcase={r.full_case_base}\tt1={r.t1_path}")

    if post_extra:
        print("\n[POST_EXTRA_PREVIEW] 已知结果里有，但分割前输入池没匹配到，前 50 个：")
        for pc in post_extra[:50]:
            print(f"  {pc.primary_key}\t{pc.source_bucket}\t{pc.path}")

    return remaining, excluded, post_extra


def write_diff_report(
    pre_records: List[T1Record],
    remaining: List[T1Record],
    excluded: List[Tuple[T1Record, str]],
    post_extra: List[PostCase],
    diff_csv: str,
) -> None:
    remaining_ids = {str(r.t1_path).lower() for r in remaining}
    excluded_map = {str(r.t1_path).lower(): reason for r, reason in excluded}

    with open(diff_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "record_type",
                "status",
                "source",
                "age",
                "full_case_base",
                "case_id",
                "case_dir",
                "t1_path",
                "all_keys",
                "exclude_reason",
                "post_bucket",
                "post_path",
            ],
        )
        writer.writeheader()

        for r in pre_records:
            key = str(r.t1_path).lower()
            status = "remaining_candidate" if key in remaining_ids else "excluded"

            writer.writerow({
                "record_type": "pre_t1",
                "status": status,
                "source": r.source,
                "age": r.age,
                "full_case_base": r.full_case_base,
                "case_id": r.case_id,
                "case_dir": str(r.case_dir),
                "t1_path": str(r.t1_path),
                "all_keys": ";".join(sorted(r.all_keys)),
                "exclude_reason": excluded_map.get(key, ""),
                "post_bucket": "",
                "post_path": "",
            })

        for pc in post_extra:
            writer.writerow({
                "record_type": "post_extra_not_in_pre",
                "status": "post_has_but_pre_missing",
                "source": "",
                "age": "",
                "full_case_base": pc.primary_key,
                "case_id": "",
                "case_dir": "",
                "t1_path": "",
                "all_keys": ";".join(sorted(pc.all_keys)),
                "exclude_reason": "",
                "post_bucket": pc.source_bucket,
                "post_path": str(pc.path),
            })

    print(f"[OK] 分割前/后集合差报告已写出：{Path(diff_csv).resolve()}")


# ============================================================
# NIfTI / 形状匹配
# ============================================================

def load_nifti_array(path: Path) -> Any:
    if nib is None or np is None:
        raise RuntimeError("缺少 nibabel/numpy。请先运行：python -m pip install nibabel numpy")

    img = nib.load(str(path))
    arr = np.asanyarray(img.dataobj)

    if arr.ndim > 3:
        arr = np.squeeze(arr)

    if arr.ndim != 3:
        raise ValueError(f"NIfTI 不是 3D：{path}, shape={arr.shape}")

    return arr


def binary_from_label(path: Path) -> Any:
    arr = load_nifti_array(path)
    return np.ascontiguousarray(arr != 0)


def prepare_t1_array(path: Path) -> Any:
    arr = load_nifti_array(path).astype(np.float32, copy=False)
    arr = np.asarray(arr)
    arr = np.where(np.isfinite(arr), arr, -np.inf)
    return arr


def binary_from_t1_fixed_threshold(arr: Any, threshold: float) -> Any:
    return np.ascontiguousarray(arr > threshold)


def binary_from_t1_topk(arr: Any, target_count: int) -> Tuple[Any, float]:
    if target_count <= 0:
        return np.zeros(arr.shape, dtype=bool), float("inf")

    flat = arr.ravel()
    n = int(flat.size)

    if target_count >= n:
        return np.ones(arr.shape, dtype=bool), float(np.nanmin(flat))

    kth = n - int(target_count)
    threshold = float(np.partition(flat, kth)[kth])

    binary = arr >= threshold
    count = int(binary.sum())

    if count > int(target_count * 1.02):
        idx = np.argpartition(flat, kth)[kth:]
        bflat = np.zeros(n, dtype=bool)
        bflat[idx] = True
        binary = bflat.reshape(arr.shape)
        threshold = float(flat[idx].min())

    return np.ascontiguousarray(binary), threshold


def compute_bbox(binary: Any) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    nz = np.nonzero(binary)
    if len(nz[0]) == 0:
        return (0, 0, 0), (0, 0, 0)

    mins = tuple(int(np.min(v)) for v in nz)
    maxs = tuple(int(np.max(v)) for v in nz)
    return mins, maxs


def compute_com(binary: Any) -> Tuple[float, float, float]:
    nz = np.nonzero(binary)
    if len(nz[0]) == 0:
        return 0.0, 0.0, 0.0
    return tuple(float(np.mean(v)) for v in nz)


def compute_profiles(binary: Any) -> Tuple[Any, Any, Any]:
    p0 = binary.sum(axis=(1, 2)).astype(np.float64)
    p1 = binary.sum(axis=(0, 2)).astype(np.float64)
    p2 = binary.sum(axis=(0, 1)).astype(np.float64)
    return p0, p1, p2


def make_feature(label: str, path: str, binary: Any) -> BinaryFeature:
    if binary.ndim != 3:
        raise ValueError(f"binary is not 3D: {label}, shape={binary.shape}")

    count = int(binary.sum())
    bbox_min, bbox_max = compute_bbox(binary)
    com = compute_com(binary)
    profiles = compute_profiles(binary)

    return BinaryFeature(
        label=label,
        path=path,
        binary=binary,
        shape=tuple(int(x) for x in binary.shape),
        count=count,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        com=com,
        profiles=profiles,
    )


def profile_corr(a: Any, b: Any) -> float:
    if a.shape != b.shape:
        return 0.0

    a = a.astype(np.float64)
    b = b.astype(np.float64)

    a_std = float(a.std())
    b_std = float(b.std())
    if a_std == 0 or b_std == 0:
        return 0.0

    corr = float(np.corrcoef(a, b)[0, 1])
    if math.isnan(corr):
        return 0.0

    return max(0.0, min(1.0, (corr + 1.0) / 2.0))


def bbox_similarity(a: BinaryFeature, b: BinaryFeature) -> float:
    diff = 0.0
    for x, y in zip(a.bbox_min, b.bbox_min):
        diff += abs(x - y)
    for x, y in zip(a.bbox_max, b.bbox_max):
        diff += abs(x - y)

    return max(0.0, 1.0 - diff / 60.0)


def com_similarity(a: BinaryFeature, b: BinaryFeature) -> float:
    dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(a.com, b.com)))
    return max(0.0, 1.0 - dist / 20.0)


def compare_features(
    t1_feat: BinaryFeature,
    target_feat: BinaryFeature,
    method: str,
    threshold: str,
) -> ShapeScore:
    if t1_feat.shape != target_feat.shape:
        return ShapeScore(
            variant=target_feat.label,
            method=method,
            threshold=threshold,
            score=0.0,
            dice=0.0,
            jaccard=0.0,
            volume_ratio=0.0,
            bbox_score=0.0,
            com_score=0.0,
            profile_score=0.0,
            t1_count=t1_feat.count,
            target_count=target_feat.count,
            reason=f"shape_diff t1={t1_feat.shape} target={target_feat.shape}",
        )

    a = t1_feat.binary
    b = target_feat.binary

    inter = int(np.logical_and(a, b).sum())
    a_count = t1_feat.count
    b_count = target_feat.count
    union = a_count + b_count - inter

    dice = 1.0 if a_count + b_count == 0 else 2.0 * inter / float(a_count + b_count)
    jaccard = 1.0 if union == 0 else inter / float(union)
    volume_ratio = 1.0 if max(a_count, b_count) == 0 else min(a_count, b_count) / float(max(a_count, b_count))

    bbox_score = bbox_similarity(t1_feat, target_feat)
    com_score = com_similarity(t1_feat, target_feat)

    p_corrs = [
        profile_corr(t1_feat.profiles[0], target_feat.profiles[0]),
        profile_corr(t1_feat.profiles[1], target_feat.profiles[1]),
        profile_corr(t1_feat.profiles[2], target_feat.profiles[2]),
    ]
    profile_score = float(sum(p_corrs) / len(p_corrs))

    score = (
        1000.0 * dice
        + 500.0 * jaccard
        + 250.0 * volume_ratio
        + 150.0 * bbox_score
        + 150.0 * com_score
        + 300.0 * profile_score
    )

    reason = (
        f"variant={target_feat.label}; method={method}; threshold={threshold}; "
        f"dice={dice:.6f}; jaccard={jaccard:.6f}; "
        f"volume_ratio={volume_ratio:.6f}; "
        f"bbox_score={bbox_score:.6f}; "
        f"com_score={com_score:.6f}; "
        f"profile_score={profile_score:.6f}; "
        f"t1_count={a_count}; target_count={b_count}"
    )

    return ShapeScore(
        variant=target_feat.label,
        method=method,
        threshold=threshold,
        score=score,
        dice=dice,
        jaccard=jaccard,
        volume_ratio=volume_ratio,
        bbox_score=bbox_score,
        com_score=com_score,
        profile_score=profile_score,
        t1_count=a_count,
        target_count=b_count,
        reason=reason,
    )


def compare_t1_array_to_target(t1_arr: Any, t1_path: Path, target: TargetCase) -> ShapeScore:
    scores: List[ShapeScore] = []
    topk_feature_cache: Dict[int, Tuple[BinaryFeature, float]] = {}

    if USE_TOPK_VOLUME_MATCH:
        for variant in target.variants.values():
            if variant.count not in topk_feature_cache:
                t1_bin, threshold = binary_from_t1_topk(t1_arr, variant.count)
                t1_feat = make_feature(
                    label=f"t1_topk_{variant.count}",
                    path=str(t1_path),
                    binary=t1_bin,
                )
                topk_feature_cache[variant.count] = (t1_feat, threshold)

            t1_feat, threshold = topk_feature_cache[variant.count]
            scores.append(
                compare_features(
                    t1_feat=t1_feat,
                    target_feat=variant,
                    method="topk_volume_matched",
                    threshold=f"{threshold:.6f}",
                )
            )

    if USE_FIXED_THRESHOLD_CANDIDATES:
        for threshold in FIXED_T1_THRESHOLDS:
            t1_bin = binary_from_t1_fixed_threshold(t1_arr, threshold)
            t1_feat = make_feature(
                label=f"t1_gt_{threshold}",
                path=str(t1_path),
                binary=t1_bin,
            )

            for variant in target.variants.values():
                scores.append(
                    compare_features(
                        t1_feat=t1_feat,
                        target_feat=variant,
                        method="fixed_threshold",
                        threshold=f"{threshold:.6f}",
                    )
                )

    if not scores:
        raise RuntimeError("没有生成任何 T1 foreground candidate")

    scores.sort(key=lambda s: s.score, reverse=True)
    return scores[0]


# ============================================================
# 扫描本地目标
# ============================================================

def discover_targets(target_root: Path) -> List[TargetCase]:
    print("\n========== 扫描本地目标目录 ==========")
    print(f"[TARGET_ROOT] {target_root}")

    if not target_root.is_dir():
        raise FileNotFoundError(f"本地目标目录不存在：{target_root}")

    targets: List[TargetCase] = []

    for item in sorted(target_root.iterdir(), key=lambda p: p.name):
        if not item.is_dir():
            continue

        if not PROCESS_ALREADY_RENAMED_DIRS:
            if re.match(r"^(N\d+|sub\d+|\d{6,}).+_\d{1,3}mo$", item.name, flags=re.IGNORECASE):
                continue

        age = parse_age_from_name(item.name)
        if age is None:
            print(f"[SKIP] {item.name}: 无法从目录名解析月龄")
            continue

        pair = find_mask_pair(item)
        if pair is None:
            print(f"[SKIP] {item.name}: 未找到 dk-struct/tissue 成对 mask")
            continue

        try:
            dk_bin = binary_from_label(pair.dk)
            tissue_bin = binary_from_label(pair.tissue)
            union_bin = np.ascontiguousarray(np.logical_or(dk_bin, tissue_bin))
        except Exception as e:
            print(f"[SKIP] {item.name}: 读取 mask 失败：{repr(e)}")
            continue

        variants = {
            "dk": make_feature("dk", str(pair.dk), dk_bin),
            "tissue": make_feature("tissue", str(pair.tissue), tissue_bin),
            "union": make_feature("union", f"{pair.dk} | {pair.tissue}", union_bin),
        }

        target = TargetCase(
            name=item.name,
            case_dir=item,
            age=age,
            mask_pair=pair,
            variants=variants,
        )
        targets.append(target)

        print(
            f"[TARGET] {item.name}: age={age}, "
            f"shape={variants['union'].shape}, "
            f"dk_count={variants['dk'].count}, "
            f"tissue_count={variants['tissue'].count}, "
            f"union_count={variants['union'].count}"
        )

    print(f"[TARGET] 找到可匹配目标数量：{len(targets)}")
    return targets


def group_targets_by_age(targets: List[TargetCase]) -> Dict[int, List[TargetCase]]:
    out: Dict[int, List[TargetCase]] = {}
    for t in targets:
        out.setdefault(t.age, []).append(t)
    return out


# ============================================================
# 匹配与执行
# ============================================================

def update_top_candidates(top_map: Dict[str, List[Candidate]], target: TargetCase, cand: Candidate) -> None:
    arr = top_map.setdefault(target.name, [])
    arr.append(cand)
    arr.sort(key=lambda c: c.best.score, reverse=True)
    del arr[TOP_K:]


def scan_t1_and_match(records: List[T1Record], targets_by_age: Dict[int, List[TargetCase]]) -> Dict[str, List[Candidate]]:
    top_map: Dict[str, List[Candidate]] = {}

    print("\n========== 读取剩余 T1_acpc 并做 top-k 形状匹配 ==========")

    processed = 0
    failed = 0

    for record in records:
        if record.age not in targets_by_age:
            continue

        try:
            t1_arr = prepare_t1_array(record.t1_path)
            processed += 1

            for target in targets_by_age[record.age]:
                best_score = compare_t1_array_to_target(t1_arr, record.t1_path, target)
                cand = Candidate(record=record, best=best_score)
                update_top_candidates(top_map, target, cand)

            if processed % 10 == 0:
                print(f"[PROGRESS] 已读取并比较 T1 数量：{processed}/{len(records)}")

        except Exception as e:
            failed += 1
            print(f"[WARN] 处理 T1 失败：{record.source}/{record.full_case_base}: {record.t1_path}: {repr(e)}")

    print(f"[DONE] 已处理 T1 数量：{processed}，失败数量：{failed}")
    return top_map


def count_records_by_age(records: List[T1Record]) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for r in records:
        out[r.age] = out.get(r.age, 0) + 1
    return out


def is_candidate_accepted(candidates: List[Candidate], remaining_count_for_age: int) -> Tuple[bool, str]:
    if not candidates:
        return False, "无候选"

    top = candidates[0]
    has_second = len(candidates) > 1

    second_score = candidates[1].best.score if has_second else None
    second_dice = candidates[1].best.dice if has_second else None
    margin = top.best.score - second_score if second_score is not None else None

    second_score_msg = f"{second_score:.2f}" if second_score is not None else "NA"
    second_dice_msg = f"{second_dice:.6f}" if second_dice is not None else "NA"
    margin_msg = f"{margin:.2f}" if margin is not None else "NA"

    if ACCEPT_UNIQUE_REMAINING_BY_AGE and remaining_count_for_age == 1:
        if top.best.dice >= UNIQUE_REMAINING_MIN_DICE:
            return (
                True,
                f"accepted_unique_remaining_by_age; remaining_count_for_age=1; "
                f"top_score={top.best.score:.2f}; top_dice={top.best.dice:.6f}; "
                f"second_score={second_score_msg}; second_dice={second_dice_msg}; margin={margin_msg}; "
                f"top={top.record.source}/{top.record.full_case_base}; "
                f"variant={top.best.variant}; method={top.best.method}; threshold={top.best.threshold}"
            )

        return (
            False,
            f"该月龄只剩 1 个候选，但 Dice 仍过低；"
            f"top_dice={top.best.dice:.6f}, need>={UNIQUE_REMAINING_MIN_DICE:.6f}; "
            f"top={top.record.source}/{top.record.full_case_base}"
        )

    if top.best.dice < ACCEPT_MIN_DICE:
        return (
            False,
            f"top dice 不足；top_dice={top.best.dice:.6f}, "
            f"second_dice={second_dice_msg}, "
            f"need>={ACCEPT_MIN_DICE:.6f}, top={top.record.source}/{top.record.full_case_base}"
        )

    if top.best.score < ACCEPT_MIN_SCORE:
        return (
            False,
            f"top score 不足；top_score={top.best.score:.2f}, "
            f"need>={ACCEPT_MIN_SCORE:.2f}, top={top.record.source}/{top.record.full_case_base}"
        )

    if margin is not None and margin < ACCEPT_MIN_MARGIN:
        return (
            False,
            f"top1-top2 差距不足；top_score={top.best.score:.2f}, "
            f"second_score={second_score_msg}, margin={margin_msg}, "
            f"need>={ACCEPT_MIN_MARGIN:.2f}"
        )

    return (
        True,
        f"accepted; top_score={top.best.score:.2f}; second_score={second_score_msg}; "
        f"margin={margin_msg}; top_dice={top.best.dice:.6f}; second_dice={second_dice_msg}; "
        f"top={top.record.source}/{top.record.full_case_base}; "
        f"variant={top.best.variant}; method={top.best.method}; threshold={top.best.threshold}"
    )


def safe_rename_target_dir(old_dir: Path, new_name: str, dry_run: bool) -> Tuple[Path, str]:
    new_dir = old_dir.parent / new_name

    if str(old_dir).lower() == str(new_dir).lower():
        return old_dir, f"目录名已正确：{old_dir}"

    if new_dir.exists():
        raise FileExistsError(f"目标重命名目录已存在，为避免合并/覆盖，停止：{new_dir}")

    if dry_run:
        return new_dir, f"[DRY-RUN] 将重命名目录：{old_dir} -> {new_dir}"

    old_dir.rename(new_dir)
    return new_dir, f"已重命名目录：{old_dir} -> {new_dir}"


def copy_t1_to_target(t1_path: Path, target_dir: Path, overwrite: bool, dry_run: bool) -> Tuple[str, str]:
    dst = target_dir / DST_FILE_NAME
    existed_before = dst.exists()

    if existed_before and not overwrite:
        return "skipped_existing", f"目标已存在 {dst}，未覆盖"

    if dry_run:
        action = "dry_run_overwrite" if existed_before else "dry_run_copy"
        return action, f"[DRY-RUN] 将复制 {t1_path} -> {dst}"

    shutil.copy2(t1_path, dst)
    action = "overwritten" if existed_before else "copied"
    return action, f"已复制 {t1_path} -> {dst}"


def format_top_candidates(candidates: List[Candidate], max_n: int = TOP_K) -> str:
    parts = []

    for c in candidates[:max_n]:
        r = c.record
        b = c.best
        parts.append(
            f"{r.source}:{r.full_case_base}:case_id={r.case_id}:age={r.age}:"
            f"score={b.score:.2f}:dice={b.dice:.6f}:jaccard={b.jaccard:.6f}:"
            f"variant={b.variant}:method={b.method}:threshold={b.threshold}:"
            f"t1_count={b.t1_count}:target_count={b.target_count}:"
            f"vol_ratio={b.volume_ratio:.6f}:"
            f"bbox={b.bbox_score:.6f}:com={b.com_score:.6f}:profile={b.profile_score:.6f}:"
            f"case_dir={r.case_dir}:t1={r.t1_path}"
        )

    return " || ".join(parts)


def write_reports(rows: List[Dict[str, Any]], log_csv: str, unmatched_txt: str) -> None:
    fieldnames = [
        "target_name",
        "target_dir",
        "target_age",
        "target_dk",
        "target_tissue",
        "remaining_count_for_age",
        "status",
        "accepted",
        "matched_source",
        "matched_id",
        "matched_full_case_base",
        "final_dir_name",
        "final_dir",
        "matched_age",
        "matched_case_dir",
        "matched_t1",
        "best_variant",
        "best_method",
        "best_threshold",
        "best_score",
        "best_dice",
        "best_jaccard",
        "best_volume_ratio",
        "best_bbox_score",
        "best_com_score",
        "best_profile_score",
        "best_t1_count",
        "best_target_count",
        "decision_reason",
        "rename_message",
        "copy_message",
        "top_candidates",
    ]

    with open(log_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with open(unmatched_txt, "w", encoding="utf-8-sig", newline="") as f:
        for row in rows:
            if row["accepted"] != "True":
                f.write(
                    f"target_name={row['target_name']}\t"
                    f"age={row['target_age']}\t"
                    f"remaining_count_for_age={row['remaining_count_for_age']}\t"
                    f"status={row['status']}\t"
                    f"reason={row['decision_reason']}\t"
                    f"top_candidates={row['top_candidates']}\n"
                )

    print(f"[OK] 全量匹配日志已写出：{Path(log_csv).resolve()}")
    print(f"[OK] 未匹配/歧义列表已写出：{Path(unmatched_txt).resolve()}")


def main() -> None:
    args = parse_args()

    dry_run = DRY_RUN
    overwrite = args.overwrite or OVERWRITE_EXISTING
    target_root = Path(args.target_root) if args.target_root else LOCAL_MIX_ROOT

    print("========== 任务参数 ==========")
    print(f"DRY_RUN:                         {dry_run}")
    print(f"OVERWRITE_EXISTING:              {overwrite}")
    print(f"LOCAL_MIX_ROOT:                  {LOCAL_MIX_ROOT}")
    print(f"TARGET_ROOT:                     {target_root}")
    print(f"TOBESEG_ROOT:                    {TOBESEG_ROOT}")
    print(f"RESULTS_ROOT:                    {RESULTS_ROOT}")
    print(f"PRE_INPUT_ROOTS:                 {PRE_INPUT_ROOTS}")
    print(f"KNOWN_RESULT_ROOTS:              {KNOWN_RESULT_ROOTS}")
    print(f"UNKNOWN_RESULT_ROOT:             {UNKNOWN_RESULT_ROOT}")
    print(f"CANDIDATE_PRE_SOURCE_NAMES:      {CANDIDATE_PRE_SOURCE_NAMES}")
    print(f"MAX_T1_SEARCH_DEPTH:             {MAX_T1_SEARCH_DEPTH}")
    print(f"MAX_POST_RESULT_SCAN_DEPTH:      {MAX_POST_RESULT_SCAN_DEPTH}")
    print(f"USE_EXACT_AGE_FILTER:            {USE_EXACT_AGE_FILTER}")
    print(f"ACCEPT_UNIQUE_REMAINING_BY_AGE:  {ACCEPT_UNIQUE_REMAINING_BY_AGE}")
    print(f"UNIQUE_REMAINING_MIN_DICE:       {UNIQUE_REMAINING_MIN_DICE}")
    print(f"USE_TOPK_VOLUME_MATCH:           {USE_TOPK_VOLUME_MATCH}")
    print(f"USE_FIXED_THRESHOLD_CANDIDATES:  {USE_FIXED_THRESHOLD_CANDIDATES}")
    print(f"FIXED_T1_THRESHOLDS:             {FIXED_T1_THRESHOLDS}")
    print(f"ACCEPT_MIN_DICE:                 {ACCEPT_MIN_DICE}")
    print(f"ACCEPT_MIN_SCORE:                {ACCEPT_MIN_SCORE}")
    print(f"ACCEPT_MIN_MARGIN:               {ACCEPT_MIN_MARGIN}")
    print(f"LOG_CSV:                         {args.log_csv}")
    print(f"UNMATCHED_TXT:                   {args.unmatched_txt}")
    print(f"DIFF_CSV:                        {args.diff_csv}")

    if dry_run:
        print("\n当前是 DRY_RUN=True：会做集合差和匹配，但不会真正重命名目录，也不会复制 brain.nii.gz。")
    else:
        print("\n当前是 DRY_RUN=False：会真实重命名目录，并复制 brain.nii.gz。")

    if nib is None or np is None:
        raise RuntimeError("缺少 nibabel/numpy。请先运行：python -m pip install nibabel numpy")

    print("\n========== 连接 NAS ==========")
    connect_required_nas_shares()

    targets = discover_targets(target_root)
    targets_by_age = group_targets_by_age(targets)
    target_ages = set(targets_by_age.keys())

    pre_records = build_all_t1_records(target_ages)
    post_cases = collect_post_result_cases()
    remaining_records, excluded_records, post_extra = apply_pre_minus_post_filter(pre_records, post_cases)

    write_diff_report(
        pre_records=pre_records,
        remaining=remaining_records,
        excluded=excluded_records,
        post_extra=post_extra,
        diff_csv=args.diff_csv,
    )

    remaining_by_age = count_records_by_age(remaining_records)
    top_map = scan_t1_and_match(remaining_records, targets_by_age)

    rows: List[Dict[str, Any]] = []

    matched_count = 0
    renamed_or_planned_count = 0
    copied_or_planned_count = 0
    skipped_existing_count = 0
    unmatched_count = 0
    failed_count = 0

    print("\n========== 判定匹配结果、计划重命名和复制 ==========")

    for target in targets:
        candidates = top_map.get(target.name, [])
        remaining_count_for_age = remaining_by_age.get(target.age, 0)
        accepted, decision_reason = is_candidate_accepted(candidates, remaining_count_for_age)

        row: Dict[str, Any] = {
            "target_name": target.name,
            "target_dir": str(target.case_dir),
            "target_age": target.age,
            "target_dk": str(target.mask_pair.dk),
            "target_tissue": str(target.mask_pair.tissue),
            "remaining_count_for_age": remaining_count_for_age,
            "status": "",
            "accepted": str(accepted),
            "matched_source": "",
            "matched_id": "",
            "matched_full_case_base": "",
            "final_dir_name": "",
            "final_dir": "",
            "matched_age": "",
            "matched_case_dir": "",
            "matched_t1": "",
            "best_variant": "",
            "best_method": "",
            "best_threshold": "",
            "best_score": "",
            "best_dice": "",
            "best_jaccard": "",
            "best_volume_ratio": "",
            "best_bbox_score": "",
            "best_com_score": "",
            "best_profile_score": "",
            "best_t1_count": "",
            "best_target_count": "",
            "decision_reason": decision_reason,
            "rename_message": "",
            "copy_message": "",
            "top_candidates": format_top_candidates(candidates),
        }

        if not candidates:
            unmatched_count += 1
            row["status"] = "unmatched"
            print(f"[UNMATCHED] {target.name}: 无候选；remaining_count_for_age={remaining_count_for_age}")
            rows.append(row)
            continue

        top = candidates[0]
        r = top.record
        b = top.best

        row["matched_source"] = r.source
        row["matched_id"] = r.case_id
        row["matched_full_case_base"] = r.full_case_base
        row["matched_age"] = r.age
        row["matched_case_dir"] = str(r.case_dir)
        row["matched_t1"] = str(r.t1_path)
        row["best_variant"] = b.variant
        row["best_method"] = b.method
        row["best_threshold"] = b.threshold
        row["best_score"] = f"{b.score:.6f}"
        row["best_dice"] = f"{b.dice:.6f}"
        row["best_jaccard"] = f"{b.jaccard:.6f}"
        row["best_volume_ratio"] = f"{b.volume_ratio:.6f}"
        row["best_bbox_score"] = f"{b.bbox_score:.6f}"
        row["best_com_score"] = f"{b.com_score:.6f}"
        row["best_profile_score"] = f"{b.profile_score:.6f}"
        row["best_t1_count"] = str(b.t1_count)
        row["best_target_count"] = str(b.target_count)

        if not accepted:
            unmatched_count += 1
            row["status"] = "low_confidence"
            print(f"[LOW_CONF] {target.name}: {decision_reason}")
            print(
                f"           remaining_count_for_age={remaining_count_for_age}, "
                f"top={r.source}/{r.full_case_base}, "
                f"score={b.score:.2f}, dice={b.dice:.6f}, "
                f"variant={b.variant}, method={b.method}, threshold={b.threshold}, "
                f"t1_count={b.t1_count}, target_count={b.target_count}"
            )
            rows.append(row)
            continue

        try:
            final_name = final_target_dir_name(r, target.age)
            row["final_dir_name"] = final_name

            print(
                f"[MATCHED] {target.name} -> {r.source}/{final_name}, "
                f"remaining_count_for_age={remaining_count_for_age}, "
                f"score={b.score:.2f}, dice={b.dice:.6f}, "
                f"variant={b.variant}, method={b.method}, threshold={b.threshold}"
            )

            renamed_dir, rename_msg = safe_rename_target_dir(
                old_dir=target.case_dir,
                new_name=final_name,
                dry_run=dry_run,
            )
            row["final_dir"] = str(renamed_dir)
            row["rename_message"] = rename_msg
            renamed_or_planned_count += 1
            matched_count += 1

            print(f"[RENAME] {target.name}: {rename_msg}")

            copy_status, copy_msg = copy_t1_to_target(
                t1_path=r.t1_path,
                target_dir=renamed_dir,
                overwrite=overwrite,
                dry_run=dry_run,
            )

            row["status"] = copy_status
            row["copy_message"] = copy_msg

            if copy_status == "skipped_existing":
                skipped_existing_count += 1
            else:
                copied_or_planned_count += 1

            print(f"[{copy_status.upper()}] {target.name}: {copy_msg}")
            rows.append(row)

        except Exception as e:
            failed_count += 1
            row["status"] = "failed"
            row["decision_reason"] = row["decision_reason"] + "; " + repr(e)
            print(f"[FAIL] {target.name}: {repr(e)}")
            rows.append(row)

    print("\n========== 写出报告 ==========")
    write_reports(rows, args.log_csv, args.unmatched_txt)

    print("\n========== 汇总 ==========")
    print(f"目标月龄目录数量：{len(targets)}")
    print(f"分割前同月龄 T1 数量：{len(pre_records)}")
    print(f"集合差后剩余 T1 数量：{len(remaining_records)}")
    print(f"成功确定 ID/来源数量：{matched_count}")
    print(f"计划重命名/已重命名数量：{renamed_or_planned_count}")
    print(f"计划复制/已复制 brain.nii.gz 数量：{copied_or_planned_count}")
    print(f"已有 brain.nii.gz 跳过数量：{skipped_existing_count}")
    print(f"未匹配/低置信度/歧义数量：{unmatched_count}")
    print(f"失败数量：{failed_count}")

    if unmatched_count > 0:
        print("\n========== 未匹配/低置信度目标 ==========")
        for row in rows:
            if row["accepted"] != "True":
                print(
                    f"{row['target_name']}\tage={row['target_age']}\t"
                    f"remaining_count_for_age={row['remaining_count_for_age']}\t"
                    f"status={row['status']}\t"
                    f"reason={row['decision_reason']}\t"
                    f"top={row['top_candidates']}"
                )

    if dry_run:
        print("\n当前是 DRY_RUN=True，没有真正重命名/复制。")
        print("先看 pre_post_pool_diff_report.csv 和匹配报告。确认无误后，把脚本顶部 DRY_RUN 改成 False 再运行。")
    else:
        print("\n真实执行完成。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断。")
        sys.exit(130)