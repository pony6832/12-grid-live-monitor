$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# Builds a single-file installer exe. Run .\build-v2.0.ps1 first so dist\ holds the current app.
$appName = "12宮格直播監控"
$version = "V2.0"
$appDir = Join-Path $PSScriptRoot "dist\$appName"
$payload = Join-Path $PSScriptRoot "build\installer\payload.zip"
$iconPath = Join-Path $PSScriptRoot "assets\12grid-live-monitor-icon.ico"
$releaseRoot = Join-Path $PSScriptRoot "release"
$setupName = "$appName-$version-安裝程式"

if (-not (Test-Path (Join-Path $appDir "$appName.exe"))) {
    throw "找不到 $appDir，請先執行 .\build-v2.0.ps1"
}

& .\.venv\Scripts\python.exe .\tools\make_payload.py $appDir (Join-Path $PSScriptRoot "config.json") $payload
if ($LASTEXITCODE -ne 0) { throw "payload 建立失敗" }

& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $setupName `
    --icon $iconPath `
    --add-data "$payload;." `
    --distpath $releaseRoot `
    --workpath (Join-Path $PSScriptRoot "build\installer-work") `
    --specpath (Join-Path $PSScriptRoot "build") `
    installer\setup_exe.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失敗" }

Write-Host "安裝執行檔：" (Join-Path $releaseRoot "$setupName.exe")
