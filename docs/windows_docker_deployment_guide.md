# Docker Deployment Guide

This guide is optional. Complete `docs/windows_deployment_guide.md` first unless your instructor or IT team already provides prepared Docker images.

Docker is useful for reproducible runtime environments. It still depends on Windows, WSL2, NVIDIA drivers, model files, and licensed neuroimaging software.

## 1. Deployment Model

The user still runs PowerShell entrypoints:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> [options]
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> [options]
```

Docker is selected per backend:

```powershell
--registration-backend docker
--nnunet-backend docker
--acpc-backend docker
--denoise-backend docker
--recon-backend docker
```

The containers receive mounted project code and mounted batch data. They do not own the workflow.

## 2. Install Docker Desktop

Official WSL2 backend guide: https://docs.docker.com/desktop/features/wsl/

Install Docker Desktop for Windows and enable:

- WSL2 backend.
- Integration with the Ubuntu distribution you use for this project.
- NVIDIA GPU support if nnU-Net/moAR-Diff will run in Docker.

Check in PowerShell:

```powershell
docker version
docker run --rm hello-world
```

Check GPU container support:

```powershell
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

If this fails, fix Docker Desktop, WSL2 integration, or NVIDIA driver before running the pipeline with Docker backends.

## 3. Images in This Repository

Two local images are defined:

```text
smri_pipeline_win:ai
  CUDA runtime
  PyTorch
  nnU-Net v1
  moAR-Diff Python dependencies

smri_pipeline_win:tools
  Ubuntu runtime
  Python utilities
  ANTs / GNU parallel / support packages
  FSL/FreeSurfer-facing job wrappers
```

Important: the default tools Dockerfile does not redistribute FSL or FreeSurfer. It is a base image. A site may extend it privately or mount existing installs.

## 3.1 Current Verified Status

On the development Windows machine, both local images have been built and checked:

```text
smri_pipeline_win:ai     about 14.9 GB
smri_pipeline_win:tools  about 4.5 GB
```

Verified with `docker/doctor.ps1`:

- Docker Desktop WSL2 backend works.
- NVIDIA GPU passthrough works with `--gpus all`.
- `smri_pipeline_win:ai` sees PyTorch 2.5.1 and CUDA.
- `smri_pipeline_win:ai` can run the Task523 nnU-Net wrapper from the PowerShell entrypoint.
- `smri_pipeline_win:tools` sees `N4BiasFieldCorrection` from ANTs.
- `smri_pipeline_win:tools` sees `wb_command` from `resources/software/workbench...` when the repository is mounted.
- `smri_pipeline_win:tools` does not currently include FSL `flirt`.
- `smri_pipeline_win:tools` does not currently include FreeSurfer `infant_recon_all`.

So the current recommended Docker use is AI Docker first, and tools Docker only after FSL/FreeSurfer are mounted or added to a private image.
## 4. Build Images

From the repository root:

```powershell
cd <PIPELINE_DIR>
.\docker\build_images.ps1
```

Build only one image:

```powershell
.\docker\build_images.ps1 -NoTools
.\docker\build_images.ps1 -NoAi
```

First build can take a long time and many GB of disk.

## 5. Configure Docker Environment Variables

Copy and edit:

```powershell
Copy-Item .\environment\docker_env.example.ps1 .\environment\docker_env.local.ps1
notepad .\environment\docker_env.local.ps1
```

Load it before Docker runs:

```powershell
. .\environment\docker_env.local.ps1
```

Typical values:

```powershell
$env:SMRI_DOCKER_TOOLS_IMAGE = "smri_pipeline_win:tools"
$env:SMRI_DOCKER_AI_IMAGE = "smri_pipeline_win:ai"
$env:SMRI_DOCKER_GPUS = "all"
```

FreeSurfer license default is `<PIPELINE_DIR>\resources\software\freesurfer\license.txt`. Ask each user to replace that file with their own FreeSurfer license. No command-line change is needed when this relative path is used.

```powershell
# Optional override only when the license is outside the repository:
$env:FS_LICENSE = "\\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\license.txt"
```

If FreeSurfer is already inside your private tools image:

```powershell
$env:FREESURFER_HOME = "/opt/freesurfer"
$env:FS_LICENSE = "/licenses/freesurfer/license.txt"
```

## 5.1 Minimal Docker Smoke Test

After building images and loading any local Docker env file, run this small test before a full batch:

```powershell
.\docker\doctor.ps1 -PipelineDir <PIPELINE_DIR> -BatchDir <BATCH_DIR>

.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --stage1-only `
  --qc-excel <QC_EXCEL.xlsx> `
  --registration-backend skip `
  --nnunet-backend docker `
  --mask-backend skip
```

Expected PowerShell output includes `START` and `COMPLETE` for `05_nnunet_task523 [docker-bash]`. The detailed log is under `<BATCH_DIR>\2_nnunet_output\logs\05_nnunet_task523.log`.
## 6. Run AI Steps in Docker

Example: use Docker only for nnU-Net and moAR-Diff, keep FSL/ACPC in WSL:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <QC_EXCEL.xlsx> `
  --registration-backend wsl `
  --nnunet-backend docker `
  --mask-backend windows `
  --acpc-backend wsl `
  --denoise-backend docker
```

This is the most realistic first Docker target because AI dependencies are often harder to reproduce than simple Windows Python steps.

## 7. Run Tool Steps in Docker

Example full Docker backend selection:

```powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> `
  --submit `
  --qc-excel <QC_EXCEL.xlsx> `
  --registration-backend docker `
  --nnunet-backend docker `
  --mask-backend windows `
  --acpc-backend docker `
  --denoise-backend docker
```

Use this only after confirming the tools image can see FSL, ANTs, Workbench, and any templates/models.

## 8. Run Recon in Docker

Recon requires FreeSurfer and a license inside the container or mounted into it.

```powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> `
  --submit `
  --presurf-backend windows `
  --recon-backend docker `
  --recon-jobs 2
```

If FreeSurfer is not inside the image, this will fail until you provide a mount/private image strategy.

## 8.1 FreeSurfer and FSL Deployment Choices

FreeSurfer can be handled in Docker, but the license should stay outside the image.

Recommended rule:

```text
Container/image may contain FreeSurfer software.
User-specific license.txt is mounted at runtime.
```

Ask each user or institution to request a FreeSurfer license from the official FreeSurfer download/install page, then save it at a predictable local path such as:

```text
<PIPELINE_DIR>\resources\software\freesurfer\license.txt
```

Then set:

```powershell
$env:FS_LICENSE = "<PIPELINE_DIR>\resources\software\freesurfer\license.txt"
```

If the license stays at the repository default path, the container reads it as `/pipeline/resources/software/freesurfer/license.txt`. If `FS_LICENSE` points to an external Windows drive or UNC path, the Docker launcher mounts it as `/licenses/freesurfer/license.txt` and sets `FS_LICENSE` inside the container.

There are three practical deployment patterns:

| Pattern | What happens | Best use |
| --- | --- | --- |
| WSL local tools | FSL/FreeSurfer installed in Ubuntu WSL2; Docker used mainly for AI | Development, debugging, first successful machine |
| Docker mounts | Host folders are mounted to `/opt/fsl` and `/opt/freesurfer`; license mounted separately | Machines that already have tool folders prepared |
| Private full tools image | Internal image includes FSL, FreeSurfer, ANTs, Workbench; license still mounted separately | Hospital/lab deployment with fixed versions |

For this repository, the default public `smri_pipeline_win:tools` image includes ANTs and can see mounted Workbench resources. It does not yet include FSL or a verified complete FreeSurfer runtime. A future private image can be named, for example:

```text
smri_pipeline_win:tools-full
```

If using mounted host tools from WSL2, this pattern has been verified on the development machine:

```powershell
Copy-Item .\environment\docker_env.wsl_tools.example.ps1 .\environment\docker_env.local.ps1
. .\environment\docker_env.local.ps1
.\docker\doctor.ps1 -PipelineDir <PIPELINE_DIR> -BatchDir <BATCH_DIR>
```

The example maps WSL paths like:

```text
\\wsl.localhost\Ubuntu-22.04\home\<USER>\fsl              -> /opt/fsl
\\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\8.1.0  -> /opt/freesurfer
\\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\license.txt -> /licenses/freesurfer/license.txt
```

If using mounted host tools:

```powershell
$env:SMRI_DOCKER_EXTRA_MOUNTS = "D:\smri_resources\software\fsl:/opt/fsl:ro;D:\smri_resources\software\freesurfer:/opt/freesurfer:ro"
$env:FSLDIR = "/opt/fsl"
$env:FREESURFER_HOME = "/opt/freesurfer"
$env:FS_LICENSE = "<PIPELINE_DIR>\resources\software\freesurfer\license.txt"
```

After this, run:

```powershell
.\docker\doctor.ps1 -PipelineDir <PIPELINE_DIR> -BatchDir <BATCH_DIR>
```

Expected production-ready tool checks should show `FOUND flirt`, `FOUND recon-all`, `FOUND mri_convert`, and `FOUND infant_recon_all` if infant recon is required.
## 9. What Must Be Mounted or Included

The Docker command builder always mounts:

```text
<PIPELINE_DIR> -> /pipeline
<BATCH_DIR>    -> /batch
```

The project code then expects resources under `/pipeline/resources` unless overridden.

For advanced deployments, a site may also mount:

```text
host FSL install        -> /opt/fsl
host FreeSurfer install -> /opt/freesurfer
host FS license         -> /licenses/freesurfer/license.txt
```

Use `SMRI_DOCKER_EXTRA_MOUNTS` for semicolon-separated Docker volume specs:

```powershell
$env:SMRI_DOCKER_EXTRA_MOUNTS = "D:\tools\fsl:/opt/fsl:ro;D:\tools\freesurfer:/opt/freesurfer:ro"
$env:FSLDIR = "/opt/fsl"
$env:FREESURFER_HOME = "/opt/freesurfer"
```

License files can also be mounted automatically when `FS_LICENSE` points to an external Windows drive or UNC path. The repository default license path needs no extra mount because `<PIPELINE_DIR>` is already mounted as `/pipeline`.

Run the Docker doctor after editing mounts:

```powershell
.\docker\doctor.ps1 -PipelineDir <PIPELINE_DIR> -BatchDir <BATCH_DIR>
```

Until FSL/FreeSurfer distribution is finalized, prefer either WSL-installed FSL/FreeSurfer or a private full tools image for beginner deployments.


## 9.1 Data Is Mounted, Not Baked Into Images

Raw data and batch outputs should stay on the local machine or an approved data drive. They are not copied into Docker images.

When the user runs:

```powershell
.\bin\smri_preprocessing.ps1 D:\data\my_batch --submit ...
```

Docker receives this bind mount for that run:

```text
D:\data\my_batch -> /batch
```

The container reads and writes `/batch`, while the real files remain under the Windows path. This is the right model for hospital data: images stay outside Docker images and outside disposable containers.
## 10. Troubleshooting

`docker: command not found`

- Docker Desktop is not installed or PowerShell was opened before Docker updated PATH.

`could not select device driver with capabilities: [[gpu]]`

- Docker GPU support is not working.
- Test with the NVIDIA CUDA `nvidia-smi` container command above.

`CUDA is not available to PyTorch`

- The container started but PyTorch cannot see the GPU.
- Check NVIDIA driver, Docker Desktop WSL2 backend, and `--docker-gpus all`.

`flirt: command not found`

- The tools image does not include FSL and no FSL mount was provided.

`infant_recon_all: command not found`

- FreeSurfer is not inside the tools image and no FreeSurfer mount was provided.

`FreeSurfer license missing`

- Set `FS_LICENSE` and make sure it is available inside the container.

## 11. Beginner Recommendation

For beginners next week:

- Use WSL2 deployment as the primary tutorial.
- Use Docker only if you provide prebuilt images and a known-good machine.
- Do not ask beginners to solve FSL/FreeSurfer licensing and Docker mounts on day one.








## 12. When to Rebuild or Push Images

If the pipeline repository is mounted into Docker, ordinary script changes under `bin`, `scripts`, `docs`, or `environment` usually do not require rebuilding the image. The container sees the current mounted code at `/pipeline`.

Rebuild and push Docker images when one of these changes:

- `docker/Dockerfile.*`
- Linux system packages
- Python package versions
- CUDA/PyTorch/nnU-Net/moAR-Diff environment
- baked-in models or templates
- baked-in FSL, ANTs, Workbench, or FreeSurfer

For other PCs, prefer versioned release tags instead of silently replacing a local tag:

```text
smri_pipeline_win:ai-2026-07-13
smri_pipeline_win:tools-2026-07-13
```

Data should still be mounted from the host. Do not bake raw MRI data into images.
