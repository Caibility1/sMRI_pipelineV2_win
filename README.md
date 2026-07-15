# sMRI Pipeline V2 Windows/WSL2/Docker

This repository provides two one-stop PowerShell entrypoints for structural MRI preprocessing and infant FreeSurfer reconstruction on Windows. The recommended deployment uses one all-in-one Docker image, while Windows runs only lightweight Python orchestration.

## Recommended New-PC Path

The portable image contains PyTorch/CUDA, nnU-Net and its Task523 model, moAR-Diff and its checkpoint, FSL, ANTs, FreeSurfer 8.1, Workbench, and the UNC infant templates.

The host PC needs Windows 10/11, Docker Desktop with WSL2 system support (no separate Ubuntu distribution is required), Git, Miniforge, an NVIDIA driver for GPU stages, and a valid FreeSurfer license.

After cloning the repository:

~~~powershell
cd D:\path\to\sMRI_pipelineV2_win
.\setup_new_machine.ps1 -Release <RELEASE> -FsLicenseSource D:\path\to\license.txt
~~~

For a network-free installation:

~~~powershell
.\setup_new_machine.ps1 -OfflineArchive D:\smri_transfer\smri_pipeline_win_full.tar -FsLicenseSource D:\smri_transfer\license.txt
~~~

The setup is repeatable. If it asks for a restart, a new PowerShell window, or the first Docker Desktop start, do that one action and run the same command again. No FSL/ANTs/FreeSurfer installation inside Ubuntu is required.

Full instructions: [Portable Docker deployment tutorial](docs/portable_docker_tutorial.md).

## User Commands

Preprocessing:

~~~powershell
.\bin\smri_preprocessing.ps1 <BATCH_DIR> [options]
~~~

Post-segmentation presurf/recon:

~~~powershell
.\bin\smri_presurf_recon.ps1 <BATCH_DIR> [options]
~~~

Both entrypoints automatically load:

~~~text
environment\windows_env.local.ps1
environment\docker_env.local.ps1
~~~

Users do not need to remember FSL, FreeSurfer, Workbench, template, model, or nnU-Net environment variables after setup.

## Docker-First Example

External age table without visual QC:

~~~powershell
.\bin\smri_preprocessing.ps1 D:\data\batch001 --submit --qc-excel D:\data\age.xlsx --age-source excel --qc-mode all-pass
~~~

After valid segmentation exists under 6_seg:

~~~powershell
.\bin\smri_presurf_recon.ps1 D:\data\batch001 --submit --recon-jobs 1
~~~

## Data And Segmentation Boundary

MRI data is never stored in Git or Docker images. The absolute batch directory is mounted into the container and all outputs remain on the host.

Minimum preprocessing input:

~~~text
<BATCH_DIR>\1_T2toT1\data\<subject_id>\T1.nii.gz
<BATCH_DIR>\1_T2toT1\data\<subject_id>\T2.nii.gz   optional
~~~

Recon requires externally generated segmentation:

~~~text
<BATCH_DIR>\6_seg\<subject_id>\brain.nii.gz
<BATCH_DIR>\6_seg\<subject_id>\dk-struct.nii.gz
<BATCH_DIR>\6_seg\<subject_id>\tissue.nii.gz
~~~

The existing iBEAT image is not yet called automatically by the two entrypoints.

## Verify And Find Results

Run doctor:

~~~powershell
.\docker\doctor.ps1 -PipelineDir (Resolve-Path .)
~~~

Reports and status:

~~~text
<BATCH_DIR>\logs\preprocessing_report.md
<BATCH_DIR>\logs\postprocessing_report.md
<BATCH_DIR>\manifests\windows_status.csv
<BATCH_DIR>\manifests\40_recon_summary.csv
~~~

## Publishing Or Moving The Image

Build on a prepared source PC:

~~~powershell
.\docker\build_portable_images.ps1
~~~

Publish to private GHCR:

~~~powershell
.\docker\publish_portable_images.ps1 -Release <RELEASE> -AlsoLatest
~~~

Create an offline archive instead:

~~~powershell
.\docker\publish_portable_images.ps1 -Release <RELEASE> -SkipPush -OfflineArchive D:\smri_transfer\smri_pipeline_win_full.tar
~~~

The local development images remain available, but the recommended remote-deployment tag is smri_pipeline_win:full-portable.

## Documentation

- [Portable Docker deployment tutorial](docs/portable_docker_tutorial.md)
- [Command reference](docs/command_reference.md)
- [Full test runbook](docs/full_test_runbook.md)
- [Hardware and performance](docs/performance_and_hardware.md)
- [Windows/WSL2 deployment guide](docs/windows_deployment_guide.md)
- [Docker internals and alternatives](docs/windows_docker_deployment_guide.md)
- [Containerization strategy](docs/containerization_strategy.md)
