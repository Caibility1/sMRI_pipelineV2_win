param(
    [string]$LocalImage = "smri_pipeline_demo:cloud-nomcr-test",
    [string]$Release = "cloud-nomcr-v1-2026-07-23",
    [string]$Registry = "caibility1/smri_pipeline_demo"
)

$ErrorActionPreference = "Stop"
$ReleaseImage = "${Registry}:${Release}"

& docker image inspect $LocalImage *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Local image not found: $LocalImage"
}

& docker tag $LocalImage $ReleaseImage
if ($LASTEXITCODE -ne 0) {
    throw "Cannot tag $ReleaseImage"
}

& docker push $ReleaseImage
if ($LASTEXITCODE -ne 0) {
    throw "Cannot push $ReleaseImage"
}

Write-Host "Published: $ReleaseImage"
