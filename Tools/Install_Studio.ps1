# Install Mo's Place Studio to D:\MosPlaceRadioPlatform\Studio
param(
    [string]$InstallRoot = "D:\MosPlaceRadioPlatform\Studio",
    [string]$SourceRoot = "",
    [switch]$StartWithWindows,
    [switch]$SkipShortcuts
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $SourceRoot) {
    $SourceRoot = Join-Path $RepoRoot "Studio\dist\MoPlaceStudio"
}
if (-not (Test-Path (Join-Path $SourceRoot "MoPlaceStudio.exe"))) {
    throw "MoPlaceStudio.exe not found at $SourceRoot. Run Tools\Build_Studio_EXE.bat first."
}

$PlatformRoot = Split-Path -Parent $InstallRoot
$Preserve = @("config", "assets", "data", "logs", "backups")

Write-Host "Installing Mo's Place Studio to $InstallRoot"

foreach ($folder in @(
    $InstallRoot,
    "$PlatformRoot\Automation\LiveDJ",
    "$PlatformRoot\Automation\News",
    "$PlatformRoot\Automation\Requests",
    "$PlatformRoot\Automation\Website",
    "$PlatformRoot\Audio\Generated",
    "$PlatformRoot\Assets\Voices",
    "$PlatformRoot\Backups",
    "$PlatformRoot\Documentation",
    "$PlatformRoot\Documentation\InventoryReports",
    "$PlatformRoot\Logs",
    "$PlatformRoot\Reports",
    "$PlatformRoot\StationData",
    "$PlatformRoot\Website"
)) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
}

if (-not (Test-Path $InstallRoot)) {
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
}

Get-ChildItem -Path $SourceRoot -Force | ForEach-Object {
    if ($Preserve -contains $_.Name -and (Test-Path (Join-Path $InstallRoot $_.Name))) {
        Write-Host "Preserving existing $($_.Name) folder"
        return
    }
    Copy-Item -Path $_.FullName -Destination (Join-Path $InstallRoot $_.Name) -Recurse -Force
}

Rename-Item -Path (Join-Path $InstallRoot "MoPlaceStudio.exe") -NewName "Studio.exe" -Force -ErrorAction SilentlyContinue

foreach ($sidecar in $Preserve) {
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot $sidecar) | Out-Null
}

$DocsSource = Join-Path $RepoRoot "Docs"
if (-not (Test-Path $DocsSource)) {
    $DocsSource = Join-Path $RepoRoot "docs"
}
$DocsDest = Join-Path $PlatformRoot "Documentation\StudioGuides"
if (Test-Path $DocsSource) {
    Copy-Item -Path $DocsSource -Destination $DocsDest -Recurse -Force
}

$ReleaseNotes = Join-Path $RepoRoot "Releases\RELEASE_NOTES_v2.0_RC.md"
if (Test-Path $ReleaseNotes) {
    Copy-Item -Path $ReleaseNotes -Destination (Join-Path $InstallRoot "RELEASE_NOTES.txt") -Force
}

if (-not $SkipShortcuts) {
    $WshShell = New-Object -ComObject WScript.Shell
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Mo's Place Studio"
    New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
    $ShortcutPath = Join-Path $Desktop "Mo's Place Studio.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Join-Path $InstallRoot "Studio.exe"
    $Shortcut.WorkingDirectory = $InstallRoot
    $Shortcut.Description = "Mo's Place Studio"
    $Shortcut.Save()
    $StartShortcut = Join-Path $StartMenu "Mo's Place Studio.lnk"
    $StartLink = $WshShell.CreateShortcut($StartShortcut)
    $StartLink.TargetPath = Join-Path $InstallRoot "Studio.exe"
    $StartLink.WorkingDirectory = $InstallRoot
    $StartLink.Save()
}

if ($StartWithWindows) {
    $RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    Set-ItemProperty -Path $RunKey -Name "MoPlaceStudio" -Value "`"$InstallRoot\Studio.exe`""
}

@'
@echo off
setlocal
echo Mo's Place Studio Uninstaller
echo.
echo This removes Studio application files and shortcuts.
echo Your station data under D:\MosPlaceRadioPlatform is NOT removed.
echo.
set /p CONFIRM=Continue? [Y/N]:
if /I not "%CONFIRM%"=="Y" exit /b 0
set INSTALL=%~dp0
del /Q "%USERPROFILE%\Desktop\Mo's Place Studio.lnk" 2>nul
rmdir /S /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Mo's Place Studio" 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v MoPlaceStudio /f 2>nul
echo.
echo Shortcuts removed. Delete this Studio folder manually if you want to remove the application files.
echo Config, assets, data, logs, and backups were preserved.
pause
'@ | Set-Content -Path (Join-Path $InstallRoot "Uninstall_Studio.bat") -Encoding ASCII

Write-Output "Installed to: $InstallRoot"
Write-Output "Executable: $(Join-Path $InstallRoot 'Studio.exe')"
