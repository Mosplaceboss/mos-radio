# Backup and Restore Guide

Mo's Place Studio protects your work with automatic and manual backups.

## What gets backed up

- Studio settings
- Platform configuration
- Personalities and voice library
- Schedules and programming data
- Operations and deployment records

Backups are stored under:

`D:\MosPlaceRadioPlatform\Backups`

## Create a backup before big changes

1. Open **Operations Manager**.
2. Go to **Backup Manager**.
3. Choose the backup type you need.
4. Click **Create Backup**.
5. Confirm when asked.

## Restore from backup

1. Open **Operations Manager**.
2. Choose **Restore Last Backup** or select a backup from history.
3. Confirm twice if Studio asks — restores replace local working copies.

Restores do **not** change the live on-air station unless you explicitly publish in Production Mode.

## Update backups

Before importing a Studio update package, Studio automatically creates a pre-update backup in:

`D:\MosPlaceRadioPlatform\Backups\Updates`

You can roll back from **Settings → Updates** in Advanced Mode.

## Best practice

Create a backup before:

- Major schedule changes
- Personality or voice updates
- Testing a new Studio update
- Deployment package testing
