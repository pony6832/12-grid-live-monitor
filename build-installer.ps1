# .\build-installer.ps1             -> 12宮格直播監控 安裝程式
# .\build-installer.ps1 -Edition 6  -> 6宮格直播監控 安裝程式
param([ValidateSet("12", "6")][string]$Edition = "12")

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# Builds a single-file installer exe. Run .\build.ps1 (same -Edition) first so dist\ holds the app.
$editions = @{
    "12" = @{ Name = "12宮格直播監控"; Entry = "installer\setup_exe.py";   Config = "config.json"; Icon = "12grid-live-monitor-icon" }
    "6"  = @{ Name = "6宮格直播監控";  Entry = "installer\setup_6grid.py"; Config = "config-6grid.json"; Icon = "6grid-live-monitor-icon" }
}
$spec = $editions[$Edition]
$env:LIVE_MONITOR_EDITION = $Edition

$appName = $spec.Name
$version = (& .\.venv\Scripts\python.exe -c "from app.version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) { throw "讀不到 app\edition.py 的版本號" }
$appDir = Join-Path $PSScriptRoot "dist\$appName"
$payload = Join-Path $PSScriptRoot "build\installer\payload.zip"
$iconPath = Join-Path $PSScriptRoot "assets\$($spec.Icon).ico"
$releaseRoot = Join-Path $PSScriptRoot "release"
$setupName = "$appName-$version-安裝程式"

if (-not (Test-Path (Join-Path $appDir "$appName.exe"))) {
    throw "找不到 $appDir，請先執行 .\build.ps1 -Edition $Edition"
}

& .\.venv\Scripts\python.exe .\tools\make_payload.py $appDir (Join-Path $PSScriptRoot $spec.Config) $payload
if ($LASTEXITCODE -ne 0) { throw "payload 建立失敗" }

& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $setupName `
    --icon $iconPath `
    --paths $PSScriptRoot `
    --paths (Join-Path $PSScriptRoot "installer") `
    --add-data "$payload;." `
    --distpath $releaseRoot `
    --workpath (Join-Path $PSScriptRoot "build\installer-work") `
    --specpath (Join-Path $PSScriptRoot "build") `
    $spec.Entry
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失敗" }

Write-Host "安裝執行檔：" (Join-Path $releaseRoot "$setupName.exe")
