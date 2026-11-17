$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Running install.ps1 first."
    .\install.ps1
}

.\.venv\Scripts\python.exe .\tools\create_icon.py
if ($LASTEXITCODE -ne 0) { throw "圖示建立失敗" }

# The version lives only in app\version.py.
$appName = "12宮格直播監控"
$version = (& .\.venv\Scripts\python.exe -c "from app.version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) { throw "讀不到 app\version.py 的版本號" }
$iconPath = Join-Path $PSScriptRoot "assets\12grid-live-monitor-icon.ico"

.\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --windowed `
    --name $appName `
    --icon $iconPath `
    app\chrome_embed.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失敗" }

$internal = Join-Path $PSScriptRoot "dist\$appName\_internal"
$qtDir = Join-Path $internal "PySide6"

# Qt 6.11 needs a recent VC++ runtime. PyInstaller leaves Python's older 14.38 VCRUNTIME140 in
# _internal root, which wins over the newer copies in PySide6\ and breaks QtWidgets on machines
# whose system runtime is old ("DLL load failed while importing QtWidgets"). Make the app
# self-contained by putting the newest bundled runtime in _internal root.
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

# The app is plain widgets plus network and websockets. PyInstaller also pulls in the software
# OpenGL renderer and the Quick/QML/PDF/virtual-keyboard stack through Qt plugins; none is used.
$unused = @(
    "opengl32sw.dll", "Qt6Quick.dll", "Qt6Qml.dll", "Qt6QmlModels.dll", "Qt6QmlMeta.dll",
    "Qt6QmlWorkerScript.dll", "Qt6Pdf.dll", "Qt6VirtualKeyboard.dll", "Qt6OpenGL.dll",
    "plugins\imageformats\qpdf.dll", "plugins\platforminputcontexts\qtvirtualkeyboardplugin.dll"
)
$saved = 0
foreach ($name in $unused) {
    $path = Join-Path $qtDir $name
    if (Test-Path $path) { $saved += (Get-Item $path).Length; Remove-Item -Force $path }
}
Write-Host ("  移除用不到的 Qt 元件：{0:N1} MB" -f ($saved / 1MB))

# Running the build from dist\ leaves user state behind; it must never reach a package.
foreach ($name in @("data", "config.json", "config.json.tmp", "config.json.broken")) {
    $path = Join-Path $PSScriptRoot "dist\$appName\$name"
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
}

$releaseRoot = Join-Path $PSScriptRoot "release"
$packageDir = Join-Path $releaseRoot "$appName-$version"
if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "dist\$appName") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "config.json") (Join-Path $packageDir "$appName\config.json")
Copy-Item -Force (Join-Path $PSScriptRoot "installer\安裝-12宮格直播監控.cmd") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "installer\install.ps1") $packageDir
Copy-Item -Force (Join-Path $PSScriptRoot "README.md") $packageDir

$zipPath = Join-Path $releaseRoot "$appName-$version.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath

Write-Host "$version package created:"
Write-Host $packageDir
Write-Host $zipPath
