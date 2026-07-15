param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsFromUser
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PipelineDir = Split-Path -Parent $ScriptDir
$WindowsEnv = Join-Path $PipelineDir "environment\windows_env.local.ps1"
$DockerEnv = Join-Path $PipelineDir "environment\docker_env.local.ps1"
if (Test-Path -LiteralPath $WindowsEnv) { . $WindowsEnv }
if (Test-Path -LiteralPath $DockerEnv) { . $DockerEnv }
$Python = if ($env:SMRI_PYTHON) { $env:SMRI_PYTHON } else { "python" }
$Entry = Join-Path $PipelineDir "scripts\jobs\smri_preprocessing_win.py"

Write-Host "=== sMRI preprocessing Windows entrypoint ==="
Write-Host "PIPELINE_DIR=$PipelineDir"
Write-Host "PYTHON=$Python"

& $Python $Entry @ArgsFromUser
exit $LASTEXITCODE
