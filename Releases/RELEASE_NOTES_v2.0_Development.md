# Mo's Place Studio v2.0 Development — Release Notes

**Release:** Mo's Place Studio v2.0 Development  
**Date:** July 2026  
**Build type:** Development (live publishing disabled)

## Overview

Mo's Place Studio v2 integrates all station management modules into one consistent desktop application with grouped navigation, shared Platform Manager paths, and a unified dashboard.

## Included Modules

- Station Manager — on-air overview, service health, alerts
- Dashboard — service status, module summaries, alerts, quick actions
- Help — plain-English module guide and daily checklist
- Programming Manager — shows, formats, clocks, validation
- Music Manager — library browsing (development mode)
- Personalities — host profiles and assignments
- Voice Library — voice profiles for automation
- Schedule — weekly show schedule
- Requests — listener request settings (development copy)
- Advertising Manager — sponsors and campaigns
- Website & Audience Manager — content and audience planning
- News & Content Manager — news feeds, scripts, development output
- Inventory — launch Inventory app and review scan reports
- Operations Manager — backups, deployment packages, migration staging
- Reports — station reports
- Settings — station preferences and operation mode
- Platform Manager — shared folder paths for all modules
- Advanced — Connection Setup, LiveDJ, automation, and technical tools

## Safety

- **Development Mode is the default.** Live publishing to production is blocked.
- No Task Scheduler changes.
- No RadioDJ database changes.
- No automatic migrations.
- Production files are not modified by this build.

## Requirements

- Windows 10 or later
- Platform paths configured in Platform Manager (defaults use `D:\MosPlaceRadioPlatform\`)

## First Run

1. Extract the deployment ZIP to your development PC.
2. Run `First_Run_Setup.bat` once.
3. Launch `Studio.exe`.
4. Open Platform Manager and validate paths.
5. Keep Operation Mode on **Development** until cutover testing is complete.

## Known Limitations (Development Build)

- Live publish actions return a plain-English message when Development Mode is active.
- Inventory requires a separate scan via Mo's Place Inventory for full reports.
- Music Manager is read-only in this build.

## Support

Keep `logs\studio.log` after any issue for troubleshooting.
