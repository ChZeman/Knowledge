"""
Park Calendar Import Script
===========================
Run from Ignition Script Console (Tools > Script Console).
Reads Calendar_1_.xlsx directly from the NAS mount using Apache POI,
which is already bundled with Ignition 8.1.x.

Run once per season, or whenever the calendar is updated on the NAS.

Requirements:
  - NAS mounted at /mnt/nas_sfgr (see NAS_MOUNT_SETUP.md)
  - park_calendar table created (see db_setup.sql)
  - Ignition 8.1.x (POI 4.1.2 is bundled — no extra install needed)
"""

import re
import os
from datetime import datetime

# Ignition 8.1 bundles Apache POI — import via Java
from org.apache.poi.xssf.usermodel import XSSFWorkbook
from java.io import FileInputStream

# ── Configuration ─────────────────────────────────────────────────────────────
DB_NAME   = "SFGR"                                    # Ignition DB connection name
XLSX_PATH = "/mnt/nas_sfgr/Calendar_1_.xlsx"         # Direct xlsx read — no CSV needed
SHEET     = "Calendar"                               # Sheet name in the workbook

# Column indices (0-based) matching Calendar_1_.xlsx
COL_DATE      = 0   # Date
COL_HOURSTYPE = 1   # Hours Type
COL_CLOSED    = 5   # Closed (boolean)
# ──────────────────────────────────────────────────────────────────────────────


def cell_str(cell):
    """Return cell value as a stripped string, or empty string if None/blank."""
    if cell is None:
        return ''
    ct = cell.getCellType().toString()
    if ct == 'STRING':
        return cell.getStringCellValue().strip()
    elif ct == 'NUMERIC':
        # Date cells are stored as numeric in xlsx
        from org.apache.poi.ss.usermodel import DateUtil
        if DateUtil.isCellDateFormatted(cell):
            dt = cell.getDateCellValue()  # java.util.Date
            return str(dt)[:10]           # "YYYY-MM-DD"
        return str(int(cell.getNumericCellValue()))
    elif ct == 'BOOLEAN':
        return str(cell.getBooleanCellValue())
    elif ct == 'FORMULA':
        # Evaluate cached result
        cached = cell.getCachedFormulaResultType().toString()
        if cached == 'STRING':
            return cell.getRichStringCellValue().getString().strip()
        elif cached == 'NUMERIC':
            from org.apache.poi.ss.usermodel import DateUtil
            if DateUtil.isCellDateFormatted(cell):
                return str(cell.getDateCellValue())[:10]
            return str(int(cell.getNumericCellValue()))
        elif cached == 'BOOLEAN':
            return str(cell.getBooleanCellValue())
    return ''


def parse_times(hours_type_str):
    """
    Extract open/close from the parenthetical in HoursType, e.g. (10:30AM - 8:00PM).
    Returns (open_str, close_str, crosses_midnight) as 'HH:MM' 24h, or (None, None, False).
    """
    s = str(hours_type_str).strip()
    m = re.search(
        r'\((\d{1,2}:\d{2}\s*[AP]M)\s*[-\u2013]\s*(\d{1,2}:\d{2}\s*[AP]M)\)',
        s, re.IGNORECASE
    )
    if not m:
        return None, None, False

    def to_24h(t):
        t = t.strip().upper().replace(' ', '')
        try:
            return datetime.strptime(t, '%I:%M%p').strftime('%H:%M')
        except ValueError:
            return None

    open_24  = to_24h(m.group(1))
    close_24 = to_24h(m.group(2))
    if open_24 is None or close_24 is None:
        return None, None, False

    # Overnight: close <= open numerically, or close is exactly midnight
    crosses = (close_24 <= open_24) if close_24 != '00:00' else True
    return open_24, close_24, crosses


def run():
    logger = system.util.getLogger('ParkCalendarImport')

    if not os.path.exists(XLSX_PATH):
        logger.error('File not found: ' + XLSX_PATH)
        system.perspective.print('ERROR: File not found: ' + XLSX_PATH)
        return

    inserted = 0
    updated  = 0
    skipped  = 0
    errors   = []

    fis = FileInputStream(XLSX_PATH)
    try:
        wb = XSSFWorkbook(fis)
    finally:
        fis.close()

    sheet = wb.getSheet(SHEET)
    if sheet is None:
        logger.error('Sheet "' + SHEET + '" not found in workbook.')
        system.perspective.print('ERROR: Sheet "' + SHEET + '" not found.')
        wb.close()
        return

    row_iter = sheet.rowIterator()
    header_skipped = False

    while row_iter.hasNext():
        row = row_iter.next()
        row_num = row.getRowNum() + 1  # 1-based for logging

        if not header_skipped:
            header_skipped = True
            continue  # skip header row

        try:
            date_raw   = cell_str(row.getCell(COL_DATE))
            hours_type = cell_str(row.getCell(COL_HOURSTYPE))
            closed_raw = cell_str(row.getCell(COL_CLOSED)).lower()

            if not date_raw:
                skipped += 1
                continue

            # Normalise date string — may be "YYYY-MM-DD" or Java Date string
            date_str = date_raw.split(' ')[0]  # take YYYY-MM-DD portion
            try:
                cal_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Row ' + str(row_num) + ': bad date "' + date_raw + '"')
                continue

            closed = closed_raw in ('true', '1', 'yes')
            open_t, close_t, crosses = parse_times(hours_type)

            # Rows marked not-closed but with no parseable times are placeholders
            if not closed and open_t is None:
                closed = True

            existing = system.db.runScalarQuery(
                "SELECT COUNT(*) FROM park_calendar WHERE cal_date = '" + str(cal_date) + "'",
                DB_NAME
            )

            if existing > 0:
                # Only update non-overridden rows so operator overrides are preserved
                system.db.runUpdateQuery(
                    """UPDATE park_calendar
                       SET hours_type = ?, open_time = ?, close_time = ?,
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

    wb.close()

    summary = ('Import complete. Inserted: ' + str(inserted) +
               ', Updated: ' + str(updated) +
               ', Skipped: ' + str(skipped) +
               (', Warnings: ' + str(len(errors)) if errors else ''))
    logger.info(summary)
    for err in errors:
        logger.warn(err)

    system.perspective.print(summary)


run()
