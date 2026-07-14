# Windows/WSL2 Deployment Tutorial

This guide assumes the reader starts from a normal Windows PC and has not used WSL2, conda, or Docker before. It avoids machine-specific paths. Replace placeholders such as `<PIPELINE_DIR>` and `<BATCH_DIR>` with your own folders.`r`n`r`nFor a full beginner path with module-by-module installation, Docker choices, and external age-only data examples, start with `docs/new_machine_tutorial.md`.

## 0. What You Need Before Starting

Recommended hardware:

- Windows 10 22H2 or Windows 11, 64-bit.
- SSD with at least 150 GB free space. 250 GB is safer if FreeSurfer and Docker images are stored locally.
- 32 GB RAM minimum for small tests; 64 GB recommended.
- NVIDIA GPU recommended for nnU-Net and moAR-Diff. 8 GB VRAM or more is a practical target.
- Administrator permission, or help from IT, for WSL2, GPU driver, Docker Desktop, and some tool installs.

Folder convention used in examples:

```text
C:\smri\sMRI_pipelineV2_win       # project code
D:\smri_data\batch001             # one data batch
D:\smri_resources                 # optional external resources/licenses
```

You can use other paths. Avoid spaces and non-English characters in early tests.

## 1. Install Windows Basics

### 1.1 Install Miniforge

Miniforge provides `conda` without installing a large Anaconda distribution.

Official source: https://github.com/conda-forge/miniforge

Steps:

1. Download the Windows x86_64 Miniforge installer.
2. Install for the current user.
3. Open a new PowerShell window.
4. Check:

```powershell
conda --version
python --version
```

### 1.2 Install Git

Git is optional if the project is copied by USB or zip, but recommended for updates.

Check:

```powershell
git --version
```

### 1.3 Install NVIDIA Driver

If the PC has an NVIDIA GPU, install a recent NVIDIA driver from NVIDIA or the laptop vendor. CUDA toolkit is not always required on Windows because PyTorch/Docker can ship CUDA runtime libraries, but the driver must be installed.

Check:

```powershell
nvidia-smi
```

If this command is missing or shows no GPU, GPU inference will not work yet.

## 2. Get the Project

Put the project somewhere stable, for example:

```powershell
mkdir C:\smri
# Copy or clone the repository here.
cd C:\smri\sMRI_pipelineV2_win
```

The project should contain:

```text
bin\
scripts\
resources\
environment\
docs\
docker\
```

## 3. Create the Windows Conda Environment

The Windows environment runs lightweight Python steps: file organization, manifests, CSV reports, image checks, and some masking utilities.

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

## 4. Configure Windows Environment Variables

Copy the example file:

```powershell
cd <PIPELINE_DIR>
Copy-Item environment\windows_env.example.ps1 environment\windows_env.local.ps1
notepad environment\windows_env.local.ps1
```

Edit at least these values:

```powershell
$env:PIPELINE_DIR = "C:\smri\sMRI_pipelineV2_win"
$env:SMRI_WSL_DISTRO = "Ubuntu-22.04"
$env:NNUNET_RESOURCE_DIR = "$env:PIPELINE_DIR\resources\models\nnUNet"
$env:MOARDIFF_DIR = "$env:PIPELINE_DIR\resources\models\denoise_diffusion\CBCP_UnDPM_with_age_finetune"
```

Load it before running the pipeline:

```powershell
. .\environment\windows_env.local.ps1
```

## 5. Install WSL2 Ubuntu

Official Microsoft guide: https://learn.microsoft.com/windows/wsl/install

In an Administrator PowerShell:

```powershell
wsl --install -d Ubuntu-22.04
```

Restart if Windows asks. Then open Ubuntu from the Start menu and create a Linux username/password.

Update Ubuntu:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y build-essential curl wget git unzip zip rsync bc file perl procps ca-certificates
```

Check Windows can call WSL:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc "echo WSL OK && uname -a"
```

## 6. Install a Conda/Mamba Environment Inside WSL

Linux-only Python/GPU jobs run inside WSL. You can use Miniforge or micromamba. Miniforge is easier for new users.

Inside Ubuntu, install Miniforge from the official project page, then create the environment:

```bash
cd /mnt/c/smri/sMRI_pipelineV2_win   # change to your project path as seen from WSL
conda env create -f environment/environment.yml
conda activate sMRI_pipeline_win
python -c "import torch, nibabel, SimpleITK; print('WSL Python OK', torch.cuda.is_available())"
```

If `torch.cuda.is_available()` is `False`, nnU-Net/moAR-Diff GPU inference will not run yet. Fix the NVIDIA driver/WSL GPU path first.

## 7. Install or Expose Linux Neuroimaging Tools

### 7.1 FSL

Used by T2-to-T1 registration and ACPC jobs.

Official install guide: https://fsl.fmrib.ox.ac.uk/fsl/docs/#/install/index

Typical result after installation:

```bash
export FSLDIR=$HOME/fsl
source $FSLDIR/etc/fslconf/fsl.sh
flirt -version
```

This project tries common locations automatically through `environment/wsl_env.sh`, but a new user should still verify `flirt`, `fslmaths`, `slicer`, and `pngappend` work.

### 7.2 ANTs

Used by ACPC and bias/registration-related jobs.

Official source: https://github.com/ANTsX/ANTs

Recommended beginner path: install ANTs into the WSL conda environment if available from conda-forge:

```bash
conda activate sMRI_pipeline_win
conda install -c conda-forge ants -y
N4BiasFieldCorrection --version || true
antsRegistration --version || true
```

If the conda package is unavailable or incomplete on your machine, use an official binary/build from ANTsX and set `ANTSPATH` to its `bin` directory.

### 7.3 Connectome Workbench

Used by QC/ACPC-related scripts.

Official source: https://www.humanconnectome.org/software/connectome-workbench

This repository can use a bundled Linux Workbench copy if present under:

```text
resources/software/workbench-linux64-v2.0.0/workbench/bin_linux64
```

Check inside WSL:

```bash
cd /mnt/c/smri/sMRI_pipelineV2_win
source environment/wsl_env.sh
wb_command -version
```

If not bundled, install Workbench separately and set `SMRI_WORKBENCH_BIN` to the `bin_linux64` directory.

### 7.4 FreeSurfer and License

Used by `smri_presurf_recon.ps1` through `infant_recon_all`.

Official install/license page: https://surfer.nmr.mgh.harvard.edu/fswiki/DownloadAndInstall

FreeSurfer is large and license-controlled. This repository does not assume it can redistribute FreeSurfer. A new deployment should either:

- install FreeSurfer inside WSL, then set `FREESURFER_HOME` and `FS_LICENSE`; or
- build a private institutional Docker image that includes FreeSurfer, if your license permits it; or
- mount an existing FreeSurfer install into a Docker container.

Check:

```bash
source /path/to/freesurfer/SetUpFreeSurfer.sh
infant_recon_all --help | head
recon-all -version
```

## 8. Put Models and Templates in Place

Expected project resource layout:

```text
resources\
  models\
    nnUNet\
      nnUNetData\
        nnUNet_raw_data_base\
        nnUNet_preprocessed\
        RESULTS_FOLDER\
    denoise_diffusion\
      CBCP_UnDPM_with_age_finetune\
  templates\
  software\
```

nnU-Net v1 requires these three environment variables:

```text
nnUNet_raw_data_base
nnUNet_preprocessed
RESULTS_FOLDER
```

The Windows and WSL wrappers export them automatically from `NNUNET_RESOURCE_DIR`, but they are listed here because forgetting them is one of the most common nnU-Net failures.

moAR-Diff needs:

```text
MOARDIFF_DIR
MOARDIFF_CKPT
MOARDIFF_CONFIG_NAME
```

## 9. Run the WSL Doctor

From PowerShell:

```powershell
cd <PIPELINE_DIR>
wsl.exe -d Ubuntu-22.04 -- bash /mnt/c/smri/sMRI_pipelineV2_win/environment/wsl_doctor.sh
```

Use the WSL path that corresponds to your project. For example:

- `C:\smri\...` becomes `/mnt/c/smri/...`
- `D:\work\...` becomes `/mnt/d/work/...`

The doctor checks FSL, ANTs, Workbench, FreeSurfer, nnU-Net variables, moAR-Diff checkpoint, Python, and GPU visibility.

## 10. Prepare a Test Batch

Minimum preprocessing input:

```text
<BATCH_DIR>\
  1_T2toT1\
    data\
      subject001\
        T1.nii.gz
        T2.nii.gz   # optional
```

Minimum postprocessing input after segmentation:

```text
<BATCH_DIR>\
  6_seg\
    subject001\
      brain.nii.gz
      dk-struct.nii.gz
      tissue.nii.gz
```

For the first test, use 1-2 subjects, not a full study.

## 11. Dry Run First

```powershell
cd <PIPELINE_DIR>
conda activate sMRI_pipeline_win
. .\environment\windows_env.local.ps1

.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --dry-run `
  --qc-excel <QC_EXCEL.xlsx>
```

A dry run creates command logs but does not execute heavy steps.

## 11.5 External Data Without Visual QC

Known internal datasets can use a CBCP/ASD/SHCH-style workbook with age and T1 visual QC status:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --submit --qc-excel <QC_EXCEL.xlsx>
```

For external datasets without visual QC, use `--qc-mode all-pass`. Age can come from an age-only Excel:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <AGE_TABLE.xlsx> `
  --age-source excel `
  --qc-mode all-pass
```

or from existing folder suffixes such as `subject001_24mo`:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --age-source folder `
  --qc-mode all-pass
```

Excel ID matching tolerates numeric IDs whose leading zeros were dropped.
## 12. Real Preprocessing Run

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <QC_EXCEL.xlsx>
```

Resume examples:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --acpc-start --qc-excel <QC_EXCEL.xlsx>
.\bin\smri_preprocessing.ps1 <BATCH_DIR> --denoising-start --qc-excel <QC_EXCEL.xlsx>
```

## 13. Real Presurf/Reconstruction Run

Only run this after `6_seg` exists.

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> `
  --submit `
  --recon-jobs 2
```

Use `--recon-jobs 1` on weak machines. FreeSurfer can run for many hours.

## 14. Where Results and Logs Are

- Step status table: `<BATCH_DIR>\manifests\windows_status.csv`
- Preprocessing report: `<BATCH_DIR>\logs\preprocessing_report.md`
- Postprocessing report: `<BATCH_DIR>\logs\postprocessing_report.md`
- WSL command scripts: `<BATCH_DIR>\logs\wsl_commands\`
- FreeSurfer subject log: `<BATCH_DIR>\7_presurf\<subject_id>\log\recon.log`

Monitor FreeSurfer from PowerShell:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc "ps -eo pid,ppid,etime,cmd | grep -E 'infant_recon_all|recon_all.sh|parallel --jobs' | grep -v grep"
```

## 15. Common Errors

`windows_env.local.ps1 not found`

- Copy `environment\windows_env.example.ps1` to `environment\windows_env.local.ps1` first.
- Run the command from `<PIPELINE_DIR>`.

`CUDA is not available to PyTorch`

- Check `nvidia-smi` in Windows and WSL.
- Check PyTorch was installed with CUDA support.
- CPU mode is possible only for tiny smoke tests and is not recommended for real nnU-Net/moAR-Diff runs.

`flirt: command not found`

- FSL is missing or `FSLDIR` is not exported.
- Source `environment/wsl_env.sh` and rerun `wsl_doctor.sh`.

`N4BiasFieldCorrection: command not found`

- ANTs is missing or `ANTSPATH` is not on `PATH`.

`infant_recon_all: command not found`

- FreeSurfer is missing or `FREESURFER_HOME` was not sourced.

`FreeSurfer license not found`

- Set `FS_LICENSE` to a valid license file.
- Do not assume another computer has your local license path.

## 16. When to Use Docker

Docker is optional. It is useful when you need a repeatable runtime across multiple PCs, but it still needs host GPU drivers and careful handling of licensed software.

Read next: `docs/containerization_strategy.md` and `docs/windows_docker_deployment_guide.md`.


