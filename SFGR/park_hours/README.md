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

1. **NAS:** Add `ignition_svc` user to NAS `10.250.2.10` with read access to the share.
2. **Both servers:** Follow `NAS_MOUNT_SETUP.md` to mount the NAS share at `/mnt/nas_sfgr`.
3. **DB:** Run `db_setup.sql` in Ignition Script Console to create the table.
4. **Calendar prep:** Export `Calendar_1_.xlsx` as CSV, save as `park_calendar.csv` on the NAS share.
5. **Import:** Run `import_calendar.py` from Ignition Script Console. Check logs for errors.
6. **Schedule:** Add `publish_park_hours.py` as a Gateway Scheduled script, daily at 05:00.
7. **Verify:** Run `publish_park_hours.py` manually from Script Console; check MQTT Explorer for `Park/hours/*` topics.

## Annual calendar update

1. Get new `.xlsx` from operations.
2. Export as CSV → `park_calendar.csv` → save to NAS share (overwrite).
3. Run `import_calendar.py` from Script Console.
   - Existing rows with active overrides are preserved.
   - Rows without overrides are updated.

## CSV export instructions (Excel)

The import script reads CSV, not xlsx directly (Ignition Jython limitation).
- Open `Calendar_1_.xlsx`
- File > Save As > CSV (Comma delimited)
- Save as `park_calendar.csv` in the same NAS folder
- Column order must match original: Date, HoursType, BudgetedAttendance, ProjectedAttendance, ActualAttendance, Closed, ...

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
4. At midnight, the 5 AM script will use calendar values again (overrides are not cleared automatically — clear them in the view if needed for next day).

## Notes

- Overnight events (e.g. Grad Nite 21:30→03:00): `crosses_midnight=True`, close epoch is +1 day.
- Dual-session days (e.g. `GN 10:30-20:00; 21:30-3:00`): import script uses first open, last close from parenthetical.
- Closed days publish `open_epoch=0`, `close_epoch=0`, `is_open=0`.
- `nofail` in fstab ensures servers boot even if NAS is offline.
