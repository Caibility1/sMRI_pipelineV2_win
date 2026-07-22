param(
    [string]$Image = "smri_pipeline_demo:slim-test"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath

Write-Host "=== Build sMRI teaching image ==="
Write-Host "IMAGE=$Image"
$BuildArgs = @(
    "build",
    "-f", (Join-Path $PSScriptRoot "Dockerfile.smri-demo"),
    "-t", $Image,
    $RepoRoot
)
& docker @BuildArgs
if ($LASTEXITCODE -ne 0) { throw "Docker build failed with exit code $LASTEXITCODE" }

Write-Host "Image ready: $Image"
Write-Host "Test it with: .\docker\doctor_demo.ps1 -Image $Image"
