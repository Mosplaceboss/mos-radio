# Build MoPlaceStudio production deployment ZIP.
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$StudioRoot = Join-Path $RepoRoot "Studio"
$DistRoot = Join-Path $StudioRoot "dist\MoPlaceStudio"
$ProdRoot = Join-Path $RepoRoot "MoPlaceStudio_Production"
$ZipPath = Join-Path $RepoRoot "MoPlaceStudio_Production.zip"
$ConfigSource = Join-Path $StudioRoot "config"

if (-not (Test-Path (Join-Path $DistRoot "MoPlaceStudio.exe"))) {
    throw "MoPlaceStudio.exe not found. Run Build_Studio_EXE.bat first."
}

if (Test-Path $ProdRoot) {
    Remove-Item -Recurse -Force $ProdRoot
}
if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}

Copy-Item -Path $DistRoot -Destination $ProdRoot -Recurse

Rename-Item -Path (Join-Path $ProdRoot "MoPlaceStudio.exe") -NewName "Studio.exe"

# Writable sidecar folders (empty for first deploy).
foreach ($folder in @("data", "logs", "backups", "assets", "assets\personalities", "assets\voices", "logs\automation")) {
    $path = Join-Path $ProdRoot $folder
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

# Ship clean default configuration only.
$configDest = Join-Path $ProdRoot "config"
if (Test-Path $configDest) {
    Remove-Item -Recurse -Force $configDest
}
New-Item -ItemType Directory -Force -Path $configDest | Out-Null
$configFiles = @(
    "automation.json",
    "news.json",
    "personalities.json",
    "requests.json",
    "schedule.json",
    "settings.json",
    "voice_library.json",
    "integration.local.json.example"
)
foreach ($name in $configFiles) {
    Copy-Item -Path (Join-Path $ConfigSource $name) -Destination (Join-Path $configDest $name)
}

# Remove development artifacts from the runtime bundle.
$devPatterns = @("*.py", "*.pyc", "*.pyo", ".git", ".gitignore", "__pycache__")
foreach ($pattern in $devPatterns) {
    Get-ChildItem -Path $ProdRoot -Recurse -Force -Filter $pattern -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
Get-ChildItem -Path $ProdRoot -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Drop runtime logs copied from local test runs.
Get-ChildItem -Path (Join-Path $ProdRoot "logs") -File -ErrorAction SilentlyContinue | Remove-Item -Force

@'
Mo's Place Studio — First Run
=============================

1. Extract this folder to your station PC (for example C:\MoPlaceStudio).
2. Double-click First_Run_Setup.bat once to create required folders.
3. Double-click Studio.exe to launch Mo's Place Studio.

Folders
-------
config\   Station JSON configuration (editable in Studio)
data\     Local working data
logs\     Application and automation logs
backups\  Timestamped configuration backups before publish

First-time configuration
------------------------
1. Open Settings and confirm station name, timezone, and integration paths.
2. Open Connection Setup, enter live station paths, and test connections.
3. Use Personalities, Voice Library, and Schedule to prepare programming.
4. Keep Operation Mode on development until you are ready to publish.

Notes
-----
- Studio does not modify live automation engines directly.
- Publish actions create backups automatically under backups\.
- For support, keep logs\studio.log after any issue.
'@ | Set-Content -Path (Join-Path $ProdRoot "README_First_Run.txt") -Encoding UTF8

@'
@echo off
setlocal
cd /d "%~dp0"

echo Mo's Place Studio - First Run Setup
echo.

for %%D in (config data logs backups assets assets\personalities assets\voices logs\automation) do (
    if not exist "%%D" mkdir "%%D"
)

if not exist "config\integration.local.json" if exist "config\integration.local.json.example" (
    copy /Y "config\integration.local.json.example" "config\integration.local.json" >nul
)

echo Required folders are ready.
echo You can now launch Studio.exe.
echo.
pause
'@ | Set-Content -Path (Join-Path $ProdRoot "First_Run_Setup.bat") -Encoding ASCII

Compress-Archive -Path $ProdRoot -DestinationPath $ZipPath -Force

$ReleaseNotes = Join-Path $RepoRoot "Releases\RELEASE_NOTES_v2.0_Development.md"
if (Test-Path $ReleaseNotes) {
    Copy-Item -Path $ReleaseNotes -Destination (Join-Path $ProdRoot "RELEASE_NOTES.txt") -Force
}

Write-Output "Production folder: $ProdRoot"
Write-Output "ZIP created: $ZipPath"
