import os
import time
import psycopg2
from psycopg2.extras import execute_values
import random
from datetime import datetime, timedelta
import statistics

DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = "market"
DB_USER = "postgres"
DB_PASSWORD = "admin"

def generate_ticks(n):
    ticks = []
    base_time = datetime.utcnow()
    for i in range(n):
        # Unique timestamps (ms precision)
        trade_time = base_time + timedelta(milliseconds=i)
        ticks.append((
            "BENCHUSDT", 
            65000.0 + random.uniform(-100, 100), 
            random.uniform(0.001, 1.0), 
            trade_time, 
            random.choice([True, False])
        ))
    return ticks

def run_benchmark(batch_size, total_ticks):
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port="5432")
    cur = conn.cursor()
    insert_query = "INSERT INTO raw_trades (symbol, price, quantity, trade_time, is_buyer_maker) VALUES %s"
    
    ticks = generate_ticks(total_ticks)
    
    batch_latencies = []
    start_time = time.perf_counter()
    
    if batch_size == 1:
        for tick in ticks:
            t_start = time.perf_counter()
            cur.execute(insert_query, (tick,))
            batch_latencies.append(time.perf_counter() - t_start)
    else:
        for i in range(0, total_ticks, batch_size):
            batch = ticks[i:i + batch_size]
            t_start = time.perf_counter()
            execute_values(cur, insert_query, batch)
            batch_latencies.append(time.perf_counter() - t_start)
            
    conn.commit()
    end_time = time.perf_counter()
    
    duration = end_time - start_time
    throughput = total_ticks / duration
    
    cur.execute("DELETE FROM raw_trades WHERE symbol = 'BENCHUSDT';")
    conn.commit()
    cur.close()
    conn.close()
    
    return duration, throughput, statistics.mean(batch_latencies), statistics.quantiles(batch_latencies, n=100)[95]

if __name__ == "__main__":
    TOTAL_TICKS = 10000
    ITERATIONS = 5
    
    print(f"--- Batch Benchmark V2 ({TOTAL_TICKS} ticks, {ITERATIONS} iterations) ---")
    print(f"{'Batch':<6} | {'Mean Dur (s)':<12} | {'Mean Thr (t/s)':<14} | {'Mean Batch Lat (ms)':<20} | {'P95 Batch Lat (ms)'}")
    print("-" * 80)
    
    for b_size in [1, 10, 100, 500]:
        durations = []
        throughputs = []
        mean_lats = []
        p95_lats = []
        
        for _ in range(ITERATIONS):
            dur, thr, m_lat, p95_lat = run_benchmark(b_size, TOTAL_TICKS)
            durations.append(dur)
            throughputs.append(thr)
            mean_lats.append(m_lat * 1000)
            p95_lats.append(p95_lat * 1000)
            
        print(f"{b_size:<6} | {statistics.mean(durations):<12.4f} | {statistics.mean(throughputs):<14.2f} | {statistics.mean(mean_lats):<20.4f} | {statistics.mean(p95_lats):.4f}")