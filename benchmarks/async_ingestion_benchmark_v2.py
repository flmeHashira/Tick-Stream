import asyncio
import time
import psycopg2
from psycopg2.extras import execute_values
import os
import statistics
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = "market"
DB_USER = "postgres"
DB_PASSWORD = "admin"

buffer = []
received_count = 0
persisted_count = 0
loop_lags = []
flush_tasks = []

def flush_buffer(data):
    global persisted_count
    if not data: return
    # Give each thread its own connection to avoid concurrent transaction aborts
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port="5432")
    cur = conn.cursor()
    query = "INSERT INTO raw_trades (symbol, price, quantity, trade_time, is_buyer_maker) VALUES %s"
    execute_values(cur, query, data)
    conn.commit()
    cur.close()
    conn.close()
    persisted_count += len(data)

async def producer(rate_per_sec, duration_sec):
    """Simulates Binance WebSocket pushing ticks at a specific rate, compensating for drift."""
    global received_count
    interval = 1.0 / rate_per_sec
    end_time = time.perf_counter() + duration_sec
    next_tick_time = time.perf_counter()
    
    while time.perf_counter() < end_time:
        # Use datetime object for timestamp
        buffer.append(("BENCHUSDT", 65000.0, 0.001, datetime.utcnow(), False))
        received_count += 1
        
        if len(buffer) >= 100:
            data_to_flush = list(buffer)
            buffer.clear()
            task = asyncio.create_task(asyncio.to_thread(flush_buffer, data_to_flush))
            flush_tasks.append(task)
            
        # Drift-compensating sleep
        next_tick_time += interval
        sleep_time = max(0, next_tick_time - time.perf_counter())
        await asyncio.sleep(sleep_time)

async def event_loop_monitor():
    """Measures event loop lag."""
    while True:
        t_start = time.perf_counter()
        await asyncio.sleep(0.01)
        lag = (time.perf_counter() - t_start) - 0.01
        loop_lags.append(lag * 1000)

async def main():
    global buffer, received_count, persisted_count, loop_lags, flush_tasks
    
    print("--- Async Ingestion & Event-Loop Benchmark V2 ---")
    print(f"{'Target (msg/s)':<14} | {'Received':<10} | {'Persisted':<10} | {'Loss':<8} | {'P50 Lag (ms)':<12} | {'P95 Lag (ms)':<12}")
    print("-" * 85)
    
    for rate in [100, 500, 1000]:
        # Reset state
        buffer = []
        received_count = 0
        persisted_count = 0
        loop_lags = []
        flush_tasks = []
        
        # Clean DB using a temporary connection
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port="5432")
        cur = conn.cursor()
        cur.execute("DELETE FROM raw_trades WHERE symbol = 'BENCHUSDT';")
        conn.commit()
        cur.close()
        conn.close()
        
        monitor_task = asyncio.create_task(event_loop_monitor())
        
        # Run producer
        await producer(rate, 5)
        
        # Explicitly drain all pending flush tasks
        if flush_tasks:
            await asyncio.gather(*flush_tasks, return_exceptions=True)
            
        monitor_task.cancel()
        
        loss = received_count - persisted_count
        p50 = statistics.median(loop_lags) if loop_lags else 0
        p95 = statistics.quantiles(loop_lags, n=100)[95] if loop_lags else 0
        
        print(f"{rate:<14} | {received_count:<10} | {persisted_count:<10} | {loss:<8} | {p50:<12.2f} | {p95:<12.2f}")

if __name__ == "__main__":
    asyncio.run(main())