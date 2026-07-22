param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsFromUser
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PipelineDir = Split-Path -Parent $ScriptDir
$Launcher = Join-Path $PipelineDir "scripts\steps\smri_docker_launcher.ps1"
$Image = if ($env:SMRI_RUNTIME_IMAGE) { $env:SMRI_RUNTIME_IMAGE } else { "caibility1/smri_pipeline_win:runtime-v2-2026-07-22" }

& $Launcher -Command preprocess -Image $Image @ArgsFromUser
exit $LASTEXITCODE
