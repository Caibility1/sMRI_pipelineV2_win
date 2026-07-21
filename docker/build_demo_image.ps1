param(
    [string]$Image = "smri_pipeline_demo:local",
    [string]$BaseImage = "caibility1/smri_pipeline_win:full-2026-07-15"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath

Write-Host "=== Build sMRI teaching image ==="
Write-Host "BASE_IMAGE=$BaseImage"
Write-Host "IMAGE=$Image"
$BuildArgs = @(
    "build",
    "--build-arg", "BASE_IMAGE=$BaseImage",
    "-f", (Join-Path $PSScriptRoot "Dockerfile.smri-demo"),
    "-t", $Image,
    $RepoRoot
)
& docker @BuildArgs
if ($LASTEXITCODE -ne 0) { throw "Docker build failed with exit code $LASTEXITCODE" }

Write-Host "Image ready: $Image"
Write-Host "Test it with: .\docker\doctor_demo.ps1 -Image $Image"
