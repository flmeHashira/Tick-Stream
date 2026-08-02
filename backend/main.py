import websockets
import asyncio
import json
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from psycopg2.extras import execute_values
from database import engine

app = FastAPI()

connected_clients = set()
tick_buffer = []


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
                            await client.send_json({"time": time_ms, "price": price})
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



# FastAPI Startup Hook
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(upstream_listener())