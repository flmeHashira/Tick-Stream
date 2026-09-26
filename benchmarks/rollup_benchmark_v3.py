import os
import time
import psycopg2
from psycopg2.extras import execute_values
import random
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = "market"
DB_USER = "postgres"
DB_PASSWORD = "admin"

def seed_raw_ticks(n):
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port="5432")
    cur = conn.cursor()
    print(f"Seeding {n} raw ticks...")
    cur.execute("DELETE FROM raw_trades WHERE symbol = 'BENCHUSDT';")
    cur.execute("DELETE FROM stock_candles WHERE ticker = 'BENCHUSDT';")
    
    base_time = datetime.utcnow() - timedelta(hours=1)
    ticks = []
    for i in range(n):
        trade_time = base_time + timedelta(seconds=random.uniform(0, 3600))
        ticks.append(("BENCHUSDT", 65000.0 + random.uniform(-100, 100), random.uniform(0.001, 1.0), trade_time, random.choice([True, False])))
        
    for i in range(0, len(ticks), 1000):
        execute_values(cur, "INSERT INTO raw_trades (symbol, price, quantity, trade_time, is_buyer_maker) VALUES %s", ticks[i:i+1000])
        
    conn.commit()
    cur.close()
    conn.close()

def run_e2e_rollup():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port="5432")
    cur = conn.cursor()
    
    agg_query = """
        SELECT 
            minute, MAX(open_price), MAX(price), MIN(price), MAX(close_price), SUM(quantity)
        FROM (
            SELECT DATE_TRUNC('minute', trade_time) AS minute, price, quantity,
                FIRST_VALUE(price) OVER (PARTITION BY DATE_TRUNC('minute', trade_time) ORDER BY trade_time ASC) AS open_price,
                LAST_VALUE(price) OVER (PARTITION BY DATE_TRUNC('minute', trade_time) ORDER BY trade_time ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close_price
            FROM raw_trades WHERE symbol = 'BENCHUSDT'
        ) AS subquery GROUP BY minute;
    """
    
    t_agg_start = time.perf_counter()
    cur.execute(agg_query)
    rows = cur.fetchall()
    t_agg_end = time.perf_counter()
    agg_duration = t_agg_end - t_agg_start
    
    # FIX: Prepend the ticker string to each row tuple for the upsert
    upsert_data = [('BENCHUSDT', row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]
    
    upsert_query = """
        INSERT INTO stock_candles (ticker, datetime, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (ticker, datetime) DO UPDATE SET 
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, 
            close = EXCLUDED.close, volume = EXCLUDED.volume;
    """
    
    t_upsert_start = time.perf_counter()
    execute_values(cur, upsert_query, upsert_data)
    conn.commit()
    t_upsert_end = time.perf_counter()
    upsert_duration = t_upsert_end - t_upsert_start
    
    cur.close()
    conn.close()
    
    return agg_duration, upsert_duration, len(rows)

if __name__ == "__main__":
    print("--- End-to-End Rollup Benchmark ---")
    print(f"{'Ticks':<10} | {'Agg Time (ms)':<14} | {'Upsert Time (ms)':<18} | {'Total Time (ms)'}")
    print("-" * 60)
    
    for tick_count in [10000, 100000, 1000000]:
        seed_raw_ticks(tick_count)
        agg_t, ups_t, candles = run_e2e_rollup()
        print(f"{tick_count:<10} | {agg_t*1000:<14.2f} | {ups_t*1000:<18.2f} | {(agg_t+ups_t)*1000:.2f}")