"""
Park Hours Publisher — Ignition Scheduled Script
================================================
Schedule: Daily at 5:00 AM (Gateway > Scheduling)
Script location: Project > Gateway Event Scripts > Scheduled

Reads today's park hours from park_calendar DB table.
Computes Unix epoch timestamps for open and close.
Publishes to MQTT broker via system.mqtt.publish.

Also called immediately when an operator saves a manual override
from the main view (pass force=True to skip the 5AM guard).
"""

from datetime import datetime, timedelta
import time as time_mod

# ── Configuration ────────────────────────────────────────────────────────────
DB_NAME      = "SFGR"               # Ignition DB connection name
MQTT_CLIENT  = "Ignition_Publisher" # MQTT client name configured in Ignition
MQTT_BROKER  = "Cirrus Link"        # MQTT transmission provider name in Ignition
BASE_TOPIC   = "Park/hours"
# ─────────────────────────────────────────────────────────────────────────────


def time_str_to_hhmm(t_str):
    """Parse 'HH:MM' string to (hour, minute) integers."""
    if t_str is None:
        return None, None
    parts = str(t_str).strip().split(':')
    if len(parts) != 2:
        return None, None
    return int(parts[0]), int(parts[1])


def build_epoch(base_date, hh, mm, next_day=False):
    """Build Unix epoch (seconds) from a date + hour/minute."""
    d = base_date
    if next_day:
        d = base_date + timedelta(days=1)
    dt = datetime(d.year, d.month, d.day, hh, mm, 0)
    return int(time_mod.mktime(dt.timetuple()))


def publish(topic_suffix, payload):
    system.mqtt.publish(
        MQTT_BROKER,
        MQTT_CLIENT,
        BASE_TOPIC + '/' + topic_suffix,
        str(payload),
        1,    # QoS 1
        True  # retained
    )


def run(force=False):
    logger = system.util.getLogger('ParkHoursPublisher')
    today  = datetime.now().date()

    try:
        row = system.db.runNamedQuery(
            'ParkCalendar/GetToday',
            {'cal_date': str(today)}
        )
    except Exception:
        # Fallback: direct query if named query not yet created
        ds = system.db.runQuery(
            "SELECT * FROM park_calendar WHERE cal_date = '" + str(today) + "'",
            DB_NAME
        )
        if ds.rowCount == 0:
            logger.warn('No calendar row found for ' + str(today) + ' -- publishing closed.')
            publish('date',         str(today))
            publish('closed_today', '1')
            publish('is_open',      '0')
            return
        row = {
            'open_time':        ds.getValueAt(0, 'open_time'),
            'close_time':       ds.getValueAt(0, 'close_time'),
            'crosses_midnight': ds.getValueAt(0, 'crosses_midnight'),
            'closed':           ds.getValueAt(0, 'closed'),
            'override_open':    ds.getValueAt(0, 'override_open'),
            'override_close':   ds.getValueAt(0, 'override_close'),
        }

    closed = bool(row['closed'])
    publish('date',         str(today))
    publish('closed_today', '1' if closed else '0')

    if closed:
        publish('is_open',      '0')
        publish('open_epoch',   '0')
        publish('close_epoch',  '0')
        logger.info(str(today) + ': closed day published.')
        return

    # Effective times: override takes precedence
    eff_open  = row['override_open']  if row['override_open']  else row['open_time']
    eff_close = row['override_close'] if row['override_close'] else row['close_time']
    crosses   = bool(row['crosses_midnight'])

    open_hh,  open_mm  = time_str_to_hhmm(eff_open)
    close_hh, close_mm = time_str_to_hhmm(eff_close)

    if open_hh is None or close_hh is None:
        logger.warn(str(today) + ': could not parse times. open=' + str(eff_open) + ' close=' + str(eff_close))
        return

    open_epoch  = build_epoch(today, open_hh,  open_mm,  next_day=False)
    close_epoch = build_epoch(today, close_hh, close_mm, next_day=crosses)

    now_epoch = int(time_mod.time())
    is_open   = '1' if (open_epoch <= now_epoch < close_epoch) else '0'

    publish('open_epoch',  open_epoch)
    publish('close_epoch', close_epoch)
    publish('is_open',     is_open)

    logger.info(
        str(today) + ': open=' + str(eff_open) + ' (' + str(open_epoch) + ')' +
        ' close=' + str(eff_close) + (' [+1d]' if crosses else '') +
        ' (' + str(close_epoch) + ') is_open=' + is_open
    )


run()
