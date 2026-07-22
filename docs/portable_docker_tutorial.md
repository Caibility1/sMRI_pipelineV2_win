# Win 单镜像从零部署教程

目标是让新电脑在安装 Docker Desktop 后，不再手动配置 Windows Conda、Ubuntu、FSL、ANTs、FreeSurfer、Workbench、nnU-Net 或 MoAR-Diff。核心环境、模型、模板和代码均从 Docker Hub 下载。

## 1. 主机仍需准备什么

必须：

- Windows 10/11 64 位，BIOS/UEFI 虚拟化已开启。
- WSL2 系统能力。
- Docker Desktop，使用 WSL2 backend，并处于 Engine running 状态。
- FreeSurfer `license.txt`。

按需：

- Git：推荐，用于获得两个短入口和文档；不用 Git 也能直接 `docker run`。
- NVIDIA Windows 驱动：nnU-Net 与 MoAR-Diff 的 GPU 阶段需要。Docker 镜像自带 CUDA/PyTorch 用户态库，但不能替代主机驱动。

不需要：Windows Conda/Miniforge、单独 Ubuntu、WSL 内 FSL/ANTs/FreeSurfer、Workbench 或模型下载。

## 2. 空间与硬件

- Win runtime 镜像实际内容约 36.4 GB；Docker Desktop 可能显示约 90 GB 的虚拟大小。
- 下载、解包和缓存期间，Docker 所在磁盘建议至少空出 100 GB。
- 原始数据、预处理中间结果和 FreeSurfer 输出另计。10 名受试者建议数据盘再留 150 GB 以上。
- Docker Desktop 的虚拟磁盘应迁移到空间充足的数据盘后再 pull 大镜像。
- 推荐 32 GB 内存以上；16 GB 只能低并发尝试。FreeSurfer 设 `--recon-jobs 1`。
- nnU-Net/MoAR-Diff 推荐 NVIDIA 8 GB 以上显存。低显存显卡可能 OOM；CPU 模式通常不适合课堂或批量运行。

## 3. 开启 WSL2

管理员 PowerShell：

```powershell
wsl --install --no-distribution
```

按提示重启。这里需要的是 WSL2 系统能力，不要求安装 Ubuntu。Docker Desktop 自己管理 Linux VM。

## 4. 安装并启动 Docker Desktop

安装 Docker Desktop，选择 WSL2 backend，启动后等待 Engine running。在 Windows PowerShell 检查：

```powershell
docker version
```

必须同时显示 Client 和 Server。Docker 命令在 Windows PowerShell/CMD 运行，不是在 Docker Desktop 的 Images 页面点 Run。

## 5. 获取 Git 入口和镜像

```powershell
git clone https://github.com/Caibility1/sMRI_pipelineV2_win.git D:\sMRI_pipelineV2_win
cd D:\sMRI_pipelineV2_win
docker pull caibility1/smri_pipeline_win:runtime-v2-2026-07-22
```

网络出现 `EOF` 时，统一 Docker Desktop 与系统代理/VPN设置，重新执行同一条 pull。Docker 会复用已经下载完成的层；不要先 prune。

正常流程不运行 `setup_new_machine.ps1`。旧 setup 会建立宿主 Conda 和分体环境，只为历史兼容保留。

## 6. FreeSurfer License

把自己的 `license.txt` 放在稳定位置，例如：

```powershell
$env:SMRI_FS_LICENSE = "D:\smri_install\license.txt"
```

此设置只在当前 PowerShell 窗口有效。永久记录到当前用户：

```powershell
[Environment]::SetEnvironmentVariable(
  "SMRI_FS_LICENSE",
  "D:\smri_install\license.txt",
  "User"
)
```

公开镜像不内置个人 license，两个入口会把该文件只读挂载到容器。

## 7. Doctor

```powershell
cd D:\sMRI_pipelineV2_win
.\docker\doctor_runtime.ps1 `
  -Image caibility1/smri_pipeline_win:runtime-v2-2026-07-22 `
  -LicensePath D:\smri_install\license.txt
```

应看到 Python、PyTorch、FSL `flirt`、ANTs `N4BiasFieldCorrection`、Workbench、FreeSurfer、nnU-Net 模型、MoAR-Diff checkpoint、模板和核心代码均为 `[OK]`。

GPU 另检：

```powershell
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

## 8. 准备批次

```text
D:\data\batch001\
  1_T2toT1\
    data\
      001_180mo\
        T1.nii.gz
        T2.nii.gz   optional
```

也可用 Excel 提供年龄。ID 列可叫 `ID`、`subject_id`、`participant_id` 等；年龄列支持 `age`、`month`、`months`、`mo`、`age_months` 等。Excel 把 `001` 读成数字 `1` 时，匹配逻辑可与文件夹 `001` 对齐，但仍建议把 ID 列设为文本。

## 9. 运行 Preprocessing

陌生数据、有年龄表、无视觉 QC：

```powershell
.\bin\smri_preprocessing.cmd D:\data\batch001 `
  --submit `
  --qc-excel D:\data\age.xlsx `
  --age-source excel `
  --qc-mode all-pass
```

文件夹已带年龄：

```powershell
.\bin\smri_preprocessing.cmd D:\data\batch001 `
  --submit --age-source folder --qc-mode all-pass
```

已有配套 QC 表时使用 `--qc-mode visual`。每个大步骤会打印 `START/COMPLETE` 和日志路径。

## 10. 分割边界与 Postprocessing

当前研究流程需要外部分割结果：

```text
<BATCH_DIR>\6_seg\<ID>\brain.nii.gz
<BATCH_DIR>\6_seg\<ID>\dk-struct.nii.gz
<BATCH_DIR>\6_seg\<ID>\tissue.nii.gz
```

准备后：

```powershell
.\bin\smri_presurf_recon.cmd D:\data\batch001 --submit --recon-jobs 1
```

该命令同步等待，并写入 report、summary 和每例 recon 日志。再次运行会根据关键输出断点续跑。

## 11. 不使用 Git 的直接命令

镜像已经有核心代码。下面可直接运行 preprocessing：

```powershell
docker run --rm --gpus all `
  --mount type=bind,source=D:\data\batch001,target=/data `
  caibility1/smri_pipeline_win:runtime-v2-2026-07-22 `
  preprocess /data --submit --age-source folder --qc-mode all-pass
```

有 Excel 时再只读挂载：

```powershell
--mount type=bind,source=D:\data\age.xlsx,target=/inputs/age.xlsx,readonly
```

并在容器参数中使用 `--qc-excel /inputs/age.xlsx`。postprocessing 还需挂载 license。日常推荐 Git 的 `.cmd` 入口，因为会自动处理这些路径。

## 12. 更新规则

普通用户：

```powershell
git pull --ff-only origin main
docker pull caibility1/smri_pipeline_win:runtime-v2-2026-07-22
```

维护者修改任何镜像内代码后，必须重新 build/push 新标签。Git push 与 Docker push 是两件事；只 push Git 不会改变已发布镜像。新版本验证完成后再通知使用者切换 `SMRI_RUNTIME_IMAGE` 或更新入口默认标签。

## 13. 常见错误

- `docker version` 只有 Client：Docker Desktop 未启动或 engine 未就绪。
- `failed to resolve ... EOF`：registry 网络中断，检查 Docker Desktop 代理/VPN并重试。
- `could not select device driver ... gpu`：主机 NVIDIA 驱动、Docker GPU 支持或显卡不满足；先跑 `nvidia-smi`。
- `FreeSurfer license`：检查 `SMRI_FS_LICENSE` 是否指向真实文件。
- `out of memory`：降低 `--recon-jobs`/`--acpc-jobs`，关闭其他程序，并确认 Docker 内存上限。
- 数据不在 Docker Desktop：这是正常的。数据始终在 Windows，通过 bind mount 暂时映射。
