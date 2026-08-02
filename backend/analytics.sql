SELECT 
    minute,
    MAX(open_price) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    MAX(close_price) AS close,
    SUM(quantity) AS volume
FROM (
    SELECT 
        DATE_TRUNC('minute', trade_time) AS minute,
        price,
        quantity,
        FIRST_VALUE(price) OVER (
            PARTITION BY DATE_TRUNC('minute', trade_time) 
            ORDER BY trade_time ASC
        ) AS open_price,
        LAST_VALUE(price) OVER (
            PARTITION BY DATE_TRUNC('minute', trade_time) 
            ORDER BY trade_time ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS close_price
    FROM raw_trades
    WHERE trade_time >= :start_time AND trade_time < :end_time
) AS subquery
GROUP BY minute
ORDER BY minute DESC;