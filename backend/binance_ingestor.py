import psycopg2
from psycopg2.extras import execute_values
import websocket
import json
import os
import datetime

trades = []

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "db"),
    database=os.environ.get("DB_NAME", "market"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "admin"),
    port="5432"
)
cur = conn.cursor()

insert_query = """
    INSERT INTO raw_trades (symbol, price, quantity, trade_time, is_buyer_maker)
    VALUES %s
"""

def on_open(ws):
    print("Connected to Binance WS")

def on_message(ws, message):
    msg = json.loads(message)
    
    symbol = "BTCUSDT"
    price = float(msg["p"])
    qty = float(msg["q"])
    time = datetime.datetime.utcfromtimestamp(msg['T'] / 1000.0)
    m = msg['m']
    
    trades.append((symbol, price, qty, time, m))
    
    if len(trades) >= 100:
        execute_values(cur, insert_query, trades)
        conn.commit()
        print(f"Inserted 100 trades. Current buffer cleared.")
        trades.clear()

def on_error(ws, error):
    print("Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("Disconnected", close_status_code, close_msg)

ws = websocket.WebSocketApp(
    "wss://stream.binance.com:9443/ws/btcusdt@trade",
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
)

ws.run_forever()