# Full Test Runbook From a Fresh Windows PC

This runbook starts from a fresh Windows machine and ends with staged preprocessing and postprocessing tests. It assumes the user will run the two PowerShell entrypoints, while Docker and WSL2 provide Linux tools when needed.

Replace placeholders:

```text
<PIPELINE_DIR>  project folder, for example C:\smri\sMRI_pipelineV2_win
<BATCH_DIR>     test batch folder, for example D:\smri_data\0706_TEST
<QC_EXCEL>      QC spreadsheet, for example D:\smri_data\CBCP_QC.xlsx
<WSL_DISTRO>    usually Ubuntu-22.04
<WSL_USER>      Linux username inside WSL2
```

## 1. Install Host Prerequisites

Install on Windows:

```text
Miniforge
Git, optional if project is copied by zip/USB
NVIDIA driver, if an NVIDIA GPU is present
WSL2 Ubuntu, recommended Ubuntu-22.04
Docker Desktop with WSL2 backend
```

Basic checks in PowerShell:

```powershell
conda --version
git --version
wsl.exe -l -v
docker version
nvidia-smi
```

If there is no NVIDIA GPU, Docker can still run CPU/tool checks, but nnU-Net and moAR-Diff will be slow or impractical.

## 2. Place the Project and Resources

Put the project in a stable folder without spaces, for example:

```powershell
cd C:\smri\sMRI_pipelineV2_win
```

Expected project folders:

```text
bin\
scripts\
environment\
docker\
docs\
resources\
```

Expected model/software folders:

```text
resources\models\nnUNet\
resources\models\denoise_diffusion\CBCP_UnDPM_with_age_finetune\
resources\software\workbench-linux64-v2.0.0\
resources\software\freesurfer\license.txt
```

FreeSurfer license rule:

```text
Ask the user to request their own FreeSurfer license and replace:
resources\software\freesurfer\license.txt
```

This relative path is the default. No command option is needed if the file is there.

## 3. Create the Windows Conda Environment

PowerShell:

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

## 4. Configure Windows Environment

PowerShell:

```powershell
cd <PIPELINE_DIR>
Copy-Item environment\windows_env.example.ps1 environment\windows_env.local.ps1
notepad environment\windows_env.local.ps1
. .\environment\windows_env.local.ps1
```

At minimum, confirm paths for:

```text
PIPELINE_DIR
SMRI_WSL_DISTRO
NNUNET_RESOURCE_DIR
MOARDIFF_DIR
```

## 5. Prepare WSL2 Linux Tools

Inside WSL2, install or verify:

```text
FSL
FreeSurfer with infant_recon_all
FreeSurfer license
```

Useful checks from PowerShell:

```powershell
wsl.exe -d <WSL_DISTRO> -- bash -lc "command -v flirt; flirt -version"
wsl.exe -d <WSL_DISTRO> -- bash -lc "ls -l /usr/local/freesurfer/8.1.0/bin/infant_recon_all"
wsl.exe -d <WSL_DISTRO> -- bash -lc "test -f /usr/local/freesurfer/license.txt && echo FS license OK"
```

For Docker mounting, the verified pattern is:

```text
\\wsl.localhost\<WSL_DISTRO>\home\<WSL_USER>\fsl              -> /opt/fsl
\\wsl.localhost\<WSL_DISTRO>\usr\local\freesurfer\8.1.0      -> /opt/freesurfer
\\wsl.localhost\<WSL_DISTRO>\usr\local\freesurfer\license.txt -> /licenses/freesurfer/license.txt
```

## 6. Build Docker Images

PowerShell:

```powershell
cd <PIPELINE_DIR>
.\docker\build_images.ps1
```

Expected images:

```powershell
docker image ls smri_pipeline_win
```

Expected names:

```text
smri_pipeline_win:ai
smri_pipeline_win:tools
```

## 7. Configure Docker Tool Mounts

For a WSL-mounted tools setup:

```powershell
cd <PIPELINE_DIR>
Copy-Item .\environment\docker_env.wsl_tools.example.ps1 .\environment\docker_env.local.ps1
notepad .\environment\docker_env.local.ps1
. .\environment\docker_env.local.ps1
```

Edit these if needed:

```text
Ubuntu-22.04 -> your WSL distro name
linmo22      -> your WSL username
```

Run doctor:

```powershell
.\docker\doctor.ps1 -PipelineDir <PIPELINE_DIR> -BatchDir <BATCH_DIR>
```

Expected healthy lines:

```text
FOUND N4BiasFieldCorrection
FOUND wb_command
FOUND flirt
FOUND recon-all
FOUND mri_convert
FOUND infant_recon_all
torch 2.5.1
cuda_available True
```

## 8. Prepare Test Data

Data is not copied into Docker images. Keep it on a local data drive and pass its absolute path.

Minimum preprocessing layout:

```text
<BATCH_DIR>\
  1_T2toT1\
    data\
      subject001\
        T1.nii.gz
        T2.nii.gz   optional
```

Minimum postprocessing layout after segmentation:

```text
<BATCH_DIR>\
  6_seg\
    subject001\
      brain.nii.gz
      dk-struct.nii.gz
      tissue.nii.gz
```

For first testing, use 1-2 subjects.

## 9. Stage A: Windows Preparation Smoke Test

This checks the PowerShell entrypoint and lightweight Python steps.

```powershell
cd <PIPELINE_DIR>
conda activate sMRI_pipeline_win
. .\environment\windows_env.local.ps1

.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --qc-excel <QC_EXCEL>
```

Expected: validation/report steps run, but heavy jobs do not run without `--submit`.

## 10. Stage B: Docker nnU-Net Smoke Test

This tests AI Docker only, skipping FSL registration and masking.

```powershell
. .\environment\docker_env.local.ps1

.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --stage1-only `
  --qc-excel <QC_EXCEL> `
  --registration-backend skip `
  --nnunet-backend docker `
  --mask-backend skip
```

Expected:

```text
<<< COMPLETE 05_nnunet_task523 [docker-bash]
```

Check:

```powershell
Get-Content <BATCH_DIR>\2_nnunet_output\logs\05_nnunet_task523.log -Tail 50
Get-Content <BATCH_DIR>\manifests\windows_status.csv -Tail 20
```

## 11. Stage C: Stage 1 With FSL Registration in Docker

This tests tools Docker for FSL and AI Docker for nnU-Net.

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --stage1-only `
  --qc-excel <QC_EXCEL> `
  --registration-backend docker `
  --nnunet-backend docker `
  --mask-backend windows
```

Expected completed steps include:

```text
03_registration_fsl [docker-bash]
05_nnunet_task523 [docker-bash]
06_mask_all [windows-python]
```

## 12. Stage D: ACPC in Docker

Run after Stage 1 outputs exist.

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --acpc-start `
  --qc-excel <QC_EXCEL> `
  --acpc-backend docker `
  --denoise-backend skip
```

Expected completed steps include:

```text
11_acpc_T1T2 [docker-bash]
12_qc_acpc_T1T2 [docker-bash]
11_acpc_justT1 [docker-bash]
12_qc_acpc_justT1 [docker-bash]
```

## 13. Stage E: Denoising in Docker

Run only after ACPC/QC candidate selection is valid.

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --denoising-start `
  --qc-excel <QC_EXCEL> `
  --denoise-backend docker
```

Expected:

```text
21_denoise_moardiff [docker-bash]
```

If there are no questionable/fail candidates, this step may complete quickly or skip according to the manifests.

## 14. Stage F: Presurf Only

Run after valid segmentation files exist under `6_seg`.

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> `
  --submit `
  --presurf-only `
  --presurf-backend windows
```

Expected:

```text
30_presurf_standard [windows-python]
```

## 15. Stage G: FreeSurfer Recon in Docker

This is long-running. Start with one subject and low parallelism.

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> `
  --submit `
  --presurf-backend windows `
  --recon-backend docker `
  --recon-jobs 1
```

After one-subject success, try:

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> `
  --submit `
  --presurf-backend windows `
  --recon-backend docker `
  --recon-jobs 2
```

Monitor logs:

```powershell
Get-Content <BATCH_DIR>\7_presurf\logs\40_recon_standard.log -Tail 80
Get-Content <BATCH_DIR>\7_presurf\<subject_id>\log\recon.log -Tail 80
```

## 16. Where to Check Results

```text
<BATCH_DIR>\manifests\windows_status.csv
<BATCH_DIR>\logs\preprocessing_report.md
<BATCH_DIR>\logs\postprocessing_report.md
<BATCH_DIR>\logs\docker_commands\
<BATCH_DIR>\7_presurf\logs\40_recon_standard.log
```

A staged test is considered successful only when:

```text
windows_status.csv shows success for the tested steps
expected output folders are non-empty
reports are generated
step logs contain no fatal errors
```

## 17. Common Stop Points

If Docker doctor cannot find `flirt`, fix FSL mount or use WSL backend.

If Docker doctor cannot find `infant_recon_all`, fix FreeSurfer mount or use WSL backend.

If `cuda_available False`, fix NVIDIA driver/Docker GPU support before AI Docker tests.

If FreeSurfer license fails, replace:

```text
resources\software\freesurfer\license.txt
```

or set `FS_LICENSE` in `environment\docker_env.local.ps1`.
