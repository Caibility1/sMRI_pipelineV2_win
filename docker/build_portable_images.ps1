param(
    [string]$FullImage = "smri_pipeline_win:full-portable",
    [string]$AiImage = "smri_pipeline_win:ai-portable",
    [string]$ToolsImage = "smri_pipeline_win:tools-portable",
    [string]$WslDistro = "Ubuntu-22.04",
    [string]$FslSource = "",
    [string]$FslContextImage = "smri-fsl-context:6.0.7.22",
    [switch]$RefreshFslContext,
    [switch]$BuildSplitImages,
    [switch]$NoFull,
    [switch]$NoAi,
    [switch]$NoTools
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Require-Path([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).ProviderPath
}

function Invoke-Build([string[]]$Arguments) {
    Write-Host "docker $($Arguments -join ' ')"
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed with exit code $LASTEXITCODE"
    }
}

$Nnunet = Require-Path (Join-Path $RepoRoot "resources\models\nnUNet") "nnU-Net resource"
$Moardiff = Require-Path (Join-Path $RepoRoot "resources\models\denoise_diffusion\CBCP_UnDPM_with_age_finetune") "moAR-Diff resource"
$Workbench = Require-Path (Join-Path $RepoRoot "resources\software\workbench-linux64-v2.0.0\workbench") "Workbench resource"
$Templates = Require-Path (Join-Path $RepoRoot "resources\templates") "Template resource"

$NeedFsl = (-not $NoFull) -or ($BuildSplitImages -and -not $NoTools)
if ($NeedFsl) {
    $PrepareArgs = @{
        WslDistro = $WslDistro
        ContextImage = $FslContextImage
    }
    if ($FslSource) { $PrepareArgs.FslSource = $FslSource }
    if ($RefreshFslContext) { $PrepareArgs.Force = $true }
    & (Join-Path $PSScriptRoot "prepare_fsl_context.ps1") @PrepareArgs
    if ($LASTEXITCODE -ne 0) {
        throw "FSL context preparation failed with exit code $LASTEXITCODE"
    }
}
$Fsl = "docker-image://$FslContextImage"

if (-not $NoFull) {
    # docker buildx build --build-context fsl=... --build-context nnunet=... --build-context moardiff=... --build-context workbench=... --build-context templates=...
    Invoke-Build @(
        "buildx", "build", "--output", "type=docker,compression=uncompressed",
        "-f", (Join-Path $RepoRoot "docker\Dockerfile.smri-full-portable"),
        "-t", $FullImage,
        "--build-context", "fsl=$Fsl",
        "--build-context", "nnunet=$Nnunet",
        "--build-context", "moardiff=$Moardiff",
        "--build-context", "workbench=$Workbench",
        "--build-context", "templates=$Templates",
        $RepoRoot
    )
}

if ($BuildSplitImages -and -not $NoAi) {
    # docker buildx build --build-context nnunet=... --build-context moardiff=...
    Invoke-Build @(
        "buildx", "build", "--output", "type=docker,compression=uncompressed",
        "-f", (Join-Path $RepoRoot "docker\Dockerfile.smri-ai-portable"),
        "-t", $AiImage,
        "--build-context", "nnunet=$Nnunet",
        "--build-context", "moardiff=$Moardiff",
        $RepoRoot
    )
}

if ($BuildSplitImages -and -not $NoTools) {
    # docker buildx build --build-context fsl=... --build-context workbench=... --build-context templates=...
    Invoke-Build @(
        "buildx", "build", "--output", "type=docker,compression=uncompressed",
        "-f", (Join-Path $RepoRoot "docker\Dockerfile.smri-tools-portable"),
        "-t", $ToolsImage,
        "--build-context", "fsl=$Fsl",
        "--build-context", "workbench=$Workbench",
        "--build-context", "templates=$Templates",
        $RepoRoot
    )
}

Write-Host "Portable images ready:"
if (-not $NoFull) { Write-Host "  $FullImage" }
if ($BuildSplitImages -and -not $NoAi) { Write-Host "  $AiImage" }
if ($BuildSplitImages -and -not $NoTools) { Write-Host "  $ToolsImage" }