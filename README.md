# sMRI Pipeline V2 Windows Container Runtime

这是结构像 MRI 一站式 preprocessing 与 presurf/recon 的 Windows Docker 版本。两个用户入口保持不变：

```text
bin\smri_preprocessing.ps1
bin\smri_presurf_recon.ps1
```

当前推荐架构是单镜像运行：Python/conda、FSL、ANTs、FreeSurfer 8.1、Workbench、nnU-Net Task523、MoAR-Diff、模型权重、模板和核心代码均在 `caibility1/smri_pipeline_win:runtime-v2-2026-07-22` 内。Windows 只负责启动 Docker 并挂载本地数据；不需要在 Windows 安装 Conda，也不需要在个人 Ubuntu 中安装 Linux 模组。

## Start Here

新电脑需要 Windows 10/11、WSL2 系统能力、已启动的 Docker Desktop、可选 Git、NVIDIA 驱动和 FreeSurfer `license.txt`。Git 是推荐的脚本/文档更新方式，但算法代码也已经包含在镜像里。

```powershell
# 在 Windows PowerShell 运行，不是在 Docker Desktop 镜像页面点 Run
wsl --status
docker version

git clone https://github.com/Caibility1/sMRI_pipelineV2_win.git D:\sMRI_pipelineV2_win
cd D:\sMRI_pipelineV2_win
docker pull caibility1/smri_pipeline_win:runtime-v2-2026-07-22

$env:SMRI_FS_LICENSE = "D:\smri_install\license.txt"
.\docker\doctor_runtime.ps1 -LicensePath $env:SMRI_FS_LICENSE
```

正常部署不运行 `setup_new_machine.ps1`。该文件只为旧的“宿主 Conda + 分体 Docker/WSL”架构保留。

完整教程：[单镜像从零部署](docs/portable_docker_tutorial.md)。参数说明：[命令参考](docs/command_reference.md)。

## Data

MRI 数据不进入镜像。绝对路径通过 bind mount 映射，结果仍写回 Windows 批次目录。

```text
<BATCH_DIR>\1_T2toT1\data\<ID>\T1.nii.gz
<BATCH_DIR>\1_T2toT1\data\<ID>\T2.nii.gz   optional
```

年龄可来自 Excel，或来自 `<ID>_<age>mo` 文件夹名。陌生数据没有视觉 QC 表时可使用 `--qc-mode all-pass`。

## Preprocessing

```powershell
.\bin\smri_preprocessing.cmd D:\data\batch001 `
  --submit `
  --qc-excel D:\data\age.xlsx `
  --age-source excel `
  --qc-mode all-pass
```

文件夹已带月龄时：

```powershell
.\bin\smri_preprocessing.cmd D:\data\batch001 `
  --submit --age-source folder --qc-mode all-pass
```

`.cmd` 入口绕过当前子进程的 PowerShell execution policy；`.ps1` 入口也可直接使用。

## Segmentation Boundary

当前 preprocessing 到去噪结束后，不会自动生成研究流程所需的 `6_seg`。postprocessing 前需要：

```text
<BATCH_DIR>\6_seg\<ID>\brain.nii.gz
<BATCH_DIR>\6_seg\<ID>\dk-struct.nii.gz
<BATCH_DIR>\6_seg\<ID>\tissue.nii.gz
```

## Presurf And Recon

```powershell
.\bin\smri_presurf_recon.cmd D:\data\batch001 --submit --recon-jobs 1
```

`--recon-jobs 1` 最稳妥；并发数增加会明显增加内存和磁盘压力。该命令同步运行，终端显示每步 `START/COMPLETE`，不是 Slurm 提交。

## Results

```text
<BATCH_DIR>\logs\preprocessing_report.md
<BATCH_DIR>\logs\postprocessing_report.md
<BATCH_DIR>\manifests\windows_status.csv
<BATCH_DIR>\manifests\40_recon_summary.csv
<BATCH_DIR>\7_presurf\<ID>\log\recon.log
```

## Updates

普通用户更新：

```powershell
cd D:\sMRI_pipelineV2_win
git pull --ff-only origin main
docker pull caibility1/smri_pipeline_win:runtime-v2-2026-07-22
```

Git push 不会自动更新 Docker Hub。维护者修改镜像内代码、依赖或资源后，需要重新 build/push 一个新且可读的版本标签；新版本验证完成前不覆盖旧标签。

维护者命令：

```powershell
.\docker\build_runtime_image.ps1
.\docker\doctor_runtime.ps1 -Image smri_pipeline_win:runtime-test -LicensePath D:\smri_install\license.txt
.\docker\publish_runtime_image.ps1 -Release runtime-v2-2026-07-22
```

## More Documentation

- [单镜像从零部署](docs/portable_docker_tutorial.md)
- [命令参考](docs/command_reference.md)
- [新电脑完整测试](docs/full_test_runbook.md)
- [硬件与性能](docs/performance_and_hardware.md)
- [容器化设计](docs/superpowers/specs/2026-07-22-win-container-native-runtime-design.md)
