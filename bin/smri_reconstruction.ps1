param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsFromUser
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DemoEnv = Join-Path $RepoRoot "environment\demo_env.local.ps1"
if (Test-Path -LiteralPath $DemoEnv) { . $DemoEnv }
$DefaultImage = if ($env:SMRI_DEMO_IMAGE) { $env:SMRI_DEMO_IMAGE } else { "caibility1/smri_pipeline_demo:slim-v2.2-2026-07-23" }

function Show-Usage {
    Write-Host "Usage: .\bin\smri_reconstruction.ps1 BATCH_DIR --submit [options]"
    Write-Host "Options: --raw-dir PATH --dcm2niix-only --select-only --convert-only --skip-dicom --recon-jobs N --recon-threads N --subject ID"
    Write-Host "         --t1-series N --t2-series N --force-convert"
}

if (-not $ArgsFromUser -or $ArgsFromUser[0] -in @("-h", "--help")) {
    Show-Usage
    exit 0
}

$BatchDir = (Resolve-Path -LiteralPath $ArgsFromUser[0]).ProviderPath
$ForwardArgs = if ($ArgsFromUser.Count -gt 1) { @($ArgsFromUser[1..($ArgsFromUser.Count - 1)]) } else { @() }
$LicensePath = if ($env:SMRI_FS_LICENSE) {
    $env:SMRI_FS_LICENSE
} else {
    Join-Path $RepoRoot "resources\software\freesurfer\license.txt"
}
if (-not (Test-Path -LiteralPath $LicensePath -PathType Leaf)) {
    throw "FreeSurfer license not found: $LicensePath. Set SMRI_FS_LICENSE or place license.txt at resources\software\freesurfer\."
}
$LicensePath = (Resolve-Path -LiteralPath $LicensePath).ProviderPath

Write-Host "=== sMRI teaching reconstruction ==="
Write-Host "IMAGE=$DefaultImage"
Write-Host "BATCH_DIR=$BatchDir"
Write-Host "The terminal remains attached; progress is also written under BATCH_DIR\logs."

$DockerArgs = @(
    "run", "--rm",
    "-e", "FS_LICENSE=/licenses/freesurfer/license.txt",
    "-v", "${LicensePath}:/licenses/freesurfer/license.txt:ro",
    "-v", "${BatchDir}:/data",
    $DefaultImage,
    "reconstruct", "/data"
) + $ForwardArgs
& docker @DockerArgs
exit $LASTEXITCODE
