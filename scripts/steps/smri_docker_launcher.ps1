param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("preprocess", "postprocess")]
    [string]$Command,
    [Parameter(Mandatory = $true)]
    [string]$Image,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PipelineArgs
)

$ErrorActionPreference = "Stop"

function Resolve-HostPath([string]$PathValue) {
    return (Resolve-Path -LiteralPath $PathValue).ProviderPath
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install and start Docker Desktop first."
}

if (-not $PipelineArgs -or $PipelineArgs.Count -eq 0) {
    & docker run --rm $Image $Command --help
    exit $LASTEXITCODE
}

if ($PipelineArgs[0] -in @("-h", "--help")) {
    & docker run --rm $Image $Command --help
    exit $LASTEXITCODE
}

$BatchDir = Resolve-HostPath $PipelineArgs[0]
$ForwardArgs = @($PipelineArgs | Select-Object -Skip 1)
$DockerArgs = @(
    "run", "--rm", "--init",
    "--shm-size", $(if ($env:SMRI_DOCKER_SHM_SIZE) { $env:SMRI_DOCKER_SHM_SIZE } else { "8g" }),
    "--mount", "type=bind,source=$BatchDir,target=/data"
)

if ($Command -eq "preprocess") {
    $GpuSetting = if ($env:SMRI_DOCKER_GPUS) { $env:SMRI_DOCKER_GPUS } else { "all" }
    if ($GpuSetting -notin @("", "none", "0", "false", "no")) {
        $DockerArgs += @("--gpus", $GpuSetting)
    }
}

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LicenseCandidates = @(@(
    $env:SMRI_FS_LICENSE,
    (Join-Path $RepoRoot "resources\software\freesurfer\license.txt")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) })
if ($LicenseCandidates.Count -gt 0) {
    $License = Resolve-HostPath $LicenseCandidates[0]
    $DockerArgs += @(
        "--mount", "type=bind,source=$License,target=/licenses/freesurfer/license.txt,readonly",
        "--env", "FS_LICENSE=/licenses/freesurfer/license.txt"
    )
}

for ($i = 0; $i -lt $ForwardArgs.Count; $i++) {
    if ($ForwardArgs[$i] -eq "--qc-excel" -and $i + 1 -lt $ForwardArgs.Count) {
        $QcFile = Resolve-HostPath $ForwardArgs[$i + 1]
        $DockerArgs += @("--mount", "type=bind,source=$QcFile,target=/inputs/qc.xlsx,readonly")
        $ForwardArgs[$i + 1] = "/inputs/qc.xlsx"
        $i++
    }
}

Write-Host "=== sMRI container runtime ==="
Write-Host "IMAGE=$Image"
Write-Host "COMMAND=$Command"
Write-Host "BATCH_DIR=$BatchDir"
Write-Host "Logs and manifests will be written inside the mounted batch directory."

& docker @DockerArgs $Image $Command /data @ForwardArgs
exit $LASTEXITCODE
