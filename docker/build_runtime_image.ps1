param(
    [string]$Image = "smri_pipeline_win:runtime-test",
    [string]$ResourceRoot = "",
    [string]$WslDistro = "Ubuntu-22.04",
    [string]$FslSource = "",
    [string]$FslContextImage = "smri-fsl-context:6.0.7.22",
    [switch]$RefreshFslContext
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
if (-not $ResourceRoot) { $ResourceRoot = $RepoRoot }
$ResourceRoot = (Resolve-Path -LiteralPath $ResourceRoot).ProviderPath

function Require-Path([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "$Label not found: $Path" }
    return (Resolve-Path -LiteralPath $Path).ProviderPath
}

$Nnunet = Require-Path (Join-Path $ResourceRoot "resources\models\nnUNet") "nnU-Net resource"
$Moardiff = Require-Path (Join-Path $ResourceRoot "resources\models\denoise_diffusion\CBCP_UnDPM_with_age_finetune") "moAR-Diff resource"
$Workbench = Require-Path (Join-Path $ResourceRoot "resources\software\workbench-linux64-v2.0.0\workbench") "Workbench resource"
$Templates = Require-Path (Join-Path $ResourceRoot "resources\templates") "Template resource"

$PrepareArgs = @{ WslDistro = $WslDistro; ContextImage = $FslContextImage }
if ($FslSource) { $PrepareArgs.FslSource = $FslSource }
if ($RefreshFslContext) { $PrepareArgs.Force = $true }
& (Join-Path $PSScriptRoot "prepare_fsl_context.ps1") @PrepareArgs
if ($LASTEXITCODE -ne 0) { throw "FSL context preparation failed" }

$BuildArgs = @(
    "buildx", "build", "--output", "type=docker,compression=uncompressed",
    "-f", (Join-Path $PSScriptRoot "Dockerfile.smri-full-portable"),
    "-t", $Image,
    "--build-context", "fsl=docker-image://$FslContextImage",
    "--build-context", "nnunet=$Nnunet",
    "--build-context", "moardiff=$Moardiff",
    "--build-context", "workbench=$Workbench",
    "--build-context", "templates=$Templates",
    $RepoRoot
)
& docker @BuildArgs
if ($LASTEXITCODE -ne 0) { throw "Runtime image build failed" }
Write-Host "Runtime image ready: $Image"
Write-Host "Verify: .\docker\doctor_runtime.ps1 -Image $Image -LicensePath <license.txt>"
