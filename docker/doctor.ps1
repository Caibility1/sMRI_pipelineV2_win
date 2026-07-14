param(
  [string]$PipelineDir = (Resolve-Path (Join-Path $PSScriptRoot "..")),
  [string]$BatchDir = "",
  [string]$AiImage = $(if ($env:SMRI_DOCKER_AI_IMAGE) { $env:SMRI_DOCKER_AI_IMAGE } else { "smri_pipeline_win:ai" }),
  [string]$ToolsImage = $(if ($env:SMRI_DOCKER_TOOLS_IMAGE) { $env:SMRI_DOCKER_TOOLS_IMAGE } else { "smri_pipeline_win:tools" }),
  [string]$Gpus = $(if ($env:SMRI_DOCKER_GPUS) { $env:SMRI_DOCKER_GPUS } else { "all" })
)

$ErrorActionPreference = "Continue"

function Write-Section($Name) {
  Write-Host ""
  Write-Host "== $Name =="
}

function Test-CommandOk($Label, [scriptblock]$Command) {
  Write-Host "[CHECK] $Label"
  & $Command
  if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
    Write-Host "[OK]    $Label"
  } else {
    Write-Host "[WARN]  $Label failed with exit code $LASTEXITCODE"
  }
}

function Add-ContainerEnv($Name, $Value) {
  if ($Value) { $script:EnvArgs += @("-e", "$Name=$Value") }
}

$PipelineDir = (Resolve-Path $PipelineDir).Path
$BaseMountArgs = @("-v", "${PipelineDir}:/pipeline:ro")
$MountArgs = @($BaseMountArgs)
$EnvArgs = @()

if ($BatchDir) {
  $BatchDir = (Resolve-Path $BatchDir).Path
  $BaseMountArgs += @("-v", "${BatchDir}:/batch")
  $MountArgs = @($BaseMountArgs)
}

if ($env:SMRI_DOCKER_EXTRA_MOUNTS) {
  $env:SMRI_DOCKER_EXTRA_MOUNTS.Split(";") | ForEach-Object {
    $mount = $_.Trim()
    if ($mount) { $MountArgs += @("-v", $mount) }
  }
}

Add-ContainerEnv "FSLDIR" $env:FSLDIR
Add-ContainerEnv "FREESURFER_HOME" $env:FREESURFER_HOME

$DefaultFsLicense = Join-Path $PipelineDir "resources\software\freesurfer\license.txt"
if (-not $env:FS_LICENSE -and (Test-Path -LiteralPath $DefaultFsLicense)) {
  Add-ContainerEnv "FS_LICENSE" "/pipeline/resources/software/freesurfer/license.txt"
} elseif ($env:FS_LICENSE) {
  if (-not $env:FS_LICENSE.StartsWith("/") -and (Test-Path -LiteralPath $env:FS_LICENSE)) {
    $licensePath = (Resolve-Path -LiteralPath $env:FS_LICENSE).ProviderPath
    $MountArgs += @("-v", "${licensePath}:/licenses/freesurfer/license.txt:ro")
    Add-ContainerEnv "FS_LICENSE" "/licenses/freesurfer/license.txt"
  } else {
    Add-ContainerEnv "FS_LICENSE" $env:FS_LICENSE
  }
}

Write-Section "Docker"
Test-CommandOk "docker version" { docker version }

Write-Section "Images"
$ToolsImageExists = $false
$AiImageExists = $false
Test-CommandOk "tools image exists: $ToolsImage" { docker image inspect $ToolsImage *> $null; if ($LASTEXITCODE -eq 0) { $script:ToolsImageExists = $true } }
Test-CommandOk "AI image exists: $AiImage" { docker image inspect $AiImage *> $null; if ($LASTEXITCODE -eq 0) { $script:AiImageExists = $true } }

Write-Section "GPU"
$GpuArgs = @()
if ($Gpus -and $Gpus.ToLower() -notin @("none", "false", "0", "no")) {
  $GpuArgs = @("--gpus", $Gpus)
  Test-CommandOk "container GPU nvidia-smi" { docker run --rm @GpuArgs nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi }
} else {
  Write-Host "[SKIP] GPU check disabled because Gpus=$Gpus"
}

Write-Section "Tools Container"
if ($ToolsImageExists) {
  Test-CommandOk "tools container basic checks" {
    $toolsCheck = 'source /pipeline/docker/container_env.sh; python --version; echo FSLDIR=${FSLDIR:-}; echo FREESURFER_HOME=${FREESURFER_HOME:-}; echo FS_LICENSE=${FS_LICENSE:-}; echo ANTSPATH=${ANTSPATH:-}; for cmd in N4BiasFieldCorrection wb_command flirt recon-all mri_convert infant_recon_all; do if path=$(command -v "$cmd" 2>/dev/null); then echo FOUND $cmd=$path; else echo MISSING $cmd; fi; done'
    docker run --rm @EnvArgs @MountArgs $ToolsImage /bin/bash -lc $toolsCheck
  }
} else {
  Write-Host "[SKIP] Tools image is not available: $ToolsImage"
}

Write-Section "AI Container"
if ($AiImageExists) {
  Test-CommandOk "AI container Python/PyTorch checks" {
    docker run --rm @GpuArgs @BaseMountArgs $AiImage python -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('cuda_device_count', torch.cuda.device_count())"
  }
} else {
  Write-Host "[SKIP] AI image is not available: $AiImage"
}

Write-Section "Mounts and Environment"
Write-Host "Mount args: $($MountArgs -join ' ')"
if ($EnvArgs.Count -gt 0) { Write-Host "Env args: $($EnvArgs -join ' ')" }
if ($env:SMRI_DOCKER_EXTRA_MOUNTS) {
  Write-Host "SMRI_DOCKER_EXTRA_MOUNTS=$env:SMRI_DOCKER_EXTRA_MOUNTS"
} else {
  Write-Host "SMRI_DOCKER_EXTRA_MOUNTS is not set. Set it if FSL/FreeSurfer are mounted from host paths."
}

Write-Host ""
Write-Host "Docker doctor finished. WARN lines mean the Docker path is not production-ready yet."










