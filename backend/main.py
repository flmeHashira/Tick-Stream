from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from database import engine
from pathlib import Path

app = FastAPI()

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
                "volume": int(row[5])
            })
            
    return candles