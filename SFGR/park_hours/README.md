# Park Hours — Setup & Operations Guide

## Overview

Ignition reads the park calendar from a DB table (`park_calendar`) and publishes today's open/close times to MQTT at 5 AM daily. Operators can override times from the main view.

## Files

| File | Purpose |
|---|---|
| `NAS_MOUNT_SETUP.md` | Step-by-step NAS mount instructions for ignition-primary and ignition-standby |
| `db_setup.sql` | Run once to create the `park_calendar` table |
| `import_calendar.py` | Run once per season to load the Excel calendar into the DB |
| `publish_park_hours.py` | Scheduled script (5 AM daily) — publishes to MQTT |

## Setup sequence

1. **NAS:** `ignition-svc` user already created with read/write access to `Ride Data` share.
2. **Both servers:** Follow `NAS_MOUNT_SETUP.md`. Ignition OS user is `sftp` (confirmed).
3. **DB:** Run `db_setup.sql` in Ignition Script Console to create the `park_calendar` table.
4. **Import:** Drop `Calendar_1_.xlsx` in the root of the `Ride Data` share, then run `import_calendar.py` from Script Console. No CSV export needed — reads xlsx directly via POI (bundled with Ignition 8.1.x).
5. **Schedule:** Add `publish_park_hours.py` as a Gateway Scheduled script, daily at 05:00.
6. **Verify:** Run `publish_park_hours.py` manually from Script Console; check MQTT Explorer for `Park/hours/*`.

## Annual calendar update

1. Get new `.xlsx` from operations → drop on NAS share as `Calendar_1_.xlsx` (overwrite).
2. Run `import_calendar.py` from Script Console.
   - Rows with active operator overrides are preserved.
   - All other rows are updated.

## MQTT topics published

| Topic | Type | Example |
|---|---|---|
| `Park/hours/date` | string | `"2026-05-09"` |
| `Park/hours/open_epoch` | int string | `"1746790200"` |
| `Park/hours/close_epoch` | int string | `"1746835200"` |
| `Park/hours/is_open` | `"1"`/`"0"` | `"1"` |
| `Park/hours/closed_today` | `"1"`/`"0"` | `"0"` |

All topics published with QoS 1, retained.

## Override flow (main view)

1. Operator changes open or close time in main view.
2. View script writes `override_open`/`override_close` to DB with operator username and timestamp.
3. View script calls `publish_park_hours.run(force=True)` to immediately re-publish.
4. Overrides persist until manually cleared from the view — the 5 AM script respects them.

## Notes

- Overnight events (e.g. Grad Nite 21:30→03:00): `crosses_midnight=True`, close epoch is +1 day.
- Dual-session days (e.g. `GN 10:30-20:00; 21:30-3:00`): import uses first open, last close from parenthetical.
- Closed days publish `open_epoch=0`, `close_epoch=0`, `is_open=0`.
- `nofail` in fstab ensures servers boot even if NAS is offline.
- Ignition backup path: `Gateway > Config > Backup/Restore` — set output to `/mnt/nas_sfgr/ignition-backups/`.
