"""
Park Hours Daily Script — Ignition Scheduled Script
===================================================
Schedule: Daily at 5:00 AM (Gateway > Config > Scheduling)

What this script does each morning:
  1. Reads today's row from Park Hours.xlsx on the NAS
  2. Upserts it into the park_calendar DB table
     (skips update if operator overrides are active)
  3. Publishes open/close epochs and is_open flag to MQTT

Can also be called on demand when an operator saves a manual
override from the main view: call run(force=True).

No separate import step required — just keep Park Hours.xlsx
current on the NAS and this script handles the rest.
"""

import re
import os
from datetime import datetime, timedelta
import time as time_mod

# Ignition 8.1 bundles Apache POI — used to read xlsx directly
from org.apache.poi.xssf.usermodel import XSSFWorkbook
from org.apache.poi.ss.usermodel import DateUtil
from java.io import FileInputStream

# ── Configuration ────────────────────────────────────────────────────────────
DB_NAME      = "IgnitionPostgreSQL"
XLSX_PATH    = "/mnt/nas_sfgr/Building Monitoring and Control/Park Hours/Park Hours.xlsx"
SHEET        = "Calendar"
MQTT_CLIENT  = "Ignition_Publisher"
MQTT_BROKER  = "Cirrus Link"
BASE_TOPIC   = "Park/hours"
COL_DATE     = 0
COL_HOURS    = 1
COL_CLOSED   = 5
# ─────────────────────────────────────────────────────────────────────────────


def cell_str(cell):
    if cell is None:
        return ''
    ct = cell.getCellType().toString()
    if ct == 'STRING':
        return cell.getStringCellValue().strip()
    elif ct == 'NUMERIC':
        if DateUtil.isCellDateFormatted(cell):
            return str(cell.getDateCellValue())[:10]
        return str(int(cell.getNumericCellValue()))
    elif ct == 'BOOLEAN':
        return str(cell.getBooleanCellValue())
    elif ct == 'FORMULA':
        cached = cell.getCachedFormulaResultType().toString()
        if cached == 'STRING':
            return cell.getRichStringCellValue().getString().strip()
        elif cached == 'NUMERIC':
            if DateUtil.isCellDateFormatted(cell):
                return str(cell.getDateCellValue())[:10]
            return str(int(cell.getNumericCellValue()))
        elif cached == 'BOOLEAN':
            return str(cell.getBooleanCellValue())
    return ''


def parse_times(s):
    """
    Parse open/close from parenthetical, e.g. (10:30AM - 8:00PM).
    Returns (open_hhmm, close_hhmm, crosses_midnight) or (None, None, False).
    """
    m = re.search(
        r'\((\d{1,2}:\d{2}\s*[AP]M)\s*[-\u2013]\s*(\d{1,2}:\d{2}\s*[AP]M)\)',
        str(s), re.IGNORECASE
    )
    if not m:
        return None, None, False
    def to_24h(t):
        t = t.strip().upper().replace(' ', '')
        try:
            return datetime.strptime(t, '%I:%M%p').strftime('%H:%M')
        except ValueError:
            return None
    o = to_24h(m.group(1))
    c = to_24h(m.group(2))
    if not o or not c:
        return None, None, False
    crosses = (c <= o) if c != '00:00' else True
    return o, c, crosses


def read_today_from_xlsx(today_str):
    """
    Scan Park Hours.xlsx for today's row.
    Returns (hours_type, open_t, close_t, crosses, closed) or None if not found.
    """
    if not os.path.exists(XLSX_PATH):
        return None

    fis = FileInputStream(XLSX_PATH)
    try:
        wb = XSSFWorkbook(fis)
    finally:
        fis.close()

    sheet = wb.getSheet(SHEET)
    if sheet is None:
        wb.close()
        return None

    result = None
    row_iter = sheet.rowIterator()
    header_skipped = False

    while row_iter.hasNext():
        row = row_iter.next()
        if not header_skipped:
            header_skipped = True
            continue
        date_raw = cell_str(row.getCell(COL_DATE))
        if not date_raw:
            continue
        row_date = date_raw.split(' ')[0]  # normalise to YYYY-MM-DD
        if row_date == today_str:
            hours_type = cell_str(row.getCell(COL_HOURS))
            closed_raw = cell_str(row.getCell(COL_CLOSED)).lower()
            closed     = closed_raw in ('true', '1', 'yes')
            open_t, close_t, crosses = parse_times(hours_type)
            if not closed and open_t is None:
                closed = True
            result = (hours_type, open_t, close_t, crosses, closed)
            break

    wb.close()
    return result


def upsert_today(today_str, hours_type, open_t, close_t, crosses, closed):
    """
    Write today's row to park_calendar.
    Preserves existing operator overrides.
    """
    existing = system.db.runScalarQuery(
        "SELECT COUNT(*) FROM park_calendar WHERE cal_date = '" + today_str + "'",
        DB_NAME
    )
    if existing > 0:
        system.db.runUpdateQuery(
            """UPDATE park_calendar
               SET hours_type=?, open_time=?, close_time=?, crosses_midnight=?, closed=?
               WHERE cal_date=?
                 AND override_open IS NULL AND override_close IS NULL""",
            [hours_type, open_t, close_t, crosses, closed, today_str],
            DB_NAME
        )
    else:
        system.db.runUpdateQuery(
            """INSERT INTO park_calendar
                   (cal_date, hours_type, open_time, close_time, crosses_midnight, closed)
               VALUES (?,?,?,?,?,?)""",
            [today_str, hours_type, open_t, close_t, crosses, closed],
            DB_NAME
        )


def publish(suffix, payload):
    system.mqtt.publish(MQTT_BROKER, MQTT_CLIENT,
                        BASE_TOPIC + '/' + suffix, str(payload), 1, True)


def publish_closed(today_str):
    publish('date',         today_str)
    publish('closed_today', '1')
    publish('is_open',      '0')
    publish('open_epoch',   '0')
    publish('close_epoch',  '0')


def run(force=False):
    logger    = system.util.getLogger('ParkHoursPublisher')
    today     = datetime.now().date()
    today_str = str(today)

    # ── Step 1: read today from xlsx and upsert DB ────────────────────────
    nas_available = os.path.exists(XLSX_PATH)
    if nas_available:
        row = read_today_from_xlsx(today_str)
        if row:
            upsert_today(today_str, *row)
            logger.info('NAS read OK — upserted ' + today_str)
        else:
            logger.warn('No row found in xlsx for ' + today_str)
    else:
        logger.warn('NAS unavailable — using existing DB row for ' + today_str)

    # ── Step 2: read effective values from DB and publish ────────────────
    ds = system.db.runQuery(
        "SELECT * FROM park_calendar WHERE cal_date = '" + today_str + "'",
        DB_NAME
    )
    if ds.rowCount == 0:
        logger.warn('No DB row for ' + today_str + ' — publishing closed.')
        publish_closed(today_str)
        return

    closed         = bool(ds.getValueAt(0, 'closed'))
    open_time      = ds.getValueAt(0, 'open_time')
    close_time     = ds.getValueAt(0, 'close_time')
    crosses        = bool(ds.getValueAt(0, 'crosses_midnight'))
    override_open  = ds.getValueAt(0, 'override_open')
    override_close = ds.getValueAt(0, 'override_close')

    publish('date',         today_str)
    publish('closed_today', '1' if closed else '0')

    if closed:
        publish('is_open',    '0')
        publish('open_epoch', '0')
        publish('close_epoch','0')
        logger.info(today_str + ': closed.')
        return

    eff_open  = override_open  if override_open  else open_time
    eff_close = override_close if override_close else close_time

    def hhmm(t):
        if t is None: return None, None
        p = str(t).strip().split(':')
        return (int(p[0]), int(p[1])) if len(p) == 2 else (None, None)

    open_hh,  open_mm  = hhmm(eff_open)
    close_hh, close_mm = hhmm(eff_close)

    if open_hh is None or close_hh is None:
        logger.warn(today_str + ': unparseable times — open=' + str(eff_open) + ' close=' + str(eff_close))
        return

    def build_epoch(hh, mm, next_day=False):
        d = today + timedelta(days=1) if next_day else today
        return int(time_mod.mktime(datetime(d.year, d.month, d.day, hh, mm).timetuple()))

    open_epoch  = build_epoch(open_hh,  open_mm)
    close_epoch = build_epoch(close_hh, close_mm, next_day=crosses)
    now_epoch   = int(time_mod.time())
    is_open     = '1' if open_epoch <= now_epoch < close_epoch else '0'

    publish('open_epoch',  open_epoch)
    publish('close_epoch', close_epoch)
    publish('is_open',     is_open)

    logger.info(
        today_str + ': open=' + str(eff_open) + ' (' + str(open_epoch) + ')'
        + ' close=' + str(eff_close) + (' [+1d]' if crosses else '')
        + ' (' + str(close_epoch) + ') is_open=' + is_open
        + (' [NAS unavailable]' if not nas_available else '')
    )


run()
