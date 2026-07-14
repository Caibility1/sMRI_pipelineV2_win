from pathlib import Path
import re
import subprocess
from collections import defaultdict

# =========================
# NAS 登录配置
# =========================
NAS_SHARE = r"\\10.19.136.231\002"
NAS_USERNAME = r"linm"
NAS_PASSWORD = r"l9cG5/g{"

# =========================
# 路径配置
# =========================
PATH_A = Path(r"\\10.19.136.231\002\CBCP\CBCP_MRI\DataGiven\20260506\1_T2toT1")
PATH_B = Path(r"\\10.19.136.231\002\CBCP\CBCP_MRI\5_release\CBCP_release_v3.0\T1")


def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return result.returncode, result.stdout, result.stderr


def connect_nas():
    # 先断开旧连接，避免 Windows 1219 凭据冲突
    run_cmd(["net", "use", NAS_SHARE, "/delete", "/y"])
    code, out, err = run_cmd(["net", "use", NAS_SHARE, NAS_PASSWORD, f"/user:{NAS_USERNAME}"])
    if code != 0:
        raise RuntimeError(f"NAS 登录失败\nstdout:\n{out}\nstderr:\n{err}")


def disconnect_nas():
    run_cmd(["net", "use", NAS_SHARE, "/delete", "/y"])


def strip_ext(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".nii.gz"):
        return name[:-7]
    if lower.endswith(".nii"):
        return name[:-4]
    return name


def normalize_id(value):
    """
    用于比较的统一 ID：
    - 去掉 .nii/.nii.gz
    - 去掉末尾 _xxmo
    - 若含字母：保留字母数字，去掉分隔符，统一大写
    - 若纯数字：只保留数字，并去掉前导0
    """
    if value is None:
        return None

    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None

    s = strip_ext(s)
    s = re.sub(r"_(\d+(?:\.\d+)?)mo$", "", s, flags=re.IGNORECASE)

    if re.search(r"[A-Za-z]", s):
        s = re.sub(r"[^A-Za-z0-9]", "", s).upper()
        return s if s else None

    digits = re.sub(r"\D", "", s)
    if not digits:
        return None

    digits = digits.lstrip("0")
    return digits if digits else "0"


def collect_A_ids(path_a: Path):
    """
    A 侧：只看 A 路径直接下一层
    假设这里每一个直接子项就是一个 ID（通常是文件夹）
    返回：
    - a_map: norm_id -> raw_name
    """
    a_map = {}

    for p in path_a.iterdir():
        raw_name = p.name
        norm_id = normalize_id(raw_name)
        if norm_id is None:
            continue

        # 如果重复，保留第一次看到的原名即可
        if norm_id not in a_map:
            a_map[norm_id] = raw_name

    return a_map


def collect_B_ids(path_b: Path):
    """
    B 侧：只看 T1 下每个 site 的直接下一层
    排除名字里含 BCP 的 site
    返回：
    - b_map: norm_id -> {"raw_names": set(...), "sites": set(...)}
    - site_names: 纳入比较的 site 列表
    """
    b_map = defaultdict(lambda: {"raw_names": set(), "sites": set()})

    site_dirs = [p for p in path_b.iterdir() if p.is_dir() and "BCP" not in p.name.upper()]
    site_dirs = sorted(site_dirs, key=lambda x: x.name)

    for site_dir in site_dirs:
        site_name = site_dir.name
        print(f"扫描 B 侧 site: {site_name}")

        for p in site_dir.iterdir():
            raw_name = p.name
            norm_id = normalize_id(raw_name)
            if norm_id is None:
                continue

            b_map[norm_id]["raw_names"].add(raw_name)
            b_map[norm_id]["sites"].add(site_name)

    return b_map, [x.name for x in site_dirs]


def main():
    try:
        print("正在登录 NAS ...")
        connect_nas()
        print("NAS 登录成功。")

        if not PATH_A.exists():
            print(f"A 路径不存在或无权限访问：{PATH_A}")
            return

        if not PATH_B.exists():
            print(f"B 路径不存在或无权限访问：{PATH_B}")
            return

        print("开始扫描 A 路径 ...")
        a_map = collect_A_ids(PATH_A)

        print("开始扫描 B 路径 ...")
        b_map, site_names = collect_B_ids(PATH_B)

        A = set(a_map.keys())
        B = set(b_map.keys())

        a_only = A - B
        b_only = B - A

        print("\n" + "=" * 100)
        print("比较完成（只输出不一样的ID）")
        print("=" * 100)
        print(f"A 唯一ID数: {len(A)}")
        print(f"B 唯一ID数: {len(B)}")
        print(f"A 有但 B 没有: {len(a_only)}")
        print(f"B 有但 A 没有: {len(b_only)}")
        print(f"纳入比较的 B 侧 site: {site_names}")
        print("=" * 100)

        print("\nA 有但 B 没有的 ID：")
        if not a_only:
            print("  无")
        else:
            for norm_id in sorted(a_only):
                print(f"  {a_map[norm_id]}")

        print("\nB 有但 A 没有的 ID：")
        if not b_only:
            print("  无")
        else:
            for norm_id in sorted(b_only):
                raw_names = sorted(b_map[norm_id]["raw_names"])
                sites = sorted(b_map[norm_id]["sites"])

                # 一般 raw_names 只会有一个；如果多个，也一起打印
                if len(raw_names) == 1:
                    print(f"  {raw_names[0]}    [site: {', '.join(sites)}]")
                else:
                    print(f"  {norm_id}    [site: {', '.join(sites)}]    [raw_names: {raw_names}]")

    finally:
        print("\n正在断开 NAS ...")
        disconnect_nas()
        print("NAS 已断开。")


if __name__ == "__main__":
    main()