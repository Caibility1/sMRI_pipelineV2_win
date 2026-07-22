# Fresh-PC Full Test Runbook

## 1. Host checks

在 Windows PowerShell 运行：

```powershell
wsl --status
docker version
git --version
nvidia-smi
```

不要求 Conda 或 Ubuntu。Docker version 必须有 Client/Server。

## 2. Pull

```powershell
git clone https://github.com/Caibility1/sMRI_pipelineV2_win.git D:\sMRI_pipelineV2_win
cd D:\sMRI_pipelineV2_win
docker pull caibility1/smri_pipeline_win:runtime-v2-2026-07-22
$env:SMRI_FS_LICENSE = "D:\smri_install\license.txt"
```

## 3. Doctor

```powershell
.\docker\doctor_runtime.ps1 -LicensePath $env:SMRI_FS_LICENSE
```

## 4. Lightweight preprocessing smoke

准备一例 T1：

```text
<BATCH_DIR>\1_T2toT1\data\001_180mo\T1.nii.gz
```

```powershell
.\bin\smri_preprocessing.cmd <BATCH_DIR> --age-source folder --qc-mode all-pass
```

确认 `windows_status.csv` 中 standardize、age、nnU-Net input 和 report 均为 success。

## 5. Heavy preprocessing

```powershell
.\bin\smri_preprocessing.cmd <BATCH_DIR> `
  --submit --age-source folder --qc-mode all-pass --stage1-only
```

确认 registration、nnU-Net、mask 的 summary 和日志。随后按实际流程续跑 ACPC/去噪。

## 6. Presurf smoke

准备一例 `6_seg` 后：

```powershell
.\bin\smri_presurf_recon.cmd <BATCH_DIR> --submit --presurf-only
```

确认 `manifests\30_presurf_summary.csv` 为 success。

## 7. Full recon

```powershell
.\bin\smri_presurf_recon.cmd <BATCH_DIR> --submit --recon-jobs 1
```

确认 `40_recon_summary.csv`、每例 FreeSurfer 关键输出和日志。不要仅以容器退出为成功依据。

## 8. Isolation acceptance

测试机不应依赖宿主 Conda 或 Ubuntu 模组。可在不调用它们的情况下重复 doctor、轻量 preprocessing 和 presurf。数据仍在 Windows；删除容器后结果应继续存在。
