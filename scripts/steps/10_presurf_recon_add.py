import paramiko
import sys
import time


# =========================
# SSH 配置
# =========================

HOST = "10.15.49.7"
PORT = 22112
USERNAME = "linmo2025"
PASSWORD = "E>vq2fgPr9"


# =========================
# 远程数据路径配置
# 换数据集时一般只改 BASE_DIR
# =========================

BASE_DIR = "/public_bme2/bme-zhanghan/linmo2025/2026/0507_ASD"

DIR8_NAME = "8_presurf"
DIR9_NAME = "9_surf_recon"
FINAL_NAME = "10_final"


REMOTE_SCRIPT = f"""
import os
import subprocess
from pathlib import Path


BASE_DIR = Path("{BASE_DIR}")
DIR8 = BASE_DIR / "{DIR8_NAME}"
DIR9 = BASE_DIR / "{DIR9_NAME}"
FINAL = BASE_DIR / "{FINAL_NAME}"


def check_dir(path: Path, name: str):
    if not path.is_dir():
        raise FileNotFoundError(f"{{name}} 不存在或不是文件夹：{{path}}")


def list_id_dirs(path: Path):
    return sorted([p.name for p in path.iterdir() if p.is_dir()])


def copy_contents(src: Path, dst: Path):
    '''
    把 src 目录下的所有内容复制到 dst 目录下。
    注意是复制 src/. 到 dst/，不会变成 dst/src_name/。
    使用 cp -a，保留文件属性，并且可以复制大文件夹。
    '''
    dst.mkdir(parents=True, exist_ok=True)

    cmd = [
        "cp",
        "-a",
        str(src) + "/.",
        str(dst) + "/"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    return result.returncode, result.stdout, result.stderr


def main():
    check_dir(BASE_DIR, "BASE_DIR")
    check_dir(DIR8, "8_presurf")
    check_dir(DIR9, "9_surf_recon")

    FINAL.mkdir(parents=True, exist_ok=True)

    ids8 = set(list_id_dirs(DIR8))
    ids9 = set(list_id_dirs(DIR9))

    common_ids = sorted(ids8 & ids9)
    only_in_8 = sorted(ids8 - ids9)
    only_in_9 = sorted(ids9 - ids8)

    success_ids = []
    failed_ids = []

    print("========== 路径信息 ==========")
    print(f"BASE_DIR: {{BASE_DIR}}")
    print(f"8_presurf: {{DIR8}}")
    print(f"9_surf_recon: {{DIR9}}")
    print(f"10_final: {{FINAL}}")
    print("")

    print("========== ID 检查 ==========")
    print(f"8_presurf ID 数量：{{len(ids8)}}")
    print(f"9_surf_recon ID 数量：{{len(ids9)}}")
    print(f"共同 ID 数量：{{len(common_ids)}}")
    print(f"只在 8_presurf 中存在：{{len(only_in_8)}}")
    print(f"只在 9_surf_recon 中存在：{{len(only_in_9)}}")
    print("")

    for case_id in common_ids:
        src8 = DIR8 / case_id
        src9 = DIR9 / case_id
        dst = FINAL / case_id

        try:
            dst.mkdir(parents=True, exist_ok=True)

            code8, out8, err8 = copy_contents(src8, dst)
            if code8 != 0:
                failed_ids.append((case_id, "复制 8_presurf 内容失败", err8.strip()))
                print(f"[FAIL] {{case_id}}: 复制 8_presurf 内容失败")
                if err8.strip():
                    print(err8.strip())
                continue

            code9, out9, err9 = copy_contents(src9, dst)
            if code9 != 0:
                failed_ids.append((case_id, "复制 9_surf_recon 内容失败", err9.strip()))
                print(f"[FAIL] {{case_id}}: 复制 9_surf_recon 内容失败")
                if err9.strip():
                    print(err9.strip())
                continue

            success_ids.append(case_id)
            print(f"[OK] {{case_id}}: 已合并到 10_final")

        except Exception as e:
            failed_ids.append((case_id, "Python 异常", repr(e)))
            print(f"[FAIL] {{case_id}}: {{repr(e)}}")

    print("")
    print("========== 处理完成 ==========")
    print(f"一共检查 8_presurf ID 数量：{{len(ids8)}}")
    print(f"一共检查 9_surf_recon ID 数量：{{len(ids9)}}")
    print(f"共同 ID 数量：{{len(common_ids)}}")
    print(f"成功合并 ID 数量：{{len(success_ids)}}")
    print(f"失败 ID 数量：{{len(failed_ids)}}")
    print(f"只在 8_presurf 中存在的 ID 数量：{{len(only_in_8)}}")
    print(f"只在 9_surf_recon 中存在的 ID 数量：{{len(only_in_9)}}")

    if only_in_8:
        print("")
        print("========== 只在 8_presurf 中存在的 ID ==========")
        for case_id in only_in_8:
            print(case_id)

    if only_in_9:
        print("")
        print("========== 只在 9_surf_recon 中存在的 ID ==========")
        for case_id in only_in_9:
            print(case_id)

    if failed_ids:
        print("")
        print("========== 失败 ID 列表 ==========")
        for case_id, reason, detail in failed_ids:
            print(f"{{case_id}}\\t{{reason}}\\t{{detail}}")


if __name__ == "__main__":
    main()
"""


def run_remote_script():
    print("========== 正在连接集群 ==========")
    print(f"{USERNAME}@{HOST}:{PORT}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=HOST,
            port=PORT,
            username=USERNAME,
            password=PASSWORD,
            timeout=20,
            banner_timeout=20,
            auth_timeout=20,
        )
    except Exception as e:
        print(f"[ERROR] SSH 连接失败：{repr(e)}")
        sys.exit(1)

    print("[OK] SSH 已连接")
    print("========== 开始在集群上执行合并 ==========")

    command = "python3 - <<'PY_REMOTE_SCRIPT'\n" + REMOTE_SCRIPT + "\nPY_REMOTE_SCRIPT\n"

    stdin, stdout, stderr = ssh.exec_command(command)

    # 实时输出远程结果
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            data = stdout.channel.recv(4096).decode("utf-8", errors="ignore")
            print(data, end="")
        if stderr.channel.recv_stderr_ready():
            data = stderr.channel.recv_stderr(4096).decode("utf-8", errors="ignore")
            print(data, end="")
        time.sleep(0.2)

    # 读完剩余输出
    remaining_out = stdout.read().decode("utf-8", errors="ignore")
    remaining_err = stderr.read().decode("utf-8", errors="ignore")

    if remaining_out:
        print(remaining_out, end="")
    if remaining_err:
        print(remaining_err, end="")

    exit_status = stdout.channel.recv_exit_status()

    ssh.close()

    print("")
    print("========== 远程任务结束 ==========")
    print(f"远程退出码：{exit_status}")

    if exit_status != 0:
        print("[ERROR] 远程脚本执行失败，请看上面的报错。")
        sys.exit(exit_status)
    else:
        print("[OK] 10_final 合并完成。")


if __name__ == "__main__":
    run_remote_script()