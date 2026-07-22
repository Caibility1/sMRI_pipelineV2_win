param(
    [string]$Image = $(if ($env:SMRI_RUNTIME_IMAGE) { $env:SMRI_RUNTIME_IMAGE } else { "caibility1/smri_pipeline_win:runtime-v2-2026-07-22" }),
    [string]$LicensePath = ""
)

$ErrorActionPreference = "Stop"
& docker version *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop Linux engine is not running." }
& docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) { throw "Runtime image not found: $Image. Run docker pull $Image" }

$DockerArgs = @("run", "--rm")
if ($LicensePath) {
    $LicensePath = (Resolve-Path -LiteralPath $LicensePath).ProviderPath
    $DockerArgs += @(
        "--mount", "type=bind,source=$LicensePath,target=/licenses/freesurfer/license.txt,readonly",
        "--env", "FS_LICENSE=/licenses/freesurfer/license.txt"
    )
}
$DockerArgs += @($Image, "doctor")
& docker @DockerArgs
if ($LASTEXITCODE -ne 0) { throw "Runtime doctor failed." }
Write-Host "Runtime doctor complete: $Image"
