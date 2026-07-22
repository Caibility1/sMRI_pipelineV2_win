param(
    [string]$Release = "runtime-v2-2026-07-22",
    [string]$Registry = "caibility1/smri_pipeline_win",
    [string]$LocalImage = "smri_pipeline_win:runtime-test",
    [switch]$AlsoLatest
)

$ErrorActionPreference = "Stop"
$RemoteImage = "${Registry}:$Release"
& docker image inspect $LocalImage *> $null
if ($LASTEXITCODE -ne 0) { throw "Local image not found: $LocalImage" }

& docker tag $LocalImage $RemoteImage
if ($LASTEXITCODE -ne 0) { throw "Cannot tag $RemoteImage" }
& docker push $RemoteImage
if ($LASTEXITCODE -ne 0) { throw "Cannot push $RemoteImage. Run docker login first." }

if ($AlsoLatest) {
    $Latest = "${Registry}:runtime-latest"
    & docker tag $LocalImage $Latest
    & docker push $Latest
    if ($LASTEXITCODE -ne 0) { throw "Cannot push $Latest" }
}
Write-Host "Published: $RemoteImage"
