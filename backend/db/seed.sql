-- Default seed data, applied once on lazy initialisation of an empty database.
-- INSERT OR IGNORE keeps this script safe to re-run.

INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at)
VALUES ('default', 10000.0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)
SELECT
    lower(
        hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
        substr(hex(randomblob(2)), 2) || '-' ||
        substr('89ab', abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)), 2) || '-' ||
        hex(randomblob(6))
    ),
    'default',
    ticker,
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
FROM (
    SELECT 'AAPL' AS ticker
    UNION ALL SELECT 'GOOGL'
    UNION ALL SELECT 'MSFT'
    UNION ALL SELECT 'AMZN'
    UNION ALL SELECT 'TSLA'
    UNION ALL SELECT 'NVDA'
    UNION ALL SELECT 'META'
    UNION ALL SELECT 'JPM'
    UNION ALL SELECT 'V'
    UNION ALL SELECT 'NFLX'
);
