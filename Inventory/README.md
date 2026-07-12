# Mo's Place Inventory

Read-only Windows desktop utility for mapping the Mo's Place Radio environment across Office and Radio computers.

## Safety

This tool is **read-only**. It never copies, deletes, moves, renames, or modifies scanned files. The only writes are report outputs to the folder you choose.

## Run

Double-click `Launch_Inventory.bat` or run:

```bat
python app\main.py
```

## Build EXE

Double-click `Tools\Build_Inventory_EXE.bat`.

Output: `Inventory\dist\MoPlaceInventory\MoPlaceInventory.exe`

## Tabs

- Overview
- Computers
- Scheduled Tasks
- Services
- Production Map
- Duplicates
- Folder Comparison
- Reports
- Recommendations

## Reports Generated

- `Inventory.json`
- `ProductionMap.html`
- `FolderMap.html`
- `ScheduledTasks.html`
- `DuplicateFiles.html`
- `Recommendations.html`

## Verify

```bat
python verify_inventory.py
```
