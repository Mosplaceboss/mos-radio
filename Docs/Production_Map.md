# Production Map

This map shows where Mo's Place Radio production components live.

## Computers

| Role | Typical location |
|------|------------------|
| Office PC | Studio, planning, inventory, documentation |
| Radio PC | RadioDJ, live automation, broadcast output |
| Shared platform | `D:\MosPlaceRadioPlatform` or network share |

## Core production software

| System | Purpose |
|--------|---------|
| **Mo's Place Studio** | Control center, programming, operations |
| **RadioDJ** | Music scheduling and on-air playback |
| **Voicebox** | Voice generation API |
| **LiveDJ automation** | Voice tracks, sweepers, show logic |
| **News automation** | RSS, scripts, news audio |
| **Request Watcher** | Listener requests |
| **Website scheduler** | Website automation scripts |
| **Mo's Place Inventory** | Read-only folder scans and reports |

## Studio install location

Production install target:

`D:\MosPlaceRadioPlatform\Studio`

User data preserved during upgrades:

- `config\`
- `assets\`
- `data\`
- `logs\`
- `backups\`

## Safety rules

- Development Mode is default until cutover testing is complete.
- Live publishing requires Production Mode and confirmation.
- Studio does not edit the RadioDJ database in this release.
- Studio does not change Task Scheduler automatically.

## Related guide

See **Folder Map** for the full directory layout.
