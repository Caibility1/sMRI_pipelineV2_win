param(
    [string]$Image = $(if ($env:SMRI_DEMO_IMAGE) { $env:SMRI_DEMO_IMAGE } else { "caibility1/smri_pipeline_demo:slim-v2.2-2026-07-23" }),
    [string]$LicensePath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
if (-not $LicensePath) {
    $LicensePath = Join-Path $RepoRoot "resources\software\freesurfer\license.txt"
}
if (-not (Test-Path -LiteralPath $LicensePath -PathType Leaf)) {
    throw "FreeSurfer license not found: $LicensePath"
}
$LicensePath = (Resolve-Path -LiteralPath $LicensePath).ProviderPath

Write-Host "[CHECK] Docker Desktop engine"
& docker version *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop Linux engine is not running." }
Write-Host "[OK] Docker Desktop engine"

Write-Host "[CHECK] Image $Image"
& docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) { throw "Image not found: $Image" }
Write-Host "[OK] Image"

Write-Host "[CHECK] Container tools and license"
$DockerArgs = @(
    "run", "--rm",
    "-e", "FS_LICENSE=/licenses/freesurfer/license.txt",
    "-v", "${LicensePath}:/licenses/freesurfer/license.txt:ro",
    $Image, "doctor"
)
& docker @DockerArgs
if ($LASTEXITCODE -ne 0) { throw "Container doctor failed." }
Write-Host "Teaching pipeline doctor complete."
