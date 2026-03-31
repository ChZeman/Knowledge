"""
Park Calendar Import Script
===========================
Run from Ignition Script Console (Tools > Script Console) or as a one-off Gateway script.
Reads the Excel calendar from the NAS mount and populates the park_calendar DB table.

Run once per season, or whenever the calendar is updated on the NAS.

Requirements:
  - NAS mounted at /mnt/nas_sfgr (see NAS_MOUNT_SETUP.md)
  - park_calendar table created (see db_setup.sql)
  - openpyxl available in Ignition's Jython path, OR use the CSV export fallback below

Note: Ignition uses Jython 2.7. openpyxl is not available by default.
Workflow: export the Excel file as CSV from the NAS before running, OR
use the xlrd-based read below which works with .xlsx in some Ignition versions.
The recommended approach is to save a CSV copy alongside the .xlsx on the NAS.
"""

import re
import csv
import os
from datetime import datetime, date, time, timedelta

# ── Configuration ────────────────────────────────────────────────────────────
DB_NAME       = "SFGR"                          # Ignition DB connection name
CSV_PATH      = "/mnt/nas_sfgr/park_calendar.csv"  # CSV export of Calendar_1_.xlsx
# Column indices in the CSV (0-based), matching Calendar_1_.xlsx column order:
COL_DATE      = 0
COL_HOURSTYPE = 1
COL_CLOSED    = 5   # boolean column
# ─────────────────────────────────────────────────────────────────────────────


def parse_times(hours_type_str):
    """
    Extract open and close times from the HoursType string.
    Canonical format always contains parenthetical: (H:MMam - H:MMpm) or (HH:MM - HH:MM)
    Returns (open_str, close_str, crosses_midnight) as "HH:MM" 24h strings, or (None, None, False).
    """
    s = str(hours_type_str).strip()

    # Match times inside parentheses: (10:30AM - 8:00PM) or (9:30PM - 3:00AM)
    m = re.search(r'\((\d{1,2}:\d{2}\s*[AP]M)\s*[-\u2013]\s*(\d{1,2}:\d{2}\s*[AP]M)\)', s, re.IGNORECASE)
    if not m:
        return None, None, False

    def to_24h(t_str):
        t_str = t_str.strip().upper().replace(' ', '')
        for fmt in ('%I:%M%p', '%I:%M%p'):
            try:
                return datetime.strptime(t_str, fmt).strftime('%H:%M')
            except ValueError:
                pass
        return None

    open_24  = to_24h(m.group(1))
    close_24 = to_24h(m.group(2))

    if open_24 is None or close_24 is None:
        return None, None, False

    # Detect overnight: close time is numerically earlier than open time
    # e.g. open=21:30, close=03:00 — close is next day
    # Also catches 00:00 (midnight) as a close
    crosses = close_24 <= open_24 if close_24 != '00:00' else True

    return open_24, close_24, crosses


def run():
    if not os.path.exists(CSV_PATH):
        system.util.getLogger('ParkCalendarImport').error(
            'CSV file not found: ' + CSV_PATH + 
            ' -- export Calendar_1_.xlsx as CSV and save to NAS share.'
        )
        return

    inserted = 0
    updated  = 0
    errors   = []

    with open(CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header row

        for row_num, row in enumerate(reader, start=2):
            try:
                if len(row) < 6:
                    continue

                # Parse date
                date_raw = row[COL_DATE].strip()
                if not date_raw:
                    continue
                # Handle both "2026-04-23" and "2026-04-23 00:00:00" formats
                date_str = date_raw.split(' ')[0]
                cal_date = datetime.strptime(date_str, '%Y-%m-%d').date()

                hours_type = row[COL_HOURSTYPE].strip()

                # Closed flag — handle "True"/"False"/"1"/"0"
                closed_raw = row[COL_CLOSED].strip().lower()
                closed = closed_raw in ('true', '1', 'yes')

                open_t, close_t, crosses = parse_times(hours_type)

                # If marked not-closed but no times parsed, treat as closed
                # (these are placeholder rows in the spreadsheet)
                if not closed and open_t is None:
                    closed = True

                # Upsert into DB
                existing = system.db.runScalarQuery(
                    "SELECT COUNT(*) FROM park_calendar WHERE cal_date = '" + str(cal_date) + "'",
                    DB_NAME
                )

                if existing > 0:
                    system.db.runUpdateQuery(
                        """UPDATE park_calendar SET
                            hours_type = ?, open_time = ?, close_time = ?,
                            crosses_midnight = ?, closed = ?
                           WHERE cal_date = ?
                           AND override_open IS NULL AND override_close IS NULL""",
                        [hours_type, open_t, close_t, crosses, closed, str(cal_date)],
                        DB_NAME
                    )
                    updated += 1
                else:
                    system.db.runUpdateQuery(
                        """INSERT INTO park_calendar
                            (cal_date, hours_type, open_time, close_time, crosses_midnight, closed)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        [str(cal_date), hours_type, open_t, close_t, crosses, closed],
                        DB_NAME
                    )
                    inserted += 1

            except Exception as e:
                errors.append('Row ' + str(row_num) + ': ' + str(e))

    logger = system.util.getLogger('ParkCalendarImport')
    logger.info('Import complete. Inserted: ' + str(inserted) + ', Updated: ' + str(updated))
    if errors:
        for err in errors:
            logger.warn(err)

    system.perspective.print(
        'Import complete. Inserted: ' + str(inserted) +
        ', Updated: ' + str(updated) +
        (('\nWarnings: ' + str(len(errors))) if errors else '')
    )


run()
