# Portable Docker Deployment Tutorial

This is the recommended deployment path for a new Windows PC. It uses one all-in-one Linux image for AI and neuroimaging tools, while the two PowerShell entrypoints remain the user interface.

## 1. What Is And Is Not Installed

The portable image contains:

- CUDA/PyTorch runtime
- nnU-Net v1 and the Task523 model
- moAR-Diff and its checkpoint
- FSL 6.0.7.22
- ANTs
- FreeSurfer 8.1 with `infant_recon_all`
- Connectome Workbench
- UNC infant templates

The new PC still needs:

- Windows 10/11
- WSL2 system support for Docker Desktop; a separate Ubuntu user distribution is not required
- Docker Desktop
- Git
- Miniforge/conda for lightweight Windows steps
- NVIDIA Windows driver for GPU stages
- a valid FreeSurfer license

FSL, ANTs, and FreeSurfer do not need to be installed inside the user's Ubuntu distribution when every Linux backend is `docker`. Docker Desktop uses WSL2 internally, but the tools live inside the image.

## 2. Disk Space

Reserve at least 180 GB of free space before installation. The current all-in-one image reports about 91 GB logical size, and Docker also needs temporary pull/load space plus the repository resources restored from the image. Reserve 250 GB or more when several recon outputs will remain on the machine. Place Docker Desktop's virtual disk on a sufficiently large data drive before pulling or loading the image.

## 3. Install Windows Prerequisites

Open PowerShell as Administrator:

```powershell
wsl.exe --install --no-distribution
winget install --exact --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
winget install --exact --id Git.Git --accept-source-agreements --accept-package-agreements
winget install --exact --id CondaForge.Miniforge3 --accept-source-agreements --accept-package-agreements
```

Restart Windows if requested. Start Docker Desktop once and wait until its Linux engine is running.

Verify:

```powershell
wsl.exe --status
docker version
git --version
conda --version
```

For the recommended Docker mode, do not install FSL, ANTs, FreeSurfer, or Workbench into Ubuntu. Install an Ubuntu distribution only when deliberately using the advanced `wsl` backend or preparing a new image from local WSL tools.

## 4. Clone Or Update The Code

Fresh clone:

```powershell
cd D:\your_install_parent
git clone https://github.com/Caibility1/sMRI_pipelineV2_win.git
cd sMRI_pipelineV2_win
```

Existing clone:

```powershell
cd D:\path\to\sMRI_pipelineV2_win
git pull
```

Large models and Linux programs are intentionally not stored in Git history.

## 5A. Online Image Installation Through GHCR

Create a GitHub personal access token (classic) with `read:packages`. In PowerShell:

```powershell
$env:CR_PAT = "<YOUR_GITHUB_TOKEN>"
$env:CR_PAT | docker login ghcr.io -u Caibility1 --password-stdin
Remove-Item Env:CR_PAT
```

Run setup from the repository root:

```powershell
.\setup_new_machine.ps1 `
  -Release <RELEASE> `
  -FsLicenseSource D:\path\to\license.txt
```

The script creates/updates the lightweight conda environment, pulls the image, restores the two models/Workbench/templates into `resources`, copies the license, generates local environment files, and runs Docker doctor.

## 5B. Offline Installation When The Network Is Poor

On the prepared source PC, create an archive:

```powershell
.\docker\publish_portable_images.ps1 `
  -Release <RELEASE> `
  -SkipPush `
  -OfflineArchive D:\smri_transfer\smri_pipeline_win_full.tar
```

Also copy the code repository or clone it separately, and copy the FreeSurfer license:

```powershell
Copy-Item \\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\license.txt `
  D:\smri_transfer\license.txt
```

Transfer the tar and license to the new PC, then run:

```powershell
.\setup_new_machine.ps1 `
  -OfflineArchive D:\smri_transfer\smri_pipeline_win_full.tar `
  -FsLicenseSource D:\smri_transfer\license.txt
```

The current full archive is about 36.4 GB; future releases may differ. Use a sufficiently large NTFS/exFAT drive or a reliable local network share, and verify the provided SHA-256 checksum after transfer.

## 6. Environment Files

Setup generates:

```text
environment\windows_env.local.ps1
environment\docker_env.local.ps1
```

They define the Windows Python path, image name, bundled-resource mode, and Linux tool paths. Both `bin/*.ps1` entrypoints load these files automatically. Users do not need to remember nnU-Net's three variables or manually source FSL/FreeSurfer.

## 7. Verify The Installation

```powershell
.\docker\doctor.ps1 -PipelineDir (Resolve-Path .)
```

The doctor should find:

```text
torch / CUDA
nnU-Net Task523 resources
moAR-Diff checkpoint
flirt
N4BiasFieldCorrection
wb_command
recon-all
mri_convert
infant_recon_all
FreeSurfer license
UNC templates
```

Do not start a full batch until required checks pass.

## 8. Prepare Data

Data stays outside Docker. Minimum preprocessing input:

```text
<BATCH_DIR>\1_T2toT1\data\<subject_id>\T1.nii.gz
<BATCH_DIR>\1_T2toT1\data\<subject_id>\T2.nii.gz   optional
```

Use an absolute Windows batch path such as `D:\smri_data\batch001`. The launcher mounts it at `/batch` inside the container.

## 9. Run Preprocessing With The Full Image

External age table without visual QC:

```powershell
.\bin\smri_preprocessing.ps1 D:\smri_data\batch001 `
  --submit `
  --qc-excel D:\smri_data\age.xlsx `
  --age-source excel `
  --qc-mode all-pass
```

Folder names already contain age:

```powershell
.\bin\smri_preprocessing.ps1 D:\smri_data\batch001 `
  --submit `
  --age-source folder `
  --qc-mode all-pass
```

## 10. Segmentation Boundary

The current workflow does not automatically generate `6_seg`. Before recon, each subject needs:

```text
<BATCH_DIR>\6_seg\<subject_id>\brain.nii.gz
<BATCH_DIR>\6_seg\<subject_id>\dk-struct.nii.gz
<BATCH_DIR>\6_seg\<subject_id>\tissue.nii.gz
```

The existing `ibeatgroup/ibeat_v2:release210` image can be transferred separately, but it is not yet wired into the two one-stop entrypoints.

## 11. Run Presurf And Recon

Start with one concurrent reconstruction:

```powershell
.\bin\smri_presurf_recon.ps1 D:\smri_data\batch001 `
  --submit `
  --recon-jobs 1
```

Increase `--recon-jobs` only after checking RAM, CPU, and disk usage.

## 12. Logs And Reports

```text
<BATCH_DIR>\logs\preprocessing_report.md
<BATCH_DIR>\logs\postprocessing_report.md
<BATCH_DIR>\manifests\windows_status.csv
<BATCH_DIR>\manifests\40_recon_summary.csv
<BATCH_DIR>\7_presurf\<subject_id>\log\recon.log
```

## 13. Publishing A New Release

Ordinary Python/bash/PowerShell code changes require a Git push but not an image rebuild because the repository is mounted at `/pipeline`.

Rebuild the full image when models, templates, Workbench, FSL, ANTs, FreeSurfer, CUDA, PyTorch, or image dependencies change:

```powershell
.\docker\build_portable_images.ps1
```

Authenticate with a classic PAT containing `write:packages`, then publish:

```powershell
.\docker\publish_portable_images.ps1 `
  -Release <RELEASE> `
  -AlsoLatest
```

Official references:

- GitHub Container Registry: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- Docker Desktop WSL2 backend: https://docs.docker.com/desktop/features/wsl/
- FSL Linux/WSL install: https://fsl.fmrib.ox.ac.uk/fsl/docs/install/linux.html
- FreeSurfer install/license: https://surfer.nmr.mgh.harvard.edu/fswiki/DownloadAndInstall
