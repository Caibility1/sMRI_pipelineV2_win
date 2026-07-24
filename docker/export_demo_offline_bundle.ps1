param(
    [string]$Image = "caibility1/smri_pipeline_demo:slim-v2.3-2026-07-24",
    [string]$Destination = "D:\smri_demo_offline",
    [string]$LicensePath
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$Destination = [IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

& docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker image is not available locally: $Image"
}

$SafeTag = ($Image -replace "[^A-Za-z0-9._-]", "_")
$ImageTar = Join-Path $Destination "$SafeTag.tar"
$CodeZip = Join-Path $Destination "smri_pipeline_demo_code.zip"

Write-Host "Exporting Docker image. This can take several minutes..."
& docker save --output $ImageTar $Image
if ($LASTEXITCODE -ne 0) { throw "docker save failed" }

Write-Host "Exporting the tracked demo repository..."
& git -C $RepoRoot archive --format=zip --output=$CodeZip HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }

if ($LicensePath) {
    $ResolvedLicense = (Resolve-Path -LiteralPath $LicensePath).ProviderPath
    Copy-Item -LiteralPath $ResolvedLicense -Destination (Join-Path $Destination "license.txt") -Force
}

$HashPath = Join-Path $Destination "SHA256SUMS.txt"
Get-ChildItem -LiteralPath $Destination -File |
    Where-Object Name -ne "SHA256SUMS.txt" |
    Get-FileHash -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash)  $([IO.Path]::GetFileName($_.Path))" } |
    Set-Content -LiteralPath $HashPath -Encoding ASCII

Write-Host "Offline bundle ready: $Destination"
Write-Host "Student import command: docker load -i `"$ImageTar`""
