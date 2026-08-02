import os
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2.extras import execute_values

def fetch_yahoo_data(yahoo_ticker, db_ticker, conn):
    print(f"--- Seeding {yahoo_ticker} ---")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    chunk_size = timedelta(days=7)
    
    chunks = []
    current_start = start_date

    while current_start < end_date:
        current_end = min(current_start + chunk_size, end_date)
        print(f"Fetching {yahoo_ticker}: {current_start.date()} to {current_end.date()}")
        
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

def fetch_binance_data(db_ticker, conn):
    print(f"--- Seeding {db_ticker} from Binance REST API ---")
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=90)).timestamp() * 1000)
    
    all_candles = []
    current_start = start_time
    
    while current_start < end_time:
        url = f"https://api.binance.com/api/v3/klines?symbol={db_ticker}&interval=1m&startTime={current_start}&limit=1000"
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"API Error: {response.text}")
            time.sleep(2)
            continue
            
        data = response.json()
        if not data:
            break
            
        for candle in data:
            # Binance returns: [open_time, open, high, low, close, volume, close_time, ...]
            dt_object = datetime.fromtimestamp(candle[0] / 1000.0, tz=timezone.utc)
            all_candles.append((
                db_ticker, 
                dt_object, 
                float(candle[1]),  # open
                float(candle[2]),  # high
                float(candle[3]),  # low
                float(candle[4]),  # close
                float(candle[5])   # volume
            ))
            
        # Move start time to the close_time of the last candle + 1ms
        current_start = data[-1][6] + 1
        print(f"Fetched {len(all_candles)} candles so far...")
        time.sleep(0.2)

    print(f"Total candles fetched for {db_ticker}: {len(all_candles)}")
    
    cur = conn.cursor()
    insert_query = """
        INSERT INTO stock_candles (ticker, datetime, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (ticker, datetime) DO NOTHING;
    """
    execute_values(cur, insert_query, all_candles)
    conn.commit()
    cur.close()
    print(f"Successfully inserted {len(all_candles)} rows for {db_ticker}.")

def run_seed():
    print("Starting database seeding process...")
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Supabase requires SSL
        if "?" not in db_url:
            db_url += "?sslmode=require"
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "db"),
            database=os.environ.get("DB_NAME", "market"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "admin"),
            port="5432"
        )

    # 1. Seed AAPL via Yahoo
    fetch_yahoo_data("AAPL", "AAPL", conn)
    
    # 2. Seed BTCUSDT via Binance
    fetch_binance_data("BTCUSDT", conn)

    conn.close()
    print("Seeding complete.")

if __name__ == "__main__":
    run_seed()