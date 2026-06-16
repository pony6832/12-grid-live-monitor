$ErrorActionPreference = "Stop"

$appName = "12宮格直播監控"
$sourceDir = Join-Path $PSScriptRoot $appName
$installRoot = Join-Path $env:LOCALAPPDATA "Programs"
$installDir = Join-Path $installRoot $appName
$exePath = Join-Path $installDir "$appName.exe"

if (-not (Test-Path $sourceDir)) {
    throw "找不到安裝來源資料夾：$sourceDir"
}

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
$configBackup = $null
if (Test-Path $installDir) {
    $existingConfig = Join-Path $installDir "config.json"
    if (Test-Path $existingConfig) {
        $configBackup = Join-Path $env:TEMP "12grid-live-monitor-config-backup.json"
        Copy-Item -Force $existingConfig $configBackup
    }
}
if (Test-Path $installDir) {
    Remove-Item -Recurse -Force $installDir
}
Copy-Item -Recurse -Force $sourceDir $installDir
if ($configBackup -and (Test-Path $configBackup)) {
    Copy-Item -Force $configBackup (Join-Path $installDir "config.json")
}

$shell = New-Object -ComObject WScript.Shell
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"
$shortcut = $shell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $exePath
$shortcut.Save()

$startMenuDir = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
$startShortcut = Join-Path $startMenuDir "$appName.lnk"
$shortcut = $shell.CreateShortcut($startShortcut)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $exePath
$shortcut.Save()

Write-Host "安裝完成：$installDir"
Write-Host "桌面捷徑：$desktopShortcut"
