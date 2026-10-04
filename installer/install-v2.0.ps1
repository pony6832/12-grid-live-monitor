param([string]$TargetDir = "", [switch]$NoShortcuts)

$ErrorActionPreference = "Stop"

$appName = "12宮格直播監控"
$sourceDir = Join-Path $PSScriptRoot $appName
$installRoot = Join-Path $env:LOCALAPPDATA "Programs"
$installDir = if ($TargetDir) { $TargetDir } else { Join-Path $installRoot $appName }
$exePath = Join-Path $installDir "$appName.exe"

if (-not (Test-Path $sourceDir)) {
    throw "找不到安裝來源資料夾：$sourceDir"
}

if (Get-Process -Name $appName -ErrorAction SilentlyContinue) {
    throw "$appName 正在執行，請先關閉程式再安裝。"
}

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null

# config.json and data\ (Google login) are never moved or deleted: Chrome may hold files in
# data\ open, so an upgrade replaces only the program files around them.
$preserved = @("config.json", "data")
$upgraded = $false
if (Test-Path $installDir) {
    $upgraded = $true
    # V1.x builds kept the Chrome profile under _internal\data; a same-volume rename is all-or-nothing.
    $legacyProfile = Join-Path $installDir "_internal\data\chrome_monitor_profile"
    $newProfile = Join-Path $installDir "data\chrome_monitor_profile"
    if ((Test-Path $legacyProfile) -and -not (Test-Path $newProfile)) {
        New-Item -ItemType Directory -Force -Path (Join-Path $installDir "data") | Out-Null
        [System.IO.Directory]::Move($legacyProfile, $newProfile)
    }
    Get-ChildItem -LiteralPath $installDir -Force |
        Where-Object { $preserved -notcontains $_.Name } |
        Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

$hasConfig = Test-Path (Join-Path $installDir "config.json")
Get-ChildItem -LiteralPath $sourceDir -Force |
    Where-Object { -not ($hasConfig -and $_.Name -eq "config.json") } |
    Copy-Item -Destination $installDir -Recurse -Force

$shell = New-Object -ComObject WScript.Shell
$shortcutPaths = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "$appName.lnk"),
    (Join-Path (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs") "$appName.lnk")
)
if ($NoShortcuts) { $shortcutPaths = @() }
foreach ($path in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $exePath
    $shortcut.WorkingDirectory = $installDir
    $shortcut.IconLocation = $exePath
    $shortcut.Save()
}

Write-Host "安裝完成：$installDir"
if ($upgraded) {
    Write-Host "已保留原本的連結設定與 Google 登入狀態。"
}
