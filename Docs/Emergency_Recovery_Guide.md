# Emergency Recovery Guide

Use this guide when Studio or station services stop working.

## Step 1 — Stay calm and do not delete production files

Studio is designed **not** to delete or move live station files automatically. Avoid manual cleanup on the broadcast PC until you know what failed.

## Step 2 — Open Daily Operations

Refresh status and read alerts in plain English. Note which service is red:

- RadioDJ
- Voicebox
- LiveDJ watcher
- News tasks
- Request watcher
- Website scheduler

## Step 3 — Quick recovery actions

| Problem | Try this |
|---------|----------|
| RadioDJ not running | Open RadioDJ from Daily Operations |
| Voicebox down | Restart Voicebox on its PC, then refresh |
| LiveDJ watcher stopped | Restart LiveDJ Watcher (confirm when asked) |
| News stale | Run News Now (confirm when asked) |
| Requests unavailable | Restart Request Watcher (confirm when asked) |

## Step 4 — Check folders

In Advanced Mode, open **Platform Manager** and validate paths. Confirm:

- Platform root exists: `D:\MosPlaceRadioPlatform`
- Automation folders exist for LiveDJ, News, and Requests
- Audio output folders exist

## Step 5 — Restore from backup

If configuration was changed accidentally:

1. Switch to Advanced Mode.
2. Open **Operations Manager → Backup Manager**.
3. Restore the most recent good backup.

## Step 6 — Roll back a bad Studio update

1. Open **Settings → Updates** in Advanced Mode.
2. Click **Roll Back Last Update**.

## Step 7 — Collect logs

If you need outside help, keep these folders:

- `D:\MosPlaceRadioPlatform\Studio\logs`
- `D:\MosPlaceRadioPlatform\Logs`

## Still stuck?

Re-run **First-Run Setup Wizard** from Settings to re-test connections without editing code.
