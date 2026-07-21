# sMRI 教学版从零部署教程

本文面向第一次接触 Docker、FreeSurfer 和命令行的使用者。教学版处理链为：

```text
原始 DICOM
  -> dcm2niix 转换并识别 T1/T2
  -> 可选的 T2-to-T1 配准展示
  -> 标准 FreeSurfer recon-all
  -> 左/右/合并 pial 表面 STL
```

教学版不运行 ACPC、nnU-Net 去颅骨、MoAR-Diff 去噪、外部分割、presurf 或
`infant_recon_all`。标准 `recon-all` 会自行完成去颅骨、体积分割和皮层表面重建，
不需要月龄表或 CBCP_QC 表。

## 1. 电脑要求

- Windows 10/11 64 位，支持并已开启 CPU 虚拟化。
- Docker Desktop 使用 WSL2 backend。
- 建议 8 核以上 CPU、32 GB 以上内存。
- 建议至少预留 150 GB，最好 200 GB 可用磁盘空间。
- 本流程不需要 NVIDIA GPU；标准 `recon-all` 主要使用 CPU。
- 每名受试者的重建可能持续数小时到一天以上，低功耗笔记本可能更久。

第一版教学镜像复用现有完整镜像，所以包含一些本流程暂时不用的研究模型，体积较大。
这是为了减少一周内重新验证底层工具的风险，后续可以再制作瘦身镜像。

## 2. 安装 WSL2 系统能力

以管理员身份打开 PowerShell：

```powershell
wsl --install --no-distribution
```

按提示重启。这里不要求另外安装 Ubuntu。Docker Desktop 自己使用 WSL2 的 Linux
虚拟化能力。BIOS 虚拟化是 WSL2 和 Linux 容器运行所需的硬件支持，不是 MRI 算法步骤。

## 3. 安装并启动 Docker Desktop

1. 安装 Docker Desktop。
2. 第一次启动时选择 WSL2 backend。
3. 等待界面显示 Docker Engine 正常运行。
4. PowerShell 中检查：

```powershell
docker version
```

命令必须同时显示 Client 和 Server。只有 Client 通常表示 Docker Desktop 尚未启动。

## 4. 获取代码和 license

代码仓库只提供入口、文档和脚本；实际算法代码也已烘焙进镜像。克隆仓库：

```powershell
cd D:\
git clone https://github.com/Caibility1/sMRI_pipeline_demo.git
cd D:\sMRI_pipeline_demo
```

准备课程统一使用的 FreeSurfer `license.txt`，例如放在：

```text
D:\smri_install\license.txt
```

不要把 license 提交到公开 Git 仓库。

## 5. 一键拉取和检查镜像

```powershell
cd D:\sMRI_pipeline_demo
.\setup_demo.ps1 -FsLicenseSource D:\smri_install\license.txt
```

该脚本会：

1. 检查 WSL2 系统能力和 Docker Desktop。
2. 将 license 复制到仓库约定位置。
3. 拉取 `caibility1/smri_pipeline_demo:latest`。
4. 在容器内检查 `dcm2niix`、FSL、`recon-all` 和 `mris_convert`。

它不会安装 Windows Conda，也不会给用户的 WSL 安装 Ubuntu/FSL/FreeSurfer。

网络不稳出现 `EOF` 时，保持 Docker Desktop 和代理/VPN 状态一致，再重复运行同一命令。
脚本本身会自动尝试三次。镜像层下载可断点复用，不必删除已下载内容。

## 6. 准备数据目录

每个受试者一个文件夹，受试者 ID 直接来自文件夹名，前导零会保留：

```text
D:\MRI_CLASS\
  0_rawdata\
    001\
      ... DICOM files and series folders ...
    003\
      ... DICOM files and series folders ...
```

若原始目录已有其他名字，例如 `<BATCH_DIR>\26_MRIdata\<ID>`，不需要复制或重命名，
使用相对路径参数：

```powershell
.\bin\smri_reconstruction.ps1 <BATCH_DIR> --submit `
  --raw-dir 26_MRIdata --dcm2niix-only
```

DICOM 可以有多层序列子目录。不要把多名受试者的 DICOM 混在同一个受试者文件夹。
原始 DICOM 不会被删除或移动。`dcm2niix -ba y` 会减少 JSON sidecar 中的识别信息，
但原始 DICOM 仍可能包含个人信息，不应上传到公开仓库或镜像。

## 7. 先只转换并核对序列

真实数据第一次运行时，建议先停在转换阶段：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --dcm2niix-only
```

这条命令转换每个受试者的全部序列，包括多个 T1 候选；遇到重复扫描不会失败，也不会
提前决定哪个 T1 最好。检查：

```text
D:\MRI_CLASS\manifests\00_dicom_series_inventory.csv
D:\MRI_CLASS\manifests\00_dicom_conversion_summary.csv
D:\MRI_CLASS\1_T2toT1\dicom_candidates\001\*.nii.gz
```

此时 inventory 的 `selected` 列必须为空，`1_T2toT1\data` 中也不会自动生成标准化
T1/T2。用本地 NIfTI 查看器检查所有标记为 `t1` 的候选。`NDC`、scout、motion curve
和 derived/secondary 会保留转换结果，但分类为 `excluded`，不会在下一阶段自动入选。

视觉 QC 后，先让唯一候选受试者完成标准化：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only
```

若某名受试者仍有多个可信 T1，根据 inventory 中的 `series_number` 逐名指定：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only `
  --subject 001 --t1-series 302 --t2-series 401 --force-convert
```

最后确认每名受试者都有：

```text
D:\MRI_CLASS\1_T2toT1\data\<ID>\T1.nii.gz
D:\MRI_CLASS\1_T2toT1\data\<ID>\T2.nii.gz   optional
```

## 8. 启动完整重建

转换结果已确认后：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --skip-dicom --recon-jobs 1
```

先验证单名受试者时，`--subject` 会同时限制 DICOM 转换和 recon：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --skip-dicom `
  --subject 001 --recon-jobs 1 --recon-threads 4
```

若希望额外展示 FSL 刚体配准：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --skip-dicom `
  --registration --recon-jobs 1
```

`--registration` 的结果用于教学查看，不作为 FreeSurfer 的输入。FreeSurfer 会自己处理
可选 T2。内存 32 GB 的普通电脑建议 `--recon-jobs 1`；只有内存和散热充分时才尝试 2。

该命令是同步运行，不是 Slurm 提交。PowerShell 窗口会持续显示：

```text
[001] recon-all started
[001] recon-all complete
```

关闭窗口或关机会中断当前进程；重新执行同一命令会使用已有输出续跑。

## 9. 导出 STL

recon 完成后：

```powershell
.\bin\smri_3d_print.ps1 D:\MRI_CLASS
```

输出：

```text
D:\MRI_CLASS\4_stl\001\lh.pial.stl
D:\MRI_CLASS\4_stl\001\rh.pial.stl
D:\MRI_CLASS\4_stl\001\brain.pial.stl
```

`brain.pial.stl` 是左右半球合并文件，仍可能包含两个彼此分离的封闭网格。送入切片软件
前需要检查模型尺寸、朝向、底座、支撑和网格修复；本 pipeline 不自动决定打印机参数。

## 10. 日志、汇总和断点续跑

```text
<BATCH_DIR>\logs\recon\<ID>.log
<BATCH_DIR>\logs\stl\<ID>.log
<BATCH_DIR>\manifests\30_recon_summary.csv
<BATCH_DIR>\manifests\40_stl_summary.csv
```

完成的 DICOM、recon 和 STL 会被 checkpoint 跳过。失败受试者会单独记录，其他受试者
仍可继续。不要手动删除 `3_recon` 中的部分结果；先保留日志并直接重跑。

## 11. 常见问题

**No unambiguous T1-weighted series was found**

检查 inventory 的 SeriesDescription/ProtocolName。必要时确认扫描协议后用
`--t1-series` 指定，不能仅凭文件数量猜测。

**Docker pull EOF**

这是 registry 网络连接中断，不是 MRI 数据问题。启动 Docker Desktop，在 Docker Desktop
中配置与系统一致的代理后重试。不要反复执行 `docker system prune`。

**FreeSurfer license not found**

重新运行 `setup_demo.ps1 -FsLicenseSource <license.txt>`，或设置环境变量
`SMRI_FS_LICENSE` 指向 license 的绝对路径。

**recon 很久没有结束**

这是标准重建的常见情况。检查 `logs\recon\<ID>.log` 是否仍有新内容，以及任务管理器中
CPU 是否在工作。教学日前应提前全量跑完，不应把当天打印成功依赖于现场重建速度。
