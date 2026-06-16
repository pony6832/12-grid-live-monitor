$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Running install.ps1 first."
    .\install.ps1
}

.\.venv\Scripts\python.exe .\tools\create_icon.py

$appName = "12宮格直播監控"
$version = "V1.1"
$iconPath = Join-Path $PSScriptRoot "assets\12grid-live-monitor-icon.ico"

.\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --windowed `
    --name $appName `
    --icon $iconPath `
    --add-data "config.json;." `
    app\chrome_embed.py

$releaseRoot = Join-Path $PSScriptRoot "release"
$packageDir = Join-Path $releaseRoot "$appName-$version"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "dist\$appName") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "config.json") (Join-Path $packageDir "$appName\config.json")
Copy-Item -Force (Join-Path $PSScriptRoot "installer\安裝-12宮格直播監控-V1.1.cmd") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "installer\安裝-12宮格直播監控-V1.1.ps1") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "README.md") $packageDir

$zipPath = Join-Path $releaseRoot "$appName-$version.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath

Write-Host "$version package created:"
Write-Host $packageDir
Write-Host $zipPath
