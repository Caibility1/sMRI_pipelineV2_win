# sMRI Pipeline V2 Docker backend environment example.
# Copy to environment/docker_env.local.ps1 and edit local-only paths.
# Docker is optional. Complete the WSL tutorial first unless prepared images are provided.

$env:SMRI_DOCKER_TOOLS_IMAGE = "smri_pipeline_win:tools"
$env:SMRI_DOCKER_AI_IMAGE = "smri_pipeline_win:ai"

# Use "all" for GPU nnU-Net/moAR-Diff containers. Use "none" only for CPU smoke tests.
$env:SMRI_DOCKER_GPUS = "all"

# FreeSurfer license default:
#   resources\software\freesurfer\license.txt
# Ask the user to replace that file with their own FreeSurfer license.
# Set FS_LICENSE only when using an external license path, for example:
# $env:FS_LICENSE = "\\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\license.txt"

# Optional extra mounts for host-installed tools. Separate mounts with semicolons.
# Examples:
# $env:SMRI_DOCKER_EXTRA_MOUNTS = "\\wsl.localhost\Ubuntu-22.04\home\<USER>\fsl:/opt/fsl:ro;\\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\8.1.0:/opt/freesurfer:ro"
# $env:FSLDIR = "/opt/fsl"
# $env:FREESURFER_HOME = "/opt/freesurfer"

Write-Host "sMRI Docker environment variables loaded."
Write-Host "SMRI_DOCKER_TOOLS_IMAGE=$env:SMRI_DOCKER_TOOLS_IMAGE"
Write-Host "SMRI_DOCKER_AI_IMAGE=$env:SMRI_DOCKER_AI_IMAGE"
Write-Host "SMRI_DOCKER_GPUS=$env:SMRI_DOCKER_GPUS"
if ($env:SMRI_DOCKER_EXTRA_MOUNTS) { Write-Host "SMRI_DOCKER_EXTRA_MOUNTS=$env:SMRI_DOCKER_EXTRA_MOUNTS" }
