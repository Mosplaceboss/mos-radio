# Folder Map

Default platform root:

`D:\MosPlaceRadioPlatform`

## Main folders

| Folder | Purpose |
|--------|---------|
| `Studio\` | Mo's Place Studio application |
| `Automation\LiveDJ\` | LiveDJ scripts, configs, watchers |
| `Automation\News\` | News tasks, feeds, scripts |
| `Automation\Requests\` | Request watcher |
| `Automation\Website\` | Website scheduler scripts |
| `Automation\Advertising\` | Advertising automation |
| `Audio\Generated\` | Generated voice output |
| `Audio\News\` | News audio output |
| `Audio\Requests\` | Request audio output |
| `Audio\Commercials\` | Commercial audio |
| `Audio\Promos\` | Promos |
| `Audio\Sweepers\` | Sweepers |
| `Assets\Voices\` | Shared voice reference files |
| `Assets\Personalities\` | Personality images |
| `StationData\` | Development copies of manager data |
| `Backups\` | Timestamped backups and update backups |
| `Documentation\` | Reports and inventory output |
| `Documentation\InventoryReports\` | Inventory JSON reports |
| `Logs\` | Platform logs |
| `Reports\` | Station reports |
| `Website\` | Website content |

## External paths (configured in Setup)

| Path | Example |
|------|---------|
| RadioDJ | `\\MOSPLACERADIO\RadioDJv3` |
| Music library | `W:\Music` |

## Studio writable folders

Inside `Studio\`:

| Folder | Purpose |
|--------|---------|
| `config\` | Settings and station JSON |
| `assets\` | Uploaded logos, portraits, personalities |
| `data\` | Local working data |
| `logs\` | Studio and automation monitor logs |
| `backups\` | Local sidecar backups |

## Inventory output

`D:\MosPlaceRadioPlatform\Documentation\InventoryReports\Inventory.json`

## Notes

- Paths are managed in **Platform Manager** (Advanced Mode).
- First-Run Setup Wizard pre-fills these defaults.
- Inventory scans are read-only and do not modify production files.
