param(
    [Parameter(Mandatory = $true)]
    [string]$Release,
    [string]$LocalImage = "smri_pipeline_demo:local",
    [string]$Registry = "caibility1/smri_pipeline_demo",
    [switch]$AlsoLatest
)

$ErrorActionPreference = "Stop"
$ReleaseImage = "${Registry}:${Release}"
& docker image inspect $LocalImage *> $null
if ($LASTEXITCODE -ne 0) { throw "Local image not found: $LocalImage" }

& docker tag $LocalImage $ReleaseImage
if ($LASTEXITCODE -ne 0) { throw "Cannot tag $ReleaseImage" }
& docker push $ReleaseImage
if ($LASTEXITCODE -ne 0) { throw "Cannot push $ReleaseImage" }

if ($AlsoLatest) {
    $LatestImage = "${Registry}:latest"
    & docker tag $LocalImage $LatestImage
    & docker push $LatestImage
    if ($LASTEXITCODE -ne 0) { throw "Cannot push $LatestImage" }
}
Write-Host "Published: $ReleaseImage"
