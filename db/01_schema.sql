-- Create Tables
CREATE TABLE IF NOT EXISTS stock_candles (
    ticker VARCHAR(10) NOT NULL,
    datetime TIMESTAMPTZ NOT NULL,
    open NUMERIC(12, 4) NOT NULL,
    high NUMERIC(12, 4) NOT NULL,
    low NUMERIC(12, 4) NOT NULL,
    close NUMERIC(12, 4) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    PRIMARY KEY (ticker, datetime)
);

CREATE TABLE IF NOT EXISTS raw_trades (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price NUMERIC(18, 8) NOT NULL,
    quantity NUMERIC(18, 8) NOT NULL,
    trade_time TIMESTAMPTZ NOT NULL,
    is_buyer_maker BOOLEAN,
    ingestion_time TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_trades_time ON raw_trades (trade_time DESC);

-- Create Indexes
CREATE INDEX IF NOT EXISTS idx_candles_datetime ON stock_candles (datetime DESC);