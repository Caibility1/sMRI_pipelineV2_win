param(
    [Parameter(Mandatory = $true)]
    [string]$Release,
    [string]$Registry = "caibility1/smri_pipeline_win",
    [string]$LocalImage = "smri_pipeline_win:full-portable",
    [switch]$AlsoLatest,
    [switch]$SkipPush,
    [string]$OfflineArchive = ""
)

$ErrorActionPreference = "Stop"
$Tag = "full-$Release"
$RemoteImage = "${Registry}:$Tag"

docker image inspect $LocalImage *> $null
if ($LASTEXITCODE -ne 0) { throw "Local image not found: $LocalImage" }

if (-not $SkipPush) {
    Write-Host "Tagging $LocalImage as $RemoteImage"
    docker tag $LocalImage $RemoteImage
    if ($LASTEXITCODE -ne 0) { throw "docker tag failed" }

    Write-Host "Pushing $RemoteImage"
    docker push $RemoteImage
    if ($LASTEXITCODE -ne 0) {
        throw "docker push failed for $RemoteImage. Log in to the selected registry first."
    }

    if ($AlsoLatest) {
        $Latest = "${Registry}:full-latest"
        docker tag $LocalImage $Latest
        docker push $Latest
        if ($LASTEXITCODE -ne 0) { throw "docker push failed for $Latest" }
    }
} elseif (-not $OfflineArchive) {
    throw "-SkipPush requires -OfflineArchive."
}

if ($OfflineArchive) {
    $ArchivePath = [IO.Path]::GetFullPath($OfflineArchive)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ArchivePath) | Out-Null
    Write-Host "Writing offline image archive: $ArchivePath"
    docker save --output $ArchivePath $LocalImage
    if ($LASTEXITCODE -ne 0) { throw "docker save failed" }
}

if (-not $SkipPush) { Write-Host "Published: $RemoteImage" }