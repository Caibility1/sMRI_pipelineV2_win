param(
    [string]$WslDistro = "Ubuntu-22.04",
    [string]$FslSource = "",
    [string]$ContextImage = "smri-fsl-context:6.0.7.22",
    [string]$ArchivePath = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Convert-ToWslPath([string]$WindowsPath) {
    $FullPath = [IO.Path]::GetFullPath($WindowsPath)
    if ($FullPath -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "FSL cache archive must be on a Windows drive: $FullPath"
    }
    $Drive = $Matches[1].ToLowerInvariant()
    $Tail = $Matches[2].Replace('\', '/')
    return "/mnt/$Drive/$Tail"
}

function Test-DockerImage([string]$Image) {
    $PreviousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & docker image inspect $Image 1>$null 2>$null
    $Exists = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $PreviousErrorAction
    return $Exists
}

if ((Test-DockerImage $ContextImage) -and -not $Force) {
    Write-Host "FSL context image already exists: $ContextImage"
    exit 0
}

if (-not $FslSource) {
    $WslUser = (& wsl.exe -d $WslDistro -- whoami).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $WslUser) {
        throw "Cannot determine the default user for WSL distro $WslDistro"
    }
    $FslSource = "/home/$WslUser/fsl"
}

& wsl.exe -d $WslDistro -- test -d $FslSource
if ($LASTEXITCODE -ne 0) {
    throw "FSL source does not exist inside $WslDistro`: $FslSource"
}

if (-not $ArchivePath) {
    $ArchivePath = Join-Path $RepoRoot "docker\.cache\fsl-6.0.7.22.tar"
}
$ArchivePath = [IO.Path]::GetFullPath($ArchivePath)
$ArchiveDir = Split-Path -Parent $ArchivePath
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null
$ArchiveWsl = Convert-ToWslPath $ArchivePath

Write-Host "Creating FSL archive in WSL (this can take several minutes)..."
Write-Host "  source:  $WslDistro`:$FslSource"
Write-Host "  archive: $ArchivePath"
& wsl.exe -d $WslDistro -- tar -C $FslSource -cf $ArchiveWsl .
if ($LASTEXITCODE -ne 0) {
    throw "WSL tar failed with exit code $LASTEXITCODE"
}

Write-Host "Importing cached FSL build context: $ContextImage"
& docker import $ArchivePath $ContextImage
if ($LASTEXITCODE -ne 0) {
    throw "docker import failed with exit code $LASTEXITCODE"
}
if (-not (Test-DockerImage $ContextImage)) {
    throw "Docker did not create the expected image: $ContextImage"
}

Write-Host "FSL context image ready: $ContextImage"
Write-Host "The reusable archive remains at: $ArchivePath"