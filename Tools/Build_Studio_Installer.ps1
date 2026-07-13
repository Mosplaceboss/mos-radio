# Build production installer package and portable backup ZIP for Mo's Place Studio v2 RC
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$StudioRoot = Join-Path $RepoRoot "Studio"
$DistRoot = Join-Path $StudioRoot "dist\MoPlaceStudio"
$InstallRoot = "D:\MosPlaceRadioPlatform\Studio"
$PortableRoot = Join-Path $RepoRoot "MoPlaceStudio_v2.0_RC_Portable"
$PortableZip = Join-Path $RepoRoot "MoPlaceStudio_v2.0_RC_Portable.zip"
$InstallerZip = Join-Path $RepoRoot "MoPlaceStudio_v2.0_RC_Installer.zip"

Write-Host "Building Studio EXE..."
& (Join-Path $RepoRoot "Tools\Build_Studio_EXE.bat")
if ($LASTEXITCODE -ne 0) { throw "EXE build failed" }

Write-Host "Running installer to test folder..."
& (Join-Path $RepoRoot "Tools\Install_Studio.ps1") -InstallRoot $InstallRoot -SkipShortcuts

Write-Host "Creating portable backup ZIP..."
if (Test-Path $PortableRoot) { Remove-Item -Recurse -Force $PortableRoot }
Copy-Item -Path $InstallRoot -Destination $PortableRoot -Recurse
if (Test-Path $PortableZip) { Remove-Item -Force $PortableZip }
Compress-Archive -Path $PortableRoot -DestinationPath $PortableZip -Force

Write-Host "Creating installer package ZIP..."
$InstallerStage = Join-Path $RepoRoot "MoPlaceStudio_v2.0_RC_Installer"
if (Test-Path $InstallerStage) { Remove-Item -Recurse -Force $InstallerStage }
New-Item -ItemType Directory -Force -Path $InstallerStage | Out-Null
Copy-Item -Path $DistRoot -Destination (Join-Path $InstallerStage "MoPlaceStudio") -Recurse
Copy-Item -Path (Join-Path $RepoRoot "Tools\Install_Studio.ps1") -Destination $InstallerStage
$DocsFolder = Join-Path $RepoRoot "Docs"
if (-not (Test-Path $DocsFolder)) {
    $DocsFolder = Join-Path $RepoRoot "docs"
}
Copy-Item -Path $DocsFolder -Destination (Join-Path $InstallerStage "docs") -Recurse
$ReleaseNotes = Join-Path $RepoRoot "Releases\RELEASE_NOTES_v2.0_RC.md"
if (Test-Path $ReleaseNotes) {
    Copy-Item -Path $ReleaseNotes -Destination (Join-Path $InstallerStage "RELEASE_NOTES.txt")
}
@'
Install Mo's Place Studio v2.0 Release Candidate
==============================================

1. Open PowerShell as Administrator (recommended).
2. Run:  powershell -ExecutionPolicy Bypass -File Install_Studio.ps1
3. Optional: add -StartWithWindows to launch Studio at login.
4. Launch Studio from Desktop shortcut or D:\MosPlaceRadioPlatform\Studio\Studio.exe
5. Complete the First-Run Setup Wizard.

Your config, assets, data, and logs are preserved on upgrade.
Uninstall_Studio.bat removes shortcuts only and preserves station data.
'@ | Set-Content -Path (Join-Path $InstallerStage "INSTALL.txt") -Encoding UTF8
if (Test-Path $InstallerZip) { Remove-Item -Force $InstallerZip }
Compress-Archive -Path $InstallerStage -DestinationPath $InstallerZip -Force

Write-Output "Installed/test path: $InstallRoot"
Write-Output "Portable ZIP: $PortableZip"
Write-Output "Installer ZIP: $InstallerZip"
Write-Output "Studio EXE: $(Join-Path $InstallRoot 'Studio.exe')"
