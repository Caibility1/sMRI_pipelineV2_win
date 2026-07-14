import os
import re
import shutil
from pathlib import Path

# =========================
# 配置区
# =========================
source_root = Path(r"\\10.19.138.153\data2\SHCHInfant_YH\1_NII")
target_root = Path(r"\\10.19.138.153\data2\SHCHInfant_YH\2_Processing\1_sMRI\1_sMRI_data")


#! 本脚本只用于SHCHInfant_YH上海儿童医院数据1_Nii到2_preprocessing的1_smri中。
# True = 如果目标里的 T1/T2 已存在，先删再复制，避免旧内容残留
# False = 如果已存在就跳过
OVERWRITE_EXISTING = True

# True = 只预演，不真正复制
DRY_RUN = False


def extract_sub_id(folder_name: str):
    """
    从类似 'sub001-20250414-JINJIAN' 中提取 'sub001'
    只认开头的 sub+数字
    """
    m = re.match(r"^(sub\d+)", folder_name, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def safe_copy_dir(src: Path, dst: Path):
    """
    复制整个文件夹。
    """
    if dst.exists():
        if OVERWRITE_EXISTING:
            shutil.rmtree(dst)
        else:
            return "skipped_exists"

    if not DRY_RUN:
        shutil.copytree(src, dst)

    return "copied"


def safe_copy_file(src: Path, dst: Path):
    """
    复制单个文件。
    """
    if dst.exists():
        if OVERWRITE_EXISTING:
            if not DRY_RUN:
                dst.unlink()
        else:
            return "skipped_exists"

    if not DRY_RUN:
        shutil.copy2(src, dst)

    return "copied"


def main():
    if not source_root.exists():
        print(f"[错误] 源目录不存在: {source_root}")
        return

    target_root.mkdir(parents=True, exist_ok=True)

    success_cases = []
    failed_parse = []
    missing_t1 = []
    missing_t2 = []
    copy_errors = []

    all_case_folders = [p for p in source_root.iterdir() if p.is_dir()]

    print(f"源目录: {source_root}")
    print(f"目标目录: {target_root}")
    print(f"病例文件夹数量: {len(all_case_folders)}")
    print(f"模式: {'DRY_RUN 预演' if DRY_RUN else '实际复制'}")
    print("-" * 80)

    for case_folder in all_case_folders:
        src_case_name = case_folder.name
        sub_id = extract_sub_id(src_case_name)

        if sub_id is None:
            failed_parse.append(src_case_name)
            print(f"[跳过] 无法解析ID: {src_case_name}")
            continue

        dst_case_folder = target_root / sub_id
        t1_src = case_folder / "T1"
        t2_src = case_folder / "T2"

        ds_store_src = None
        for item in case_folder.iterdir():
            if item.is_file() and item.name.lower() == ".ds_store":
                ds_store_src = item
                break

        dst_case_folder.mkdir(parents=True, exist_ok=True)

        case_ok = True

        # 复制 T1
        if t1_src.exists() and t1_src.is_dir():
            try:
                result = safe_copy_dir(t1_src, dst_case_folder / "T1")
                print(f"[{'复制' if result == 'copied' else '跳过'}] {src_case_name} / T1  ->  {sub_id}\\T1")
            except Exception as e:
                case_ok = False
                copy_errors.append((src_case_name, "T1", str(e)))
                print(f"[失败] {src_case_name} / T1 复制失败: {e}")
        else:
            case_ok = False
            missing_t1.append(src_case_name)
            print(f"[缺失] {src_case_name} 中没有 T1 文件夹")

        # 复制 T2
        if t2_src.exists() and t2_src.is_dir():
            try:
                result = safe_copy_dir(t2_src, dst_case_folder / "T2")
                print(f"[{'复制' if result == 'copied' else '跳过'}] {src_case_name} / T2  ->  {sub_id}\\T2")
            except Exception as e:
                case_ok = False
                copy_errors.append((src_case_name, "T2", str(e)))
                print(f"[失败] {src_case_name} / T2 复制失败: {e}")
        else:
            case_ok = False
            missing_t2.append(src_case_name)
            print(f"[缺失] {src_case_name} 中没有 T2 文件夹")

        # 复制 .DS_Store（如果有）
        if ds_store_src is not None:
            try:
                result = safe_copy_file(ds_store_src, dst_case_folder / ds_store_src.name)
                print(f"[{'复制' if result == 'copied' else '跳过'}] {src_case_name} / {ds_store_src.name}  ->  {sub_id}\\{ds_store_src.name}")
            except Exception as e:
                copy_errors.append((src_case_name, ds_store_src.name, str(e)))
                print(f"[失败] {src_case_name} / {ds_store_src.name} 复制失败: {e}")

        if case_ok:
            success_cases.append((src_case_name, sub_id))

        print("-" * 80)

    # 总结
    print("\n")
    print("=" * 80)
    print("处理总结")
    print("=" * 80)

    print(f"成功处理病例数: {len(success_cases)}")
    for old_name, sub_id in success_cases:
        print(f"  {old_name}  ->  {sub_id}")

    print(f"\n无法解析ID的文件夹数: {len(failed_parse)}")
    for name in failed_parse:
        print(f"  {name}")

    print(f"\n缺少T1的文件夹数: {len(missing_t1)}")
    for name in missing_t1:
        print(f"  {name}")

    print(f"\n缺少T2的文件夹数: {len(missing_t2)}")
    for name in missing_t2:
        print(f"  {name}")

    print(f"\n复制报错数: {len(copy_errors)}")
    for case_name, item_name, err in copy_errors:
        print(f"  {case_name} / {item_name} : {err}")


if __name__ == "__main__":
    main()