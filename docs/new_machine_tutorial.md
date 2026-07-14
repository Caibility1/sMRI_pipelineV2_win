# New Machine Tutorial

This tutorial is for a new Windows PC. It assumes Windows conda and WSL2 Ubuntu 22.04 may already be installed, but it still shows how to verify every piece.

Use placeholders consistently:

```text
<PIPELINE_DIR>  the pipeline repository, for example D:\smri\sMRI_pipelineV2_win
<BATCH_DIR>     one dataset batch, for example D:\smri_data\batch001
<AGE_TABLE>     optional Excel file with subject ID and age
<QC_EXCEL>      optional Excel file with subject ID, age, and visual QC status
```

Avoid spaces and non-English characters in first tests.

## 1. What Must Be Installed Manually

These pieces belong to the host PC, not to the pipeline repository.

| Component | Manual? | Why |
| --- | --- | --- |
| Windows 10/11 | yes | Host OS |
| NVIDIA driver | yes, if GPU exists | Required for WSL/Docker GPU access |
| Miniforge/conda on Windows | yes | Runs lightweight Windows Python steps |
| WSL2 Ubuntu 22.04 | yes | Runs Linux-only neuroimaging tools |
| Docker Desktop | optional but recommended | Pull/run reproducible AI/tools images |
| FreeSurfer license | yes | User/institution-specific license |
| Local batch data | yes | Data is mounted, never baked into Docker images |

## 2. What Can Come From Docker

Docker images can standardize runtime software:

```text
smri_pipeline_win:ai
  PyTorch/CUDA
  nnU-Net v1 runtime
  moAR-Diff dependencies

smri_pipeline_win:tools
  Linux support packages
  ANTs/support utilities
  wrappers that can use mounted FSL/FreeSurfer/Workbench
```

FSL and FreeSurfer can be handled in three ways:

1. Install in WSL2 and mount them into Docker.
2. Bake them into a private internal tools image.
3. Run those steps directly in WSL2 without Docker.

For beginners, the easiest successful path is: Windows PowerShell entrypoints + Docker AI image + WSL/Docker-mounted Linux tools.

## 3. Disk Space Planning

Recommended free space before starting:

| Item | Typical space |
| --- | ---: |
| Pipeline code without large tools | 1-5 GB |
| Models | about 2-10 GB, depending on checkpoints |
| Windows conda env | 2-8 GB |
| WSL Ubuntu and Linux tools | 20-80 GB |
| FreeSurfer | 15-30 GB |
| Docker AI image | 10-25 GB |
| Docker tools image | 5-30 GB, more if FSL/FreeSurfer are baked in |
| Test outputs | depends on subject count; FreeSurfer output can be many GB |

A practical first machine should have at least 150 GB free. 250 GB is safer.

## 4. Verify Windows Conda

Open PowerShell:

```powershell
conda --version
python --version
```

Create or update the pipeline environment:

```powershell
cd <PIPELINE_DIR>
conda env create -f environment\environment.yml
conda activate sMRI_pipeline_win
python -c "import pandas, openpyxl, nibabel, SimpleITK, yaml; print('Windows Python OK')"
```

If the environment already exists:

```powershell
conda activate sMRI_pipeline_win
conda env update -f environment\environment.yml --prune
```

## 5. Configure Windows Environment

Copy the example once:

```powershell
cd <PIPELINE_DIR>
Copy-Item environment\windows_env.example.ps1 environment\windows_env.local.ps1
notepad environment\windows_env.local.ps1
```

Set at least:

```powershell
$env:PIPELINE_DIR = "<PIPELINE_DIR>"
$env:SMRI_WSL_DISTRO = "Ubuntu-22.04"
$env:NNUNET_RESOURCE_DIR = "$env:PIPELINE_DIR\resources\models\nnUNet"
$env:MOARDIFF_DIR = "$env:PIPELINE_DIR\resources\models\denoise_diffusion\CBCP_UnDPM_with_age_finetune"
```

Load it in every new PowerShell session:

```powershell
. .\environment\windows_env.local.ps1
```

## 6. Verify WSL2 Ubuntu

From PowerShell:

```powershell
wsl.exe -l -v
wsl.exe -d Ubuntu-22.04 -- bash -lc "echo WSL OK && uname -a"
```

Inside Ubuntu, install baseline packages if missing:

```bash
sudo apt update
sudo apt install -y build-essential curl wget git unzip zip rsync bc file perl procps ca-certificates tcsh libpng16-16
```

## 7. Linux Tool Modules

### FSL

Check first, because you said some machines may already have FSL:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc "source ~/fsl/etc/fslconf/fsl.sh 2>/dev/null || true; command -v flirt; flirt -version"
```

If missing, install FSL in WSL2 following the official FSL installer. After installation, `FSLDIR` should point to the FSL folder, usually `$HOME/fsl`.

### ANTs

Check:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc "command -v N4BiasFieldCorrection && command -v antsRegistration"
```

If missing, install from conda-forge inside the WSL environment or use an official ANTs binary and set `ANTSPATH`.

### Workbench

If bundled under `resources\software`, the pipeline can use it through `environment/wsl_env.sh`.

Check:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc "cd '<WSL_PIPELINE_DIR>' && source environment/wsl_env.sh && wb_command -version"
```

Replace `<WSL_PIPELINE_DIR>` with the WSL path, for example `/mnt/d/smri/sMRI_pipelineV2_win`.

### FreeSurfer and License

FreeSurfer is required for postprocessing/recon.

Check:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc "test -f /usr/local/freesurfer/license.txt && echo FS license found"
wsl.exe -d Ubuntu-22.04 -- bash -lc "source /usr/local/freesurfer/8.1.0/SetUpFreeSurfer.sh 2>/dev/null || true; command -v infant_recon_all; recon-all -version"
```

Each user should obtain their own FreeSurfer license and place it at the configured license path. In this project, keeping the relative path stable is easiest:

```text
<PIPELINE_DIR>\resources\software\freesurfer\license.txt
```

When using the current WSL-mounted setup, `environment\docker_env.wsl_tools.example.ps1` shows how to mount the WSL FreeSurfer folder and license into Docker.

## 8. Put Models in Place

Expected layout:

```text
<PIPELINE_DIR>\resources\models\nnUNet\nnUNetData\
  nnUNet_raw_data_base\
  nnUNet_preprocessed\
  RESULTS_FOLDER\

<PIPELINE_DIR>\resources\models\denoise_diffusion\CBCP_UnDPM_with_age_finetune\
  main.py
  exp\logs\finetuneDPM_with_age\ckpt_100000.pth
```

nnU-Net v1 needs three variables. The wrappers set them from `NNUNET_RESOURCE_DIR`, but they are worth remembering:

```text
nnUNet_raw_data_base
nnUNet_preprocessed
RESULTS_FOLDER
```

## 9. Optional Docker Setup

Install Docker Desktop with WSL2 backend. Then check:

```powershell
docker version
docker run --rm hello-world
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

Pull prebuilt images if your lab provides them:

```powershell
docker pull <registry>/smri_pipeline_win:ai
docker pull <registry>/smri_pipeline_win:tools
```

Or build locally:

```powershell
cd <PIPELINE_DIR>
.\docker\build_images.ps1
```

For mounted WSL tools:

```powershell
Copy-Item environment\docker_env.wsl_tools.example.ps1 environment\docker_env.local.ps1
notepad environment\docker_env.local.ps1
. .\environment\docker_env.local.ps1
.\docker\doctor.ps1 -PipelineDir <PIPELINE_DIR> -BatchDir <BATCH_DIR>
```

Doctor should find Docker, GPU if requested, `flirt`, `N4BiasFieldCorrection`, `wb_command`, and FreeSurfer commands when those backends are used.

## 10. Prepare Input Data

Minimum preprocessing layout:

```text
<BATCH_DIR>\1_T2toT1\data\subject001\T1.nii.gz
<BATCH_DIR>\1_T2toT1\data\subject001\T2.nii.gz   optional
```

For external data without an age Excel, put age in folder names:

```text
<BATCH_DIR>\1_T2toT1\data\subject001_24mo\T1.nii.gz
```

For age Excel, use a simple first sheet with columns like:

```text
subject_id | age
subject001 | 24
```

Column names can also be `id`, `subnum`, `subject`, `month`, `months`, or Chinese `月龄`.

For postprocessing, segmentation must exist:

```text
<BATCH_DIR>\6_seg\subject001_24mo\brain.nii.gz
<BATCH_DIR>\6_seg\subject001_24mo\dk-struct.nii.gz
<BATCH_DIR>\6_seg\subject001_24mo\tissue.nii.gz
```

## 11. Run Preprocessing

Known internal data with visual QC:

```powershell
cd <PIPELINE_DIR>
conda activate sMRI_pipeline_win
. .\environment\windows_env.local.ps1

.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <QC_EXCEL>
```

External age table, no visual QC:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <AGE_TABLE> `
  --age-source excel `
  --qc-mode all-pass
```

External folders already named with age, no visual QC:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --age-source folder `
  --qc-mode all-pass
```

Docker-heavy example:

```powershell
. .\environment\docker_env.local.ps1

.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <AGE_TABLE> `
  --age-source excel `
  --qc-mode all-pass `
  --registration-backend docker `
  --nnunet-backend docker `
  --mask-backend windows `
  --acpc-backend docker `
  --denoise-backend docker
```

## 12. Run Postprocessing/Reconstruction

After segmentation has been placed in `6_seg`:

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> `
  --submit `
  --presurf-backend windows `
  --recon-backend docker `
  --recon-jobs 1
```

Increase to `--recon-jobs 2` or more only after a small test passes. FreeSurfer may run for many hours.

## 13. Check Results

```powershell
Get-Content <BATCH_DIR>\logs\preprocessing_report.md
Get-Content <BATCH_DIR>\logs\postprocessing_report.md
Get-Content <BATCH_DIR>\manifests\windows_status.csv
Get-Content <BATCH_DIR>\manifests\40_recon_summary.csv
```

FreeSurfer subject log:

```powershell
Get-Content <BATCH_DIR>\7_presurf\<subject_id>\log\recon.log -Tail 80
```

## 14. Should Docker Be Rebuilt After Code Changes?

It depends on how the code is used.

If the repository is mounted into Docker, most Python/bash script edits do not require rebuilding the image. The container reads the current host code from `/pipeline`.

You should rebuild and push Docker images when:

- `docker/Dockerfile.*` changes.
- Python package versions change.
- System packages change.
- You decide to bake FSL, ANTs, Workbench, FreeSurfer, or models into an image.
- You want a frozen release image for another PC.

For a stable shared release, use versioned image tags, for example:

```text
smri_pipeline_win:2026-07-13
smri_pipeline_win:ai-2026-07-13
smri_pipeline_win:tools-2026-07-13
```

Keep `latest` or unversioned local tags only for development.

## 15. External References

- Miniforge: https://github.com/conda-forge/miniforge
- WSL installation: https://learn.microsoft.com/windows/wsl/install
- Docker Desktop WSL backend: https://docs.docker.com/desktop/features/wsl/
- Docker GPU support: https://docs.docker.com/desktop/features/gpu/
- FSL installation: https://fsl.fmrib.ox.ac.uk/fsl/docs/#/install/index
- FreeSurfer install/license: https://surfer.nmr.mgh.harvard.edu/fswiki/DownloadAndInstall
- ANTs: https://github.com/ANTsX/ANTs
- Connectome Workbench: https://www.humanconnectome.org/software/connectome-workbench

