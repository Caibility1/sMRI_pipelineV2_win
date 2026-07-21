param(
    [string]$Release = "latest",
    [string]$Registry = "caibility1/smri_pipeline_win",
    [string]$OfflineArchive = "",
    [string]$FsLicenseSource = "",
    [string]$WslDistro = "Ubuntu-22.04",
    [switch]$SkipPrerequisiteInstall,
    [switch]$UseLocalImage
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$EnvironmentName = "sMRI_pipeline_win"

function Test-Command([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-CondaExecutable {
    $CondaCommand = Get-Command conda.exe, conda -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($CondaCommand) {
        if ($CondaCommand.Source) { return $CondaCommand.Source }
        return $CondaCommand.Name
    }

    $DriveCandidates = Get-PSDrive -PSProvider FileSystem | ForEach-Object {
        Join-Path $_.Root "anaconda3\Scripts\conda.exe"
    }
    $Candidates = @(
        "$env:USERPROFILE\miniforge3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniforge3\Scripts\conda.exe",
        "$env:ProgramData\miniforge3\Scripts\conda.exe",
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "$env:ProgramData\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\anaconda3\Scripts\conda.exe",
        "$env:ProgramData\anaconda3\Scripts\conda.exe",
        $DriveCandidates
    )
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate)) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    return $null
}
function Test-NativeProbe([scriptblock]$Probe) {
    $PreviousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & $Probe 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $PreviousErrorAction
    }
}

function Stop-AfterInstall([string]$Message) {
    Write-Host ""
    Write-Host $Message -ForegroundColor Yellow
    Write-Host "After completing that step, run this same setup command again."
    exit 10
}

Write-Host "=== sMRI Pipeline portable new-machine setup ==="
Write-Host "PIPELINE_DIR=$RepoRoot"

if (-not (Test-Command "wsl.exe")) {
    throw "wsl.exe is unavailable. Update Windows, then open Administrator PowerShell and run: wsl --install --no-distribution"
}
if (-not (Test-NativeProbe { & wsl.exe --status })) {
    if ($SkipPrerequisiteInstall) { throw "WSL2 system support is not ready." }
    & wsl.exe --install --no-distribution
    Stop-AfterInstall "WSL2 system support was requested. Restart Windows if prompted. An Ubuntu user distribution is not required for Docker mode."
}

if (-not (Test-Command "docker")) {
    if ($SkipPrerequisiteInstall) { throw "Docker Desktop is missing." }
    if (-not (Test-Command "winget")) { throw "Install Docker Desktop manually, then rerun setup." }
    & winget install --exact --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
    Stop-AfterInstall "Docker Desktop was installed. Start it once and accept its first-run prompts."
}

if (-not (Test-NativeProbe { & docker version })) {
    Stop-AfterInstall "Docker Desktop is installed but its Linux engine is not running. Start Docker Desktop."
}

$Conda = Resolve-CondaExecutable
if (-not $Conda) {
    if ($SkipPrerequisiteInstall) { throw "Miniforge/conda is missing." }
    if (-not (Test-Command "winget")) { throw "Install Miniforge manually, then rerun setup." }
    & winget install --exact --id CondaForge.Miniforge3 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Miniforge installation failed." }
    $Conda = Resolve-CondaExecutable
    if (-not $Conda) {
        Stop-AfterInstall "Miniforge was installed. Open a new PowerShell window."
    }
}
Write-Host "CONDA=$Conda"

$CoreEnvironment = Join-Path $RepoRoot "environment\windows-core.yml"
$CondaInfo = & $Conda env list --json | ConvertFrom-Json
$ExistingEnvironment = $CondaInfo.envs | Where-Object { (Split-Path -Leaf $_) -eq $EnvironmentName }
if ($ExistingEnvironment) {
    Write-Host "Updating conda environment: $EnvironmentName"
    & $Conda env update -n $EnvironmentName -f $CoreEnvironment --prune
} else {
    Write-Host "Creating conda environment: $EnvironmentName"
    & $Conda env create -f $CoreEnvironment
}
if ($LASTEXITCODE -ne 0) { throw "Conda environment installation failed." }

$CondaInfo = & $Conda env list --json | ConvertFrom-Json
$EnvironmentPath = @($CondaInfo.envs | Where-Object { (Split-Path -Leaf $_) -eq $EnvironmentName } | Select-Object -First 1)[0]
if (-not $EnvironmentPath) { throw "Cannot resolve conda environment: $EnvironmentName" }
$Python = Join-Path $EnvironmentPath "python.exe"
if (-not (Test-Path -LiteralPath $Python)) { throw "Cannot resolve Python in $EnvironmentName" }

$WindowsEnv = Join-Path $RepoRoot "environment\windows_env.local.ps1"
$WindowsEnvText = @"
# Generated by setup_new_machine.ps1
`$env:SMRI_PYTHON = "$Python"
`$env:SMRI_WSL_DISTRO = "$WslDistro"
`$env:PIPELINE_DIR = "$RepoRoot"
"@
[IO.File]::WriteAllText($WindowsEnv, $WindowsEnvText, [Text.UTF8Encoding]::new($false))

$InstallArgs = @{
    Release = $Release
    Registry = $Registry
    WslDistro = $WslDistro
}
if ($OfflineArchive) { $InstallArgs.OfflineArchive = $OfflineArchive }
if ($FsLicenseSource) { $InstallArgs.FsLicenseSource = $FsLicenseSource }
if ($UseLocalImage) { $InstallArgs.UseLocalImage = $true }
& (Join-Path $RepoRoot "docker\install_portable.ps1") @InstallArgs
if ($LASTEXITCODE -ne 0) { throw "Portable Docker installation failed." }

. $WindowsEnv
. (Join-Path $RepoRoot "environment\docker_env.local.ps1")

& (Join-Path $RepoRoot "docker\doctor.ps1") -PipelineDir $RepoRoot -AiImage $env:SMRI_DOCKER_AI_IMAGE -ToolsImage $env:SMRI_DOCKER_TOOLS_IMAGE

Write-Host ""
Write-Host "Setup finished. The two bin entrypoints now auto-load local environment files."
Write-Host "Preprocessing: .\bin\smri_preprocessing.ps1 <BATCH_DIR> --submit ..."
Write-Host "Postprocessing: .\bin\smri_presurf_recon.ps1 <BATCH_DIR> --submit ..."
