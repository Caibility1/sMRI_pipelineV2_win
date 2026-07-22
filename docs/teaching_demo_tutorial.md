# sMRI 教学版从零部署教程

本文面向第一次接触 Docker、FreeSurfer 和命令行的使用者。镜像中已经包含 Linux、Python、dcm2niix、FreeSurfer 8.1 和全部运行代码；主机不需要 Conda、Ubuntu、FSL 或 ANTs。

## 1. 流程边界

```text
原始 DICOM
  -> 转换全部序列为 NIfTI
  -> 人工查看候选并选择 T1/可选 T2
  -> 标准 FreeSurfer recon-all
  -> 左、右和合并 pial STL
```

教学版不运行 ACPC、nnU-Net、MoAR-Diff、外部分割、presurf、`infant_recon_all` 或独立 FSL 配准。FreeSurfer 可把合适的 3D T2 用于 pial 优化。

## 2. 电脑与空间

- Windows 10/11 64 位，BIOS/UEFI 虚拟化已开启。
- WSL2 系统能力和 Docker Desktop WSL2 backend。
- 建议 8 核以上 CPU、32 GB 以上内存；16 GB 只能低并发尝试。
- 本流程主要吃 CPU 和内存，不要求 NVIDIA GPU。
- 瘦身镜像实际内容约 14–15 GB；考虑下载缓存和 Docker 虚拟磁盘，建议为 Docker 预留 40–60 GB。
- FreeSurfer 输出和原始数据另计。按约 5–15 GB/受试者预留更稳妥；10 人课程建议数据盘再留 100 GB 以上。

Docker Desktop 可能显示大于实际下载量的“虚拟大小”，不同标签共享相同层时不会重复占用全部空间。

## 3. 开启 WSL2 系统能力

管理员 PowerShell：

```powershell
wsl --install --no-distribution
```

按提示重启。这里不要求安装 Ubuntu；Docker Desktop 使用 WSL2 提供 Linux 容器能力。

## 4. 安装并启动 Docker Desktop

安装 Docker Desktop，选择 WSL2 backend，并等待界面显示 Engine running。以后所有 `docker ...` 命令都在 Windows PowerShell 或 CMD 中执行，不是在 Docker Desktop 镜像页面点 Run。

```powershell
docker version
```

必须同时显示 Client 和 Server。

## 5. 获取镜像、脚本和 license

推荐用 Git 管理启动脚本和文档：

```powershell
git clone --branch demo https://github.com/Caibility1/sMRI_pipelineV2_win.git D:\sMRI_pipeline_demo
cd D:\sMRI_pipeline_demo
docker pull caibility1/smri_pipeline_demo:slim-v2-2026-07-22
```

准备 FreeSurfer `license.txt`，例如：

```powershell
$env:SMRI_FS_LICENSE = "D:\smri_install\license.txt"
.\docker\doctor_demo.ps1 -LicensePath $env:SMRI_FS_LICENSE
```

`setup_demo.ps1` 是可选助手，仅负责检查 Docker、pull 镜像、复制 license 和写本地镜像变量。它不安装算法环境，正常运行也不依赖它：

```powershell
.\setup_demo.ps1 -FsLicenseSource D:\smri_install\license.txt
```

网络出现 `EOF` 时，确认 Docker Desktop 与系统代理/VPN一致后重试 `docker pull`。已下载的镜像层通常会复用，不要先执行 `docker system prune`。

## 6. 不克隆 Git 的直接用法

镜像内已有代码。只有一个批次时，可以直接运行：

```powershell
docker run --rm `
  --mount type=bind,source=D:\MRI_CLASS,target=/data `
  --mount type=bind,source=D:\smri_install\license.txt,target=/licenses/freesurfer/license.txt,readonly `
  --env FS_LICENSE=/licenses/freesurfer/license.txt `
  caibility1/smri_pipeline_demo:slim-v2-2026-07-22 doctor
```

后续把最后的 `doctor` 换成 `reconstruct /data ...` 或 `stl /data ...` 即可。课堂推荐 Git 入口，因为命令更短、文档与版本更容易统一。

## 7. 准备 DICOM

```text
D:\MRI_CLASS\
  0_rawdata\
    001\
      ... DICOM files and series folders ...
    003\
      ... DICOM files and series folders ...
```

受试者 ID 来自文件夹名，`001` 的前导零会保留。DICOM 可有多层序列子目录；不要把多名受试者混在同一文件夹。原始数据不会被删除、移动或写进镜像。

若原始目录名为 `26_MRIdata`：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit `
  --raw-dir 26_MRIdata --dcm2niix-only
```

## 8. 第一阶段：转换全部候选

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --dcm2niix-only
```

这一步转换全部序列，包括重复 T1、NDC、scout 和 motion 序列，但不自动选择。检查：

```text
D:\MRI_CLASS\manifests\00_dicom_series_inventory.csv
D:\MRI_CLASS\manifests\00_dicom_conversion_summary.csv
D:\MRI_CLASS\1_T2toT1\dicom_candidates\001\*.nii.gz
```

用 NIfTI 查看器查看所有 T1 候选。`NDC`、scout、motion 和 derived/secondary 会被标记为 `excluded`，但转换结果仍保留用于核对。

## 9. 第二阶段：视觉 QC 后选择

唯一可信候选可自动标准化：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only
```

多个可信 T1/T2 时按 inventory 的 `series_number` 指定：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only `
  --subject 001 --t1-series 302 --t2-series 401 --force-convert
```

确认每人至少有：

```text
D:\MRI_CLASS\1_T2toT1\data\<ID>\T1.nii.gz
D:\MRI_CLASS\1_T2toT1\data\<ID>\T2.nii.gz   optional
```

## 10. 第三阶段：重建

先跑一人：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --skip-dicom `
  --subject 001 --recon-jobs 1 --recon-threads 4
```

全批次：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --skip-dicom --recon-jobs 1
```

这是同步运行，不是 Slurm。终端会显示开始/完成，日志写入批次目录。32 GB 内存建议 `--recon-jobs 1`；并行 2 例可能造成内存不足和严重换页。重跑同一命令会利用 checkpoint。

## 11. 第四阶段：STL

```powershell
.\bin\smri_3d_print.ps1 D:\MRI_CLASS
```

```text
D:\MRI_CLASS\4_stl\001\lh.pial.stl
D:\MRI_CLASS\4_stl\001\rh.pial.stl
D:\MRI_CLASS\4_stl\001\brain.pial.stl
```

送入切片软件前仍需检查模型尺寸、方向、底座、支撑和网格；pipeline 不决定打印机参数。

## 12. 日志与故障

```text
<BATCH_DIR>\logs\recon\<ID>.log
<BATCH_DIR>\logs\stl\<ID>.log
<BATCH_DIR>\manifests\30_recon_summary.csv
<BATCH_DIR>\manifests\40_stl_summary.csv
```

- `No unambiguous T1-weighted series`：查看 inventory 和 NIfTI，使用 `--t1-series`，不要凭文件数量猜。
- `FreeSurfer license not found`：设置 `SMRI_FS_LICENSE` 或把 license 放到仓库 `resources\software\freesurfer\license.txt`。
- recon 很久：检查日志是否继续增长和 CPU 是否工作。低功耗笔记本可能运行十几小时以上；教学日前必须准备成功结果。
- 镜像更新：代码改动后维护者必须重新 build/push；学生只做 `docker pull`。Git pull 本身不会更新镜像内代码。