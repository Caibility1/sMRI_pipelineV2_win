# -*- coding: utf-8 -*-
"""
将 nnUNet 输出的 mask 复制到对应 ID 文件夹下，并重命名为 mask.nii.gz。

功能：
1. 给定 mask_path，例如 Test260623
2. 给定 target_subject_root，例如 questionable
3. 遍历 target_subject_root 下每个 ID 文件夹
4. 在 mask_path 中寻找对应 mask
5. 复制到该 ID 文件夹下，命名为 mask.nii.gz

不会复制 T1/T2。
不会处理 registration/T2_to_T1。
不会新建 skullstrip 输出目录。
"""

from pathlib import Path
import re
import shutil


# ========= 可修改配置 =========

mask_path = Path(r"D:\University\master\QC2026\2026\0604_CBCP\Test260623")

target_subject_root = Path(r"D:\University\master\QC2026\2026\0604_CBCP\questionable")

DRY_RUN = True        # 第一次建议 True，只预览；确认无误后改 False
OVERWRITE = True      # 如果目标文件夹里已有 mask.nii.gz，是否覆盖

MASK_PREFIX = "T523_" # nnUNet 输出一般类似 T523_0101010265.nii.gz

# ============================


def strip_age_suffix(name: str) -> str:
    """
    去掉末尾月龄后缀。

    0101010265_13mo          -> 0101010265
    N1062_0301010602_0mo     -> N1062_0301010602
    N1062_0301010602         -> N1062_0301010602
    """
    s = str(name).strip()
    s = re.sub(r"[_\-\s]*\d+(?:\.\d+)?\s*mo$", "", s, flags=re.IGNORECASE)
    return s


def remove_nii_suffix(filename: str) -> str:
    """
    去掉 .nii.gz 或 .nii 后缀。
    """
    s = str(filename).strip()

    if s.lower().endswith(".nii.gz"):
        return s[:-7]

    if s.lower().endswith(".nii"):
        return s[:-4]

    return s


def get_mask_core_from_filename(mask_filename: str) -> str:
    """
    从 nnUNet 输出文件名中提取核心 ID。

    T523_0101010265.nii.gz       -> 0101010265
    T523_N10620301010602.nii.gz  -> N10620301010602
    """
    core = remove_nii_suffix(mask_filename)

    if core.startswith(MASK_PREFIX):
        core = core[len(MASK_PREFIX):]

    return core


def normalize_alnum(s: str) -> str:
    """
    去掉非字母数字，并统一大写。

    N1062_0301010602 -> N10620301010602
    """
    return re.sub(r"[^A-Za-z0-9]", "", str(s)).upper()


def is_n_subject(folder_id: str) -> bool:
    return re.match(r"^N\d+", folder_id, flags=re.IGNORECASE) is not None


def extract_n_key(folder_id: str):
    """
    从 N 类文件夹 ID 中提取第一个 Nxxxx。

    N1062_0301010602     -> N1062
    N1062_0301010602_0mo -> N1062
    """
    s = strip_age_suffix(folder_id)
    m = re.match(r"^(N\d+)", s, flags=re.IGNORECASE)

    if not m:
        return None

    return m.group(1).upper()


def collect_known_n_keys(subject_root: Path):
    """
    从目标 ID 文件夹中收集所有 N 类 key。
    例如：
    N1062_0301010602_0mo -> N1062

    用于匹配：
    T523_N10620301010602.nii.gz -> N1062
    """
    n_keys = set()

    for p in subject_root.iterdir():
        if not p.is_dir():
            continue

        folder_id = strip_age_suffix(p.name)

        if is_n_subject(folder_id):
            n_key = extract_n_key(folder_id)
            if n_key:
                n_keys.add(n_key)

    return sorted(n_keys, key=len, reverse=True)


def build_mask_index(mask_dir: Path, known_n_keys):
    """
    建立 mask 文件索引。

    exact_index:
        普通数字 ID 使用完整匹配。
        0101010265 -> T523_0101010265.nii.gz

    n_key_index:
        N 类 ID 使用 Nxxxx 匹配。
        N1062 -> T523_N10620301010602.nii.gz
    """
    exact_index = {}
    n_key_index = {}
    duplicate_exact = {}
    duplicate_n = {}

    for p in mask_dir.iterdir():
        if not p.is_file():
            continue

        name = p.name

        if not (name.startswith(MASK_PREFIX) and name.lower().endswith(".nii.gz")):
            continue

        core = get_mask_core_from_filename(name)
        norm_core = normalize_alnum(core)

        if norm_core in exact_index:
            duplicate_exact.setdefault(norm_core, [exact_index[norm_core]]).append(p)
        else:
            exact_index[norm_core] = p

        if norm_core.startswith("N"):
            matched_n_key = None

            for n_key in known_n_keys:
                n_key_norm = normalize_alnum(n_key)

                if norm_core.startswith(n_key_norm):
                    matched_n_key = n_key_norm
                    break

            if matched_n_key is not None:
                if matched_n_key in n_key_index:
                    duplicate_n.setdefault(matched_n_key, [n_key_index[matched_n_key]]).append(p)
                else:
                    n_key_index[matched_n_key] = p

    return exact_index, n_key_index, duplicate_exact, duplicate_n


def find_mask_for_folder(folder_name: str, exact_index: dict, n_key_index: dict):
    """
    根据目标 ID 文件夹名寻找对应 mask。

    数字类：
        0101010265_13mo
        -> 0101010265
        -> T523_0101010265.nii.gz

    N 类：
        N1062_0301010602_0mo
        -> N1062
        -> T523_N1062xxxxxx.nii.gz
    """
    folder_id = strip_age_suffix(folder_name)

    if is_n_subject(folder_id):
        n_key = extract_n_key(folder_id)

        if n_key is None:
            return None, "N类ID解析失败"

        n_key_norm = normalize_alnum(n_key)

        if n_key_norm in n_key_index:
            return n_key_index[n_key_norm], f"N类ID1匹配成功: {n_key}"

        full_norm = normalize_alnum(folder_id)

        if full_norm in exact_index:
            return exact_index[full_norm], f"N类完整ID兜底匹配成功: {full_norm}"

        return None, f"N类mask未找到: ID1={n_key}, full_key={full_norm}"

    folder_norm = normalize_alnum(folder_id)

    if folder_norm in exact_index:
        return exact_index[folder_norm], f"完整ID匹配成功: {folder_norm}"

    return None, f"数字类mask未找到: {folder_norm}"


def copy_mask(src: Path, dst: Path):
    if dst.exists() and not OVERWRITE:
        return "exists_skip"

    if DRY_RUN:
        print(f"[DRY_RUN] copy: {src} -> {dst}")
        return "dry_run"

    shutil.copy2(src, dst)
    return "copied"


def main():
    if not mask_path.exists():
        print(f"[ERROR] mask目录不存在: {mask_path}")
        return

    if not target_subject_root.exists():
        print(f"[ERROR] target_subject_root不存在: {target_subject_root}")
        return

    known_n_keys = collect_known_n_keys(target_subject_root)

    exact_index, n_key_index, duplicate_exact, duplicate_n = build_mask_index(
        mask_dir=mask_path,
        known_n_keys=known_n_keys,
    )

    total_subjects = 0
    success_cases = []
    failed_cases = []
    skipped_existing_cases = []

    for subject_dir in sorted(target_subject_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        total_subjects += 1
        subject_name = subject_dir.name

        matched_mask, match_msg = find_mask_for_folder(
            folder_name=subject_name,
            exact_index=exact_index,
            n_key_index=n_key_index,
        )

        if matched_mask is None:
            failed_cases.append({
                "id": subject_name,
                "reason": match_msg,
            })
            continue

        target_mask = subject_dir / "mask.nii.gz"

        try:
            result = copy_mask(matched_mask, target_mask)

            if result == "exists_skip":
                skipped_existing_cases.append({
                    "id": subject_name,
                    "mask": matched_mask.name,
                    "reason": "目标已有 mask.nii.gz，OVERWRITE=False，所以跳过",
                })
            else:
                success_cases.append({
                    "id": subject_name,
                    "mask": matched_mask.name,
                    "match_msg": match_msg,
                    "target": str(target_mask),
                })

        except Exception as e:
            failed_cases.append({
                "id": subject_name,
                "reason": str(e),
            })

    print("=" * 80)
    print("mask 复制完成")
    print("=" * 80)
    print(f"模式: {'DRY_RUN 预览，不实际复制' if DRY_RUN else '实际复制'}")
    print(f"是否覆盖已有 mask.nii.gz: {OVERWRITE}")
    print(f"mask目录: {mask_path}")
    print(f"目标ID目录: {target_subject_root}")
    print("-" * 80)
    print(f"扫描到ID文件夹: {total_subjects}")
    print(f"成功匹配/复制: {len(success_cases)}")
    print(f"已有mask而跳过: {len(skipped_existing_cases)}")
    print(f"失败: {len(failed_cases)}")
    print("=" * 80)

    print()
    print("[成功ID]")
    if not success_cases:
        print("无")
    else:
        for item in success_cases:
            print(f"{item['id']} | mask={item['mask']} | {item['match_msg']}")

    print()
    print("[已有mask但跳过ID]")
    if not skipped_existing_cases:
        print("无")
    else:
        for item in skipped_existing_cases:
            print(f"{item['id']} | mask={item['mask']} | {item['reason']}")

    print()
    print("[失败ID]")
    if not failed_cases:
        print("无")
    else:
        for item in failed_cases:
            print(f"{item['id']} | 原因: {item['reason']}")

    if duplicate_exact or duplicate_n:
        print()
        print("[警告：mask索引中存在重复匹配]")
        if duplicate_exact:
            print(f"exact重复key数: {len(duplicate_exact)}")
            for key, paths in duplicate_exact.items():
                print(f"  exact key={key}")
                for p in paths:
                    print(f"    {p.name}")

        if duplicate_n:
            print(f"N类重复key数: {len(duplicate_n)}")
            for key, paths in duplicate_n.items():
                print(f"  N key={key}")
                for p in paths:
                    print(f"    {p.name}")

    print()
    print("结束。")


if __name__ == "__main__":
    main()