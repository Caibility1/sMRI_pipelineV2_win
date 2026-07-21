param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsFromUser
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DemoEnv = Join-Path $RepoRoot "environment\demo_env.local.ps1"
if (Test-Path -LiteralPath $DemoEnv) { . $DemoEnv }
$DefaultImage = if ($env:SMRI_DEMO_IMAGE) { $env:SMRI_DEMO_IMAGE } else { "caibility1/smri_pipeline_demo:latest" }

if (-not $ArgsFromUser -or $ArgsFromUser[0] -in @("-h", "--help")) {
    Write-Host "Usage: .\bin\smri_3d_print.ps1 BATCH_DIR [--subject ID] [--force]"
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
    throw "FreeSurfer license not found: $LicensePath"
}
$LicensePath = (Resolve-Path -LiteralPath $LicensePath).ProviderPath

Write-Host "=== sMRI pial surface STL export ==="
Write-Host "IMAGE=$DefaultImage"
Write-Host "BATCH_DIR=$BatchDir"

$DockerArgs = @(
    "run", "--rm",
    "-e", "FS_LICENSE=/licenses/freesurfer/license.txt",
    "-v", "${LicensePath}:/licenses/freesurfer/license.txt:ro",
    "-v", "${BatchDir}:/data",
    $DefaultImage,
    "stl", "/data"
) + $ForwardArgs
& docker @DockerArgs
exit $LASTEXITCODE
