# sMRI Docker backend example: mount FSL and FreeSurfer from WSL2 into Docker.
# Copy to environment/docker_env.local.ps1 and edit distro/user paths for another PC.

$env:SMRI_DOCKER_TOOLS_IMAGE = "smri_pipeline_win:tools"
$env:SMRI_DOCKER_AI_IMAGE = "smri_pipeline_win:ai"
$env:SMRI_DOCKER_GPUS = "all"

# Current verified WSL2 mount pattern.
# Change Ubuntu-22.04 and linmo22 if another PC uses a different WSL distro/user.
# FSL is mounted at its original WSL path because its wrapper scripts may contain
# absolute paths such as /home/<user>/fsl/bin/flirt.
# The libpng mount is needed by FreeSurfer/NiftyReg reg_aladin when FreeSurfer is mounted from WSL.
# The tcsh mount is needed by FreeSurfer csh scripts when the base tools image has not been rebuilt yet.
$env:SMRI_DOCKER_EXTRA_MOUNTS = "\\wsl.localhost\Ubuntu-22.04\home\linmo22\fsl:/home/linmo22/fsl:ro;\\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\8.1.0:/opt/freesurfer:ro;\\wsl.localhost\Ubuntu-22.04\usr\lib\x86_64-linux-gnu\libpng16.so.16.37.0:/usr/lib/x86_64-linux-gnu/libpng16.so.16:ro;\\wsl.localhost\Ubuntu-22.04\usr\bin\tcsh:/bin/tcsh:ro"
$env:FSLDIR = "/home/linmo22/fsl"
$env:FREESURFER_HOME = "/opt/freesurfer"

# Prefer replacing resources\software\freesurfer\license.txt in the repository.
# Use this external WSL license path only if you do not want to replace the repository copy.
$env:FS_LICENSE = "\\wsl.localhost\Ubuntu-22.04\usr\local\freesurfer\license.txt"

Write-Host "sMRI Docker WSL-tools environment variables loaded."
Write-Host "SMRI_DOCKER_EXTRA_MOUNTS=$env:SMRI_DOCKER_EXTRA_MOUNTS"
Write-Host "FSLDIR=$env:FSLDIR"
Write-Host "FREESURFER_HOME=$env:FREESURFER_HOME"
Write-Host "FS_LICENSE=$env:FS_LICENSE"




