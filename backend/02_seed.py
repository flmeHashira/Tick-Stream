import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values

def fetch_and_seed(yahoo_ticker, db_ticker, conn):
    print(f"--- Seeding {yahoo_ticker} ---")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    chunk_size = timedelta(days=7)
    
    chunks = []
    current_start = start_date

    while current_start < end_date:
        current_end = min(current_start + chunk_size, end_date)
        print(f"Fetching {yahoo_ticker}: {current_start.date()} to {current_end.date()}")
        
        # USE yahoo_ticker HERE
        df = yf.download(yahoo_ticker, start=current_start, end=current_end, interval="1m")
        
        if not df.empty:
            chunks.append(df)
        
        current_start = current_end

    if not chunks:
        print(f"No data fetched for {yahoo_ticker}.")
        return

    final_df = pd.concat(chunks)
    print(f"Total rows fetched for {yahoo_ticker}: {len(final_df)}")

    if 'Adj Close' in final_df.columns:
        final_df = final_df.drop(columns=['Adj Close'])

    if isinstance(final_df.columns, pd.MultiIndex):
        final_df.columns = final_df.columns.get_level_values(0)

    final_df.reset_index(inplace=True)
    final_df.rename(columns={'Datetime': 'datetime', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)

    if final_df['datetime'].dt.tz is not None:
        final_df['datetime'] = final_df['datetime'].dt.tz_convert('UTC').dt.tz_localize(None)

    # USE db_ticker HERE
    data_tuples = [
        (db_ticker, row.datetime, row.open, row.high, row.low, row.close, row.volume)
        for row in final_df.itertuples(index=False)
    ]

    cur = conn.cursor()
    insert_query = """
        INSERT INTO stock_candles (ticker, datetime, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (ticker, datetime) DO NOTHING;
    """
    
    execute_values(cur, insert_query, data_tuples)
    conn.commit()
    cur.close()
    print(f"Successfully inserted {len(data_tuples)} rows for {db_ticker}.")

if __name__ == "__main__":
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        database=os.environ.get("DB_NAME", "market"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "admin"),
        port="5432"
    )

    # Dictionary mapping: Yahoo Finance Symbol -> Database Symbol
    tickers_to_seed = {
        "AAPL": "AAPL",
        "BTC-USD": "BTCUSDT"
    }
    
    for yahoo_ticker, db_ticker in tickers_to_seed.items():
        print(f"Fetching {yahoo_ticker} -> Storing as {db_ticker}")
        fetch_and_seed(yahoo_ticker, db_ticker, conn)

    conn.close()
    print("Seeding complete.")