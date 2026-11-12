$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Running install.ps1 first."
    .\install.ps1
}

.\.venv\Scripts\python.exe .\tools\create_icon.py

$appName = "12宮格直播監控"
$version = "V3"
$iconPath = Join-Path $PSScriptRoot "assets\12grid-live-monitor-icon.ico"

.\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --windowed `
    --name $appName `
    --icon $iconPath `
    --add-data "config.json;." `
    app\chrome_embed.py

# Qt 6.11 needs a recent VC++ runtime. PyInstaller leaves Python's older 14.38 VCRUNTIME140 in
# _internal root, which wins over the newer copies in PySide6\ and breaks QtWidgets on machines
# whose system runtime is old ("DLL load failed while importing QtWidgets"). Make the app
# self-contained by putting the newest bundled runtime in _internal root.
$internal = Join-Path $PSScriptRoot "dist\$appName\_internal"
$qtDir = Join-Path $internal "PySide6"
$crtNames = @("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll")
foreach ($name in $crtNames) {
    $src = Join-Path $qtDir $name
    if (-not (Test-Path $src)) { throw "PySide6 缺少 $name，無法修正 VC++ 執行階段" }
    $dst = Join-Path $internal $name
    if ((Test-Path $dst) -and ((Get-Item $dst).VersionInfo.FileVersionRaw -gt (Get-Item $src).VersionInfo.FileVersionRaw)) { continue }
    Copy-Item -Force $src $dst
}
foreach ($name in $crtNames) {
    Write-Host ("  {0} {1}" -f $name, (Get-Item (Join-Path $internal $name)).VersionInfo.FileVersion)
}

$releaseRoot = Join-Path $PSScriptRoot "release"
$packageDir = Join-Path $releaseRoot "$appName-$version"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "dist\$appName") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "config.json") (Join-Path $packageDir "$appName\config.json")
Copy-Item -Force (Join-Path $PSScriptRoot "installer\安裝-12宮格直播監控-V3.cmd") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "installer\install-v3.ps1") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "README.md") $packageDir

$zipPath = Join-Path $releaseRoot "$appName-$version.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath

Write-Host "$version package created:"
Write-Host $packageDir
Write-Host $zipPath
