# sMRI Pipeline Demo

这是面向结构像 MRI 重建与 3D 打印教学的 Docker 版命令行 pipeline。学生使用自己的
原始 DICOM 数据亲自启动流程；教师可在教学日前用同一流程完成全量重建并准备 STL。

## Pipeline

```text
DICOM -> dcm2niix -> T1/T2 NIfTI
      -> optional FSL T2-to-T1 registration
      -> standard FreeSurfer recon-all
      -> lh/rh/combined pial STL
```

本教学分支不运行 ACPC、nnU-Net、MoAR-Diff、外部分割、presurf 或
`infant_recon_all`。标准 `recon-all` 自行完成去颅骨、aseg 和皮层表面重建；T2 可选，
不需要年龄/QC Excel。

## New PC

主机只需要：Windows 10/11、WSL2 系统能力、Docker Desktop、Git 和 FreeSurfer
`license.txt`。不需要 Windows Conda，也不需要单独安装 Ubuntu、FSL、ANTs 或
FreeSurfer。

```powershell
git clone https://github.com/Caibility1/sMRI_pipeline_demo.git D:\sMRI_pipeline_demo
cd D:\sMRI_pipeline_demo
.\setup_demo.ps1 -FsLicenseSource D:\smri_install\license.txt
```

首次部署、硬盘要求和故障处理见
[从零部署教程](docs/teaching_demo_tutorial.md)。教学组织见
[教学日运行清单](docs/teaching_day_runbook.md)。

## Data

```text
<BATCH_DIR>\
  0_rawdata\
    001\ ... DICOM files ...
    003\ ... DICOM files ...
```

数据保留在 Windows 绝对路径中，通过 bind mount 暂时映射为容器内 `/data`；数据并不
复制进镜像，也不会上传到 Docker Hub。

## Commands

第一次只转换全部 DICOM 序列，不自动选择或启动重建：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --dcm2niix-only
```

检查 `manifests\00_dicom_series_inventory.csv` 和
`1_T2toT1\dicom_candidates`。视觉 QC 后，先把确认的序列标准化：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only
```

如果某名受试者有多个 T1，按 inventory 中的 series number 明确选择：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only `
  --subject 001 --t1-series 302 --t2-series 401 --force-convert
```

确认 `1_T2toT1\data\<ID>\T1.nii.gz` 后启动标准重建：

```powershell
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --skip-dicom --recon-jobs 1
```

需要额外展示 T2-to-T1 刚体配准时加 `--registration`。完成后导出 STL：

```powershell
.\bin\smri_3d_print.ps1 D:\MRI_CLASS
```

主要结果：

```text
<BATCH_DIR>\3_recon\<ID>\mri\brainmask.mgz
<BATCH_DIR>\3_recon\<ID>\mri\aseg.mgz
<BATCH_DIR>\3_recon\<ID>\surf\lh.pial
<BATCH_DIR>\3_recon\<ID>\surf\rh.pial
<BATCH_DIR>\4_stl\<ID>\brain.pial.stl
<BATCH_DIR>\manifests\30_recon_summary.csv
<BATCH_DIR>\manifests\40_stl_summary.csv
```

## Maintainer

构建和检查本地镜像：

```powershell
.\docker\build_demo_image.ps1
.\docker\doctor_demo.ps1 -Image smri_pipeline_demo:local
```

发布 Docker Hub 版本：

```powershell
docker login
.\docker\publish_demo_image.ps1 -Release 2026-07-20 -AlsoLatest
```

镜像包含运行代码和 Linux 工具。代码发生变化后需要重新 build/push；学生本机随后执行
`docker pull caibility1/smri_pipeline_demo:latest` 即可取得新版本。
