-- Park Calendar DB Setup
-- Run once in Ignition Designer: Tools > Script Console, or via system.db.runUpdateQuery
-- Database connection name: SFGR (update if different)

CREATE TABLE IF NOT EXISTS park_calendar (
    cal_date         DATE        NOT NULL PRIMARY KEY,
    hours_type       VARCHAR(150),              -- raw string from spreadsheet, for reference
    open_time        VARCHAR(5),                -- "HH:MM" 24h, NULL if closed
    close_time       VARCHAR(5),                -- "HH:MM" 24h, NULL if closed
    crosses_midnight BOOLEAN     DEFAULT FALSE, -- true when close time is next calendar day
    closed           BOOLEAN     DEFAULT TRUE,
    override_open    VARCHAR(5)  DEFAULT NULL,  -- operator override "HH:MM", NULL = use open_time
    override_close   VARCHAR(5)  DEFAULT NULL,  -- operator override "HH:MM", NULL = use close_time
    override_by      VARCHAR(50) DEFAULT NULL,
    override_at      DATETIME    DEFAULT NULL
);

-- Verify
SELECT COUNT(*) AS row_count FROM park_calendar;
