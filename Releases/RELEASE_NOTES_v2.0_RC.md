# Mo's Place Studio v2.0 Release Candidate — Release Notes

**Version:** Mo's Place Studio v2.0 Release Candidate  
**Build:** 2.0.0-rc1  
**Date:** July 2026

## Highlights

- **First-Run Setup Wizard** — configure station name, logo, platform paths, and test connections without editing code
- **Daily Operations screen** — one simple page for everyday broadcast work
- **Operating modes** — Owner, Staff, and Advanced with navigation filtering
- **Windows installer** — installs to `D:\MosPlaceRadioPlatform\Studio` with Desktop and Start Menu shortcuts
- **Update system** — import approved update packages with automatic backup and rollback
- **Plain-English documentation** — Quick Start, Daily Operations, Staff, Backup, Emergency Recovery, Production Map, Folder Map

## Safety

- Does not modify the currently running station by default
- Development Mode remains available; Production Mode requires confirmation
- No RadioDJ database editing in this release
- No Task Scheduler changes
- Uninstall removes application files only — station data is preserved

## Install locations

| Item | Path |
|------|------|
| Application | `D:\MosPlaceRadioPlatform\Studio\Studio.exe` |
| Platform data | `D:\MosPlaceRadioPlatform\` |
| Backups | `D:\MosPlaceRadioPlatform\Backups\` |
| Documentation | `docs\` folder in repository / copied to platform Documentation |

## Upgrade notes

- Existing `config\`, `assets\`, `data\`, and `logs\` folders are preserved during install and update
- Run First-Run Setup Wizard once after install to validate paths
- Switch to Advanced Mode for update import and rollback

## Known limitations

- RadioDJ queue view is read-only (no database access yet)
- Screenshots in guides are placeholders — add station screenshots after deployment
- Advanced Mode default password is documented in Advanced settings (change after install)
