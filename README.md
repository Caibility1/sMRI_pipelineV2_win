# sMRI Pipeline Demo

这是面向结构像 MRI 重建与 3D 打印教学的 Docker 命令行 pipeline。学生可以放入自己的原始 DICOM，亲自完成序列转换、视觉 QC、标准 FreeSurfer 重建和 STL 导出。

## Pipeline

```text
DICOM -> dcm2niix -> 全部 NIfTI 候选 -> 人工选择 T1/可选 T2
      -> standard FreeSurfer recon-all (optional T2 pial refinement)
      -> lh/rh/combined pial STL
```

教学分支不运行 ACPC、nnU-Net、MoAR-Diff、外部分割、presurf 或 `infant_recon_all`，也不再运行独立 FSL 配准。标准 `recon-all` 自行完成去颅骨、aseg 和皮层表面重建；合适的 3D T2 可用于 pial 优化。不需要年龄或 QC Excel。

## New PC

主机只需要 Windows 10/11、WSL2 系统能力、Docker Desktop 和 FreeSurfer `license.txt`。不需要 Windows Conda，也不需要单独安装 Ubuntu、FSL、ANTs 或 FreeSurfer。镜像已经包含运行代码；Git 只是推荐的脚本和文档更新方式。

```powershell
git clone --branch demo https://github.com/Caibility1/sMRI_pipelineV2_win.git D:\sMRI_pipeline_demo
cd D:\sMRI_pipeline_demo
docker pull caibility1/smri_pipeline_demo:slim-v2.1-2026-07-22
$env:SMRI_FS_LICENSE = "D:\smri_install\license.txt"
.\docker\doctor_demo.ps1 -LicensePath $env:SMRI_FS_LICENSE
```

`setup_demo.ps1` 仅是可选助手；正常运行不依赖它。完全不克隆 Git 也可直接使用 `docker run`，详见[从零部署教程](docs/teaching_demo_tutorial.md)。教学组织见[教学日运行清单](docs/teaching_day_runbook.md)。

## Data

```text
<BATCH_DIR>\
  0_rawdata\
    001\ ... DICOM files ...
    003\ ... DICOM files ...
```

数据通过 bind mount 映射为容器内 `/data`；不会复制进镜像，也不会上传到 Docker Hub。

## Commands

```powershell
# 1. 转换所有 DICOM，不自动选择
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --dcm2niix-only

# 2. 视觉 QC 后标准化唯一候选
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only

# 多个 T1 时明确指定
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --select-only `
  --subject 001 --t1-series 302 --t2-series 401 --force-convert

# 3. 标准 FreeSurfer 重建
.\bin\smri_reconstruction.ps1 D:\MRI_CLASS --submit --skip-dicom --recon-jobs 1

# 4. 导出 STL
.\bin\smri_3d_print.ps1 D:\MRI_CLASS
```

检查 `manifests\00_dicom_series_inventory.csv`、`1_T2toT1\dicom_candidates` 以及日志后再进入下一阶段。

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

```powershell
.\docker\build_demo_image.ps1
.\docker\doctor_demo.ps1 -Image smri_pipeline_demo:slim-test -LicensePath D:\smri_install\license.txt
docker login
.\docker\publish_demo_image.ps1 -Release slim-v2.1-2026-07-22
```

代码变化后需重新 build/push；仅 Git push 不会改变 Docker Hub 镜像。学生随后重新 `docker pull` 指定版本即可。
