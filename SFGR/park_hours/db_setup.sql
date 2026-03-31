-- Park Calendar DB Setup
-- Run once in Ignition Script Console (Tools > Script Console)
-- using system.db.runUpdateQuery as shown below.
--
-- DB connection name: IgnitionPostgreSQL
-- Note: DATETIME is not a PostgreSQL type -- use TIMESTAMP instead.

-- Paste this into Script Console and run:
--
-- system.db.runUpdateQuery("""
-- CREATE TABLE IF NOT EXISTS park_calendar (
--     cal_date         DATE         NOT NULL PRIMARY KEY,
--     hours_type       VARCHAR(150),
--     open_time        VARCHAR(5),
--     close_time       VARCHAR(5),
--     crosses_midnight BOOLEAN      DEFAULT FALSE,
--     closed           BOOLEAN      DEFAULT TRUE,
--     override_open    VARCHAR(5)   DEFAULT NULL,
--     override_close   VARCHAR(5)   DEFAULT NULL,
--     override_by      VARCHAR(50)  DEFAULT NULL,
--     override_at      TIMESTAMP    DEFAULT NULL
-- )
-- """, "IgnitionPostgreSQL")

CREATE TABLE IF NOT EXISTS park_calendar (
    cal_date         DATE         NOT NULL PRIMARY KEY,
    hours_type       VARCHAR(150),              -- raw string from spreadsheet
    open_time        VARCHAR(5),                -- "HH:MM" 24h, NULL if closed
    close_time       VARCHAR(5),                -- "HH:MM" 24h, NULL if closed
    crosses_midnight BOOLEAN      DEFAULT FALSE, -- true when close time is next calendar day
    closed           BOOLEAN      DEFAULT TRUE,
    override_open    VARCHAR(5)   DEFAULT NULL,  -- operator override, NULL = use open_time
    override_close   VARCHAR(5)   DEFAULT NULL,  -- operator override, NULL = use close_time
    override_by      VARCHAR(50)  DEFAULT NULL,
    override_at      TIMESTAMP    DEFAULT NULL
);
