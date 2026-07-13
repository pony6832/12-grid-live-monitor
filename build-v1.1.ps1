$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Running install.ps1 first."
    .\install.ps1
}

.\.venv\Scripts\python.exe -m pip install pyinstaller pillow
if ($LASTEXITCODE -ne 0) {
    throw "無法安裝建置相依套件。"
}
.\.venv\Scripts\python.exe .\tools\create_icon.py
if ($LASTEXITCODE -ne 0) {
    throw "無法建立應用程式圖示。"
}

$appName = "12宮格直播監控"
$version = "V1.1"
$iconPath = Join-Path $PSScriptRoot "assets\12grid-live-monitor-icon.ico"

.\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --windowed `
    --name $appName `
    --icon $iconPath `
    app\light_player.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 建置失敗。"
}

$releaseRoot = Join-Path $PSScriptRoot "release"
$packageDir = Join-Path $releaseRoot "$appName-$version"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "dist\$appName") $packageDir
$packageConfigPath = Join-Path $packageDir "$appName\config.json"
$env:PACKAGE_CONFIG_PATH = $packageConfigPath
.\.venv\Scripts\python.exe -c "import os; from pathlib import Path; from app.core.config import AppConfig; AppConfig().save(Path(os.environ['PACKAGE_CONFIG_PATH']))"
Remove-Item Env:PACKAGE_CONFIG_PATH
Copy-Item -Force (Join-Path $PSScriptRoot "installer\安裝-12宮格直播監控-V1.1.cmd") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "installer\安裝-12宮格直播監控-V1.1.ps1") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "install-light-player.ps1") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "README.md") $packageDir

$zipPath = Join-Path $releaseRoot "$appName-$version.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath

Write-Host "$version package created:"
Write-Host $packageDir
Write-Host $zipPath
