import os
import websockets
import asyncio
import json
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import execute_values
from database import engine
from sqlalchemy import text
from pathlib import Path
from seed import run_seed

app = FastAPI()

allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients = set()
tick_buffer = []
ROLLUP_SQL = Path("analytics.sql").read_text()


def flush_buffer_to_db(buffer_data):
    # Use the SQLAlchemy engine to get a pooled connection
    with engine.connect() as conn:
        # Get the underlying raw psycopg2 connection for execute_values
        raw_conn = conn.connection
        cursor = raw_conn.cursor()
        
        insert_query = """
            INSERT INTO raw_trades (symbol, price, quantity, trade_time, is_buyer_maker)
            VALUES %s
        """
        execute_values(cursor, insert_query, buffer_data)
        raw_conn.commit()



def execute_rollup_and_purge(start_time, end_time):
    with engine.connect() as conn:
        # 1. Execute the aggregation query for the previous minute
        result = conn.execute(text(ROLLUP_SQL), {
            "start_time": start_time,
            "end_time": end_time
        })
        candle = result.fetchone()

        # 2. If we got a candle, upsert it into stock_candles
        if candle:
            upsert_query = text("""
                INSERT INTO stock_candles (ticker, datetime, open, high, low, close, volume)
                VALUES ('BTCUSDT', :datetime, :open, :high, :low, :close, :volume)
                ON CONFLICT (ticker, datetime) DO UPDATE SET 
                    open = EXCLUDED.open, 
                    high = EXCLUDED.high, 
                    low = EXCLUDED.low, 
                    close = EXCLUDED.close, 
                    volume = EXCLUDED.volume;
            """)
            
            conn.execute(upsert_query, {
                "datetime": candle[0],
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5]
            })
        
        # 3. Purge old raw ticks
        conn.execute(text("DELETE FROM raw_trades WHERE trade_time < NOW() - INTERVAL '1 hour';"))
        
        # 4. Commit the transaction
        conn.commit()



async def rollup_and_purge():
    while True:
        await asyncio.sleep(60)
        now = datetime.datetime.now(datetime.timezone.utc)
        current_minute = now.replace(second=0, microsecond=0)
        start_time = current_minute - datetime.timedelta(minutes=1)
        await asyncio.to_thread(execute_rollup_and_purge, start_time, current_minute)

# WebSocket Endpoint
@app.websocket("/ws/{asset}")
async def websocket_endpoint(websocket: WebSocket, asset: str):
    if asset != "BTC":
        await websocket.close(code=1008)
        return

    await websocket.accept()
    connected_clients.add(websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

# The Upstream Task
async def upstream_listener():
    while True:
        if len(connected_clients) == 0:
            await asyncio.sleep(1)
            continue
        try:
            async with websockets.connect('wss://stream.binance.com:9443/ws/btcusdt@trade') as ws:
                async for message in ws:
                    msg = json.loads(message)
                    price = float(msg['p'])
                    time_ms = msg['T']
                    quantity = float(msg["q"])
                    is_maker = msg['m']
                    dt_object = datetime.datetime.fromtimestamp(time_ms / 1000.0, tz=datetime.timezone.utc)
                    
                    for client in connected_clients:
                        try:
                            await client.send_json({
                                "time": time_ms, 
                                "price": price,
                                "quantity": quantity,
                                "is_buyer_maker": is_maker
                            })
                        except Exception:
                            pass
                            
                    # Buffer for the database
                    tick_tuple = ("BTCUSDT", price, quantity, dt_object, is_maker)
                    tick_buffer.append(tick_tuple)
                    
                    if len(tick_buffer) >= 100:
                        # Copy the buffer and clear it immediately so the loop can keep receiving ticks
                        buffer_to_flush = list(tick_buffer)
                        tick_buffer.clear()
                        
                        # Offload the blocking DB write to a thread
                        asyncio.create_task(asyncio.to_thread(flush_buffer_to_db, buffer_to_flush))

        except (websockets.ConnectionClosed, OSError) as e:
            print(f"Disconnected ({e})")
            await asyncio.sleep(5)



@app.get("/api/v1/candles")
def get_candles(asset: str, interval: str = "1m"):
    # Map the frontend interval to Postgres DATE_TRUNC syntax
    db_interval = {
        "1m": "minute",
        "30m": "hour", # We will use 30 min logic below
        "1d": "day",
        "7d": "week"
    }.get(interval, "minute")

    if asset == "AAPL" or asset == "BTCUSDT":
        if interval == "1m":
            # Just fetch the raw 1m candles directly
            query = text("""
                SELECT datetime, open, high, low, close, volume 
                FROM stock_candles 
                WHERE ticker = :ticker
                ORDER BY datetime ASC
            """)
        else:
            # Rollup logic for 30m, 1d, 7d
            if interval == "30m":
                # Custom math to bucket into 30-minute intervals
                query = text("""
                    SELECT 
                        to_timestamp(floor((extract('epoch' from datetime) / 1800 )) * 1800) AT TIME ZONE 'UTC' AS bucket_time,
                        (ARRAY_AGG(open ORDER BY datetime ASC))[1] AS open,
                        MAX(high) AS high,
                        MIN(low) AS low,
                        (ARRAY_AGG(close ORDER BY datetime DESC))[1] AS close,
                        SUM(volume) AS volume
                    FROM stock_candles
                    WHERE ticker = :ticker
                    GROUP BY 1
                    ORDER BY bucket_time ASC
                """)
            else:
                # 1d, 7d
                trunc_val = "day" if interval == "1d" else "week"
                query = text(f"""
                    SELECT 
                        DATE_TRUNC('{trunc_val}', datetime) AS bucket_time,
                        (ARRAY_AGG(open ORDER BY datetime ASC))[1] AS open,
                        MAX(high) AS high,
                        MIN(low) AS low,
                        (ARRAY_AGG(close ORDER BY datetime DESC))[1] AS close,
                        SUM(volume) AS volume
                    FROM stock_candles
                    WHERE ticker = :ticker
                    GROUP BY 1
                    ORDER BY bucket_time ASC
                """)
    else:
        raise HTTPException(status_code=400, detail="Invalid asset. Use AAPL or BTCUSDT.")

    with engine.connect() as conn:
        result = conn.execute(query, {"ticker": asset})
        rows = result.fetchall()
        
        candles = []
        for row in rows:
            candles.append({
                "time": row[0].isoformat(),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })
            
    return candles



# FastAPI Startup Hook
@app.on_event("startup")
async def startup_event():
    # 1. Idempotent Seed Check
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM stock_candles;"))
        count = result.scalar()
    
    if count == 0:
        print("Database is empty. Running seeder in background thread...")
        asyncio.create_task(asyncio.to_thread(run_seed))
    else:
        print(f"Database already has {count} candles. Skipping seed.")

    # 2. Start background tasks
    asyncio.create_task(upstream_listener())
    asyncio.create_task(rollup_and_purge())