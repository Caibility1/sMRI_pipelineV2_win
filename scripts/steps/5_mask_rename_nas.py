import posixpath
import shlex
import stat
import sys

try:
    import paramiko
except ImportError:
    print("缺少 paramiko，请先安装：python -m pip install paramiko")
    sys.exit(1)

# =========================
# 集群连接信息
# =========================
HOST = "10.15.49.7"
PORT = 22112
USERNAME = "linmo2025"
PASSWORD = r"E>vq2fgPr9"

# =========================
# 路径配置
# =========================
SRC_ROOT = "/public_bme2/bme-zhanghan/linmo2025/2026/0506_CBCP/0_rawdata"
DEST_ROOT = "/public_bme2/bme-zhanghan/linmo2025/2026/0506_CBCP/1_T2toT1"

# True = 只预演，不真正复制
# False = 真正执行复制
DRY_RUN = False

# 如果目标里原来有 T2，但源目录现在没有 registration/T2_to_T1.nii.gz，
# 是否删除目标里的旧 T2.nii.gz
REMOVE_STALE_T2 = False


def is_dir_attr(attr):
    return stat.S_ISDIR(attr.st_mode)


def remote_exists(sftp, path):
    try:
        sftp.stat(path)
        return True
    except IOError:
        return False


def run_remote(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    return rc, out, err


def q(path):
    return shlex.quote(path)


def main():
    ssh = None
    sftp = None

    copied_t1_only = []
    copied_t1_t2 = []
    missing_t1 = []
    missing_t2 = []
    failed = []

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=HOST,
            port=PORT,
            username=USERNAME,
            password=PASSWORD,
            timeout=30,
        )

        sftp = ssh.open_sftp()

        if not remote_exists(sftp, SRC_ROOT):
            print(f"源目录不存在: {SRC_ROOT}")
            return

        # 创建目标总目录
        if not DRY_RUN:
            rc, out, err = run_remote(ssh, f"mkdir -p {q(DEST_ROOT)}")
            if rc != 0:
                print(f"创建目标目录失败: {DEST_ROOT}")
                print(err)
                return

        # 遍历所有病例目录
        subject_attrs = sftp.listdir_attr(SRC_ROOT)
        subject_dirs = [x for x in subject_attrs if is_dir_attr(x)]

        for attr in subject_dirs:
            subject_id = attr.filename
            src_subject_dir = posixpath.join(SRC_ROOT, subject_id)
            dst_subject_dir = posixpath.join(DEST_ROOT, subject_id)

            src_t1 = posixpath.join(src_subject_dir, "T1.nii.gz")
            src_t2_reg = posixpath.join(src_subject_dir, "registration", "T2_to_T1.nii.gz")

            dst_t1 = posixpath.join(dst_subject_dir, "T1.nii.gz")
            dst_t2 = posixpath.join(dst_subject_dir, "T2.nii.gz")

            has_t1 = remote_exists(sftp, src_t1)
            has_t2_reg = remote_exists(sftp, src_t2_reg)

            if not has_t1:
                missing_t1.append(subject_id)
                continue

            # 只要有 T1，就先准备目标目录
            if not DRY_RUN:
                rc, out, err = run_remote(ssh, f"mkdir -p {q(dst_subject_dir)}")
                if rc != 0:
                    failed.append((subject_id, f"创建目标文件夹失败: {err.strip()}"))
                    continue

            if has_t2_reg:
                cmd = f"cp -f {q(src_t1)} {q(dst_t1)} && cp -f {q(src_t2_reg)} {q(dst_t2)}"
                if DRY_RUN:
                    copied_t1_t2.append(subject_id)
                else:
                    rc, out, err = run_remote(ssh, cmd)
                    if rc == 0:
                        copied_t1_t2.append(subject_id)
                    else:
                        failed.append((subject_id, f"复制 T1/T2 失败: {err.strip()}"))
            else:
                # 只有 T1
                cmd = f"cp -f {q(src_t1)} {q(dst_t1)}"
                if REMOVE_STALE_T2:
                    cmd += f" ; rm -f {q(dst_t2)}"

                if DRY_RUN:
                    copied_t1_only.append(subject_id)
                    missing_t2.append(subject_id)
                else:
                    rc, out, err = run_remote(ssh, cmd)
                    if rc == 0:
                        copied_t1_only.append(subject_id)
                        missing_t2.append(subject_id)
                    else:
                        failed.append((subject_id, f"复制 T1 失败: {err.strip()}"))

        # ===== 输出总结 =====
        print("=" * 80)
        print("处理完成")
        print("=" * 80)
        print(f"模式: {'预演(DRY_RUN=True)' if DRY_RUN else '实际复制(DRY_RUN=False)'}")
        print(f"源目录: {SRC_ROOT}")
        print(f"目标目录: {DEST_ROOT}")
        print(f"扫描到的病例文件夹数: {len(subject_dirs)}")
        print()

        print(f"[1] 成功复制 T1 + 配准后T2: {len(copied_t1_t2)}")
        print(f"[2] 仅复制 T1（缺配准后T2）: {len(copied_t1_only)}")
        print(f"[3] 缺 T1，已跳过: {len(missing_t1)}")
        print(f"[4] 缺配准后T2: {len(missing_t2)}")
        print(f"[5] 复制失败: {len(failed)}")
        print()

        if missing_t1:
            print("缺 T1 的病例：")
            for x in missing_t1:
                print(f"  {x}")
            print()

        if missing_t2:
            print("缺 registration/T2_to_T1.nii.gz 的病例：")
            for x in missing_t2:
                print(f"  {x}")
            print()

        if failed:
            print("复制失败详情：")
            for subject_id, reason in failed:
                print(f"  {subject_id} -> {reason}")
            print()

        print("结束。")

    finally:
        if sftp is not None:
            sftp.close()
        if ssh is not None:
            ssh.close()


if __name__ == "__main__":
    main()