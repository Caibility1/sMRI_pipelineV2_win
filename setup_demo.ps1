param(
    [string]$Image = "caibility1/smri_pipeline_demo:slim-v2-2026-07-22",
    [Parameter(Mandatory = $true)]
    [string]$FsLicenseSource,
    [int]$PullAttempts = 3
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL2 system support is missing. In Administrator PowerShell run: wsl --install --no-distribution"
}
& wsl.exe --status *> $null
if ($LASTEXITCODE -ne 0) {
    throw "WSL2 is not ready. Enable virtualization/WSL2, restart Windows, and rerun this setup."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is missing. Install it, select the WSL2 backend, start it once, then rerun setup."
}
& docker version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but its Linux engine is not running. Start Docker Desktop and rerun setup."
}
if (-not (Test-Path -LiteralPath $FsLicenseSource -PathType Leaf)) {
    throw "FreeSurfer license not found: $FsLicenseSource"
}

$LicenseDir = Join-Path $RepoRoot "resources\software\freesurfer"
New-Item -ItemType Directory -Force -Path $LicenseDir | Out-Null
Copy-Item -LiteralPath $FsLicenseSource -Destination (Join-Path $LicenseDir "license.txt") -Force

$pulled = $false
for ($attempt = 1; $attempt -le $PullAttempts; $attempt++) {
    Write-Host "Pulling $Image (attempt $attempt/$PullAttempts)"
    & docker pull $Image
    if ($LASTEXITCODE -eq 0) {
        $pulled = $true
        break
    }
    if ($attempt -lt $PullAttempts) { Start-Sleep -Seconds (5 * $attempt) }
}
if (-not $pulled) {
    throw "Docker pull failed after $PullAttempts attempts. Check Docker Desktop proxy/VPN settings and retry."
}

$EnvironmentDir = Join-Path $RepoRoot "environment"
New-Item -ItemType Directory -Force -Path $EnvironmentDir | Out-Null
$EnvFile = Join-Path $EnvironmentDir "demo_env.local.ps1"
[IO.File]::WriteAllText(
    $EnvFile,
    "`$env:SMRI_DEMO_IMAGE = `"$Image`"`r`n",
    [Text.UTF8Encoding]::new($false)
)
$env:SMRI_DEMO_IMAGE = $Image
& (Join-Path $RepoRoot "docker\doctor_demo.ps1") -Image $Image

Write-Host ""
Write-Host "Setup complete. No Windows conda environment or Ubuntu distribution is required for this teaching image."
Write-Host "Run: .\bin\smri_reconstruction.ps1 D:\path\to\batch --submit --recon-jobs 1"
