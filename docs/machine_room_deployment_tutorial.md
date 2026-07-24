# 机房部署与课堂运行教程

本教程用于 Windows 机房部署 sMRI 教学 Demo。所有命令均在 **Windows PowerShell** 中执行，不在 Docker Desktop 的镜像页面中执行，也不需要进入 Ubuntu 终端。

教学 Demo 使用标准 FreeSurfer `recon-all`，主要消耗 CPU、内存和时间，不依赖 NVIDIA GPU。主机不需要另装 Conda、Python、FSL、ANTs 或 FreeSurfer。

## 0. 课前硬件与权限门槛

- Windows 10 22H2（build 19045）或 Windows 11 23H2（build 22631）及以上。
- x86-64 CPU，BIOS/UEFI 中已开启 Intel VT-x 或 AMD-V/SVM。
- 建议 32 GB 内存，64 GB 更稳；16 GB 不作为完整重建配置。
- 每台机器至少留出 80 GB 可用空间，建议 100 GB；公开镜像本地展开约 41 GB。
- 需要一次管理员权限来启用 WSL2；Docker Desktop 可按用户安装。
- 有还原卡或非持久桌面时，管理员必须保留 Docker/WSL 数据，否则重启后镜像会丢失。

微软说明 `wsl --install` 需要管理员 PowerShell 和重启：<https://learn.microsoft.com/en-us/windows/wsl/install>。Docker Desktop 当前要求 WSL 2.1.5 或更高，并要求 BIOS/UEFI 硬件虚拟化：<https://docs.docker.com/desktop/setup/install/windows-install/>。

## 1. 管理员检查机房电脑

在 **管理员 PowerShell** 中执行：

```powershell
Get-ComputerInfo |
  Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture

Get-CimInstance Win32_Processor |
  Select-Object Name, VirtualizationFirmwareEnabled,
    SecondLevelAddressTranslationExtensions, VMMonitorModeExtensions

Get-CimInstance Win32_ComputerSystem |
  Select-Object Manufacturer, Model,
    @{Name="RAM_GB";Expression={[math]::Round($_.TotalPhysicalMemory / 1GB)}}
```

`VirtualizationFirmwareEnabled` 必须为 `True`。如果为 `False`，PowerShell 无法替代 BIOS 设置，必须请机房管理员开启 VT-x/AMD-V/SVM。

## 2. 管理员启用 WSL2

优先执行：

```powershell
wsl --install --no-distribution
Restart-Computer
```

若旧版 Windows 不识别 `--no-distribution`：

```powershell
wsl --install
Restart-Computer
```

重启后，在普通 PowerShell 中检查：

```powershell
wsl --update
wsl --set-default-version 2
wsl --version
wsl --status
```

Docker Desktop 自带 `docker-desktop` 发行版，本 Demo 不要求另外配置 Ubuntu。

## 3. 安装并启动 Docker Desktop

有网络和 `winget` 时：

```powershell
winget install --id Docker.DockerDesktop -e `
  --accept-package-agreements --accept-source-agreements
```

使用提前下载的离线安装包时，在安装包所在目录执行：

```powershell
Start-Process ".\Docker Desktop Installer.exe" -Wait `
  -ArgumentList "install","--user","--accept-license"
```

从开始菜单启动 Docker Desktop，等待显示 **Engine running**。不需要在 Images 页面点 `Run`。随后检查：

```powershell
docker version
docker info --format "OSType={{.OSType}} CPUs={{.NCPU}} Memory={{.MemTotal}}"
```

`OSType` 应为 `linux`。Docker 官方说明 Docker 命令可直接从 Windows 终端调用，并且不要求安装特定 Ubuntu 发行版：<https://docs.docker.com/desktop/features/wsl/>。

若 C 盘空间紧张，安装镜像前在 Docker Desktop 中打开 `Settings -> Resources -> Advanced -> Disk image location`，把位置改到数据盘。

## 4. 安装 NIfTI 查看器

教师或管理员安装 Windows 版 ITK-SNAP。它只用于打开 `1_T2toT1\dicom_candidates\<ID>\*.nii.gz` 做人工 QC，不参与算法运行。

## 5A. 首选：离线部署

教师提前生成离线包：

```powershell
cd D:\master\QC\sMRI_pipelineV2_win
git switch demo
git pull --ff-only origin demo
docker pull caibility1/smri_pipeline_demo:slim-v2.3-2026-07-24
Set-ExecutionPolicy -Scope Process Bypass -Force

.\docker\export_demo_offline_bundle.ps1 `
  -Destination D:\smri_demo_offline `
  -LicensePath D:\smri_install\license.txt
```

把整个 `D:\smri_demo_offline` 复制到移动硬盘。学生电脑导入：

```powershell
New-Item -ItemType Directory -Force D:\sMRI_pipeline_demo | Out-Null
Expand-Archive `
  -Path E:\smri_demo_offline\smri_pipeline_demo_code.zip `
  -DestinationPath D:\sMRI_pipeline_demo -Force

docker load -i `
  E:\smri_demo_offline\caibility1_smri_pipeline_demo_slim-v2.3-2026-07-24.tar

New-Item -ItemType Directory -Force `
  D:\sMRI_pipeline_demo\resources\software\freesurfer | Out-Null
Copy-Item E:\smri_demo_offline\license.txt `
  D:\sMRI_pipeline_demo\resources\software\freesurfer\license.txt -Force
```

把 `E:` 改成移动硬盘的实际盘符。

## 5B. 备用：在线部署

有稳定网络时：

```powershell
winget install --id Git.Git -e `
  --accept-package-agreements --accept-source-agreements

git clone --branch demo `
  https://github.com/Caibility1/sMRI_pipelineV2_win.git `
  D:\sMRI_pipeline_demo

docker pull caibility1/smri_pipeline_demo:slim-v2.3-2026-07-24

New-Item -ItemType Directory -Force `
  D:\sMRI_pipeline_demo\resources\software\freesurfer | Out-Null
Copy-Item D:\smri_install\license.txt `
  D:\sMRI_pipeline_demo\resources\software\freesurfer\license.txt -Force
```

课堂当天不建议依赖此路径；GitHub 或 Docker Hub 网络失败会直接中断部署。

## 6. 部署自检

以下命令及后续 pipeline 命令都在 **普通 Windows PowerShell** 中执行：

```powershell
cd D:\sMRI_pipeline_demo
Set-ExecutionPolicy -Scope Process Bypass -Force

.\docker\doctor_demo.ps1 `
  -Image caibility1/smri_pipeline_demo:slim-v2.3-2026-07-24 `
  -LicensePath D:\sMRI_pipeline_demo\resources\software\freesurfer\license.txt
```

`python3`、`dcm2niix`、`recon-all`、`mris_convert` 和 license 均显示 `[OK]` 才进入数据处理。

## 7. 准备数据

```text
D:\MRI_CLASS\
  0_rawdata\
    001\
      ... DICOM files ...
    003\
      ... DICOM files ...
```

每名学生只放自己的一名受试者。不要把不同人的 DICOM 混在同一个 ID 目录中。

## 8. 第一段：全部 DICOM 转 NIfTI

```powershell
cd D:\sMRI_pipeline_demo
Set-ExecutionPolicy -Scope Process Bypass -Force
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --dcm2niix-only
```

查看候选和清单：

```powershell
Import-Csv D:\MRI_CLASS\manifests\00_dicom_series_inventory.csv |
  Format-Table subject,series_number,series_description,classification,selected
```

用 ITK-SNAP 打开 `D:\MRI_CLASS\1_T2toT1\dicom_candidates\<ID>\*.nii.gz`。排除 scout、Motion Curve、NDC 和明显失败序列。若只有一个合格 T1：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only
```

若有多个 T1/T2，显式指定清单中的 `series_number`：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit `
  --select-only `
  --subject 001 `
  --t1-series 302 `
  --t2-series 401 `
  --force-convert
```

没有合格 T2 时省略 `--t2-series`。确认生成：

```powershell
Test-Path D:\MRI_CLASS\1_T2toT1\data\001\T1.nii.gz
```

## 9. 第二段：标准 FreeSurfer 重建

先只跑一例，32 GB 机器使用 4 线程：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit `
  --skip-dicom `
  --subject 001 `
  --recon-jobs 1 `
  --recon-threads 4
```

这是同步任务，PowerShell 不会像 Slurm 一样立即返回。不要关闭窗口、删除容器或删除 `3_recon`。同一命令可断点续跑。

另开一个 PowerShell 查看状态：

```powershell
docker ps
Get-Item D:\MRI_CLASS\3_recon\001\scripts\recon-all.log |
  Select-Object Length,LastWriteTime
Get-Content D:\MRI_CLASS\3_recon\001\scripts\recon-all.log -Tail 30
Test-Path D:\MRI_CLASS\3_recon\001\scripts\recon-all.done
```

## 10. 第三段：导出 STL

`recon-all.done` 为 `True` 后执行：

```powershell
.\bin\smri_3d_print.ps1 D:\MRI_CLASS --subject 001
```

检查：

```powershell
Get-Item D:\MRI_CLASS\4_stl\001\brain.pial.stl
Import-Csv D:\MRI_CLASS\manifests\40_stl_summary.csv | Format-Table
```

主要结果：

```text
D:\MRI_CLASS\3_recon\001\mri\brainmask.mgz
D:\MRI_CLASS\3_recon\001\mri\aseg.mgz
D:\MRI_CLASS\3_recon\001\surf\lh.pial
D:\MRI_CLASS\3_recon\001\surf\rh.pial
D:\MRI_CLASS\4_stl\001\lh.pial.stl
D:\MRI_CLASS\4_stl\001\rh.pial.stl
D:\MRI_CLASS\4_stl\001\brain.pial.stl
```

## 11. 明天先做的最小测试

不要一上来部署整间机房。先选一台机器完成：

```powershell
wsl --version
docker version
docker image inspect caibility1/smri_pipeline_demo:slim-v2.3-2026-07-24

cd D:\sMRI_pipeline_demo
Set-ExecutionPolicy -Scope Process Bypass -Force
.\docker\doctor_demo.ps1
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --dcm2niix-only
```

若 `doctor_demo.ps1` 全部通过且 DICOM 能生成 NIfTI，说明机房的 WSL2、Docker、镜像挂载和核心代码链路都可用。完整 `recon-all` 仍应提前跑一例作为性能与内存验收，课堂当天则准备好预计算 STL 兜底。
