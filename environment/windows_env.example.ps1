# sMRI Pipeline V2 Windows/WSL2 environment example.
# Copy this file to environment/windows_env.local.ps1 and edit local paths.
# Do not commit your local file if it contains private paths or licenses.

$env:SMRI_PYTHON = "python"
$env:SMRI_WSL_DISTRO = "Ubuntu-22.04"

# Project root on Windows. Change this to your copied/cloned repository.
$env:PIPELINE_DIR = "C:\smri\sMRI_pipelineV2_win"

# Optional project/resource root used by some helper scripts.
$env:SMRI_QC_DIR = $env:PIPELINE_DIR

# nnU-Net v1 resources. The three nnU-Net variables are required by nnU-Net v1.
$env:NNUNET_RESOURCE_DIR = "$env:PIPELINE_DIR\resources\models\nnUNet"
$env:nnUNet_raw_data_base = "$env:NNUNET_RESOURCE_DIR\nnUNetData\nnUNet_raw_data_base"
$env:nnUNet_preprocessed = "$env:NNUNET_RESOURCE_DIR\nnUNetData\nnUNet_preprocessed"
$env:RESULTS_FOLDER = "$env:NNUNET_RESOURCE_DIR\nnUNetData\RESULTS_FOLDER"

# moAR-Diff denoise model.
$env:MOARDIFF_DIR = "$env:PIPELINE_DIR\resources\models\denoise_diffusion\CBCP_UnDPM_with_age_finetune"
$env:MOARDIFF_CKPT = "$env:MOARDIFF_DIR\exp\logs\finetuneDPM_with_age\ckpt_100000.pth"
$env:MOARDIFF_CONFIG_NAME = "inference.yml"

# Linux-only tools are expected inside WSL2 by default. Use Linux paths here.
# Edit these after installing FreeSurfer and placing the license.
$env:FREESURFER_HOME = "/usr/local/freesurfer"
$env:FS_LICENSE = "/usr/local/freesurfer/license.txt"

Write-Host "sMRI Windows environment variables loaded."
Write-Host "PIPELINE_DIR=$env:PIPELINE_DIR"
Write-Host "SMRI_WSL_DISTRO=$env:SMRI_WSL_DISTRO"
Write-Host "NNUNET_RESOURCE_DIR=$env:NNUNET_RESOURCE_DIR"
Write-Host "MOARDIFF_DIR=$env:MOARDIFF_DIR"
