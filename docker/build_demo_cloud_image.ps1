param(
    [string]$Image = "smri_pipeline_demo:cloud-nomcr-test"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath

Write-Host "=== Build sMRI Codespaces image (no MCR) ==="
Write-Host "IMAGE=$Image"
$env:DOCKER_BUILDKIT = "1"
& docker build `
    -f (Join-Path $PSScriptRoot "Dockerfile.smri-demo-cloud") `
    -t $Image `
    $RepoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed with exit code $LASTEXITCODE"
}

Write-Host "Image ready: $Image"
Write-Host "Verify with docker image inspect and the container doctor command."
