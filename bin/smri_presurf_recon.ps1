param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsFromUser
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PipelineDir = Split-Path -Parent $ScriptDir
$Python = if ($env:SMRI_PYTHON) { $env:SMRI_PYTHON } else { "python" }
$Entry = Join-Path $PipelineDir "scripts\jobs\smri_presurf_recon_win.py"

Write-Host "=== sMRI presurf/recon Windows entrypoint ==="
Write-Host "PIPELINE_DIR=$PipelineDir"
Write-Host "PYTHON=$Python"

& $Python $Entry @ArgsFromUser
exit $LASTEXITCODE
