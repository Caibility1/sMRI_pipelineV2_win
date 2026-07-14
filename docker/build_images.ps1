param(
  [string]$AiImage = "smri_pipeline_win:ai",
  [string]$ToolsImage = "smri_pipeline_win:tools",
  [switch]$NoAi,
  [switch]$NoTools
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Invoke-DockerBuild($Dockerfile, $Image) {
  Write-Host "Building $Image from $Dockerfile"
  docker build -f $Dockerfile -t $Image .
  if ($LASTEXITCODE -ne 0) {
    throw "docker build failed for $Image with exit code $LASTEXITCODE"
  }
}

if (-not $NoAi) {
  Invoke-DockerBuild "docker/Dockerfile.smri-ai" $AiImage
}
if (-not $NoTools) {
  Invoke-DockerBuild "docker/Dockerfile.smri-tools" $ToolsImage
}

Write-Host "Docker images ready."
Write-Host "AI image:    $AiImage"
Write-Host "Tools image: $ToolsImage"
