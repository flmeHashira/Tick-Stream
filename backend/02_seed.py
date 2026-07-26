import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Set end date to today, start date to 3 months ago
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

# Fetch in 7-day chunks to bypass Yahoo's limit
chunk_size = timedelta(days=7)
chunks = []
current_start = start_date

while current_start < end_date:
    current_end = min(current_start + chunk_size, end_date)
    print(f"Fetching {current_start.date()} to {current_end.date()}")
    
    # Fetch data for this chunk
    df = yf.download("AAPL", start=current_start, end=current_end, interval="1m")
    
    if not df.empty:
        chunks.append(df)
    
    current_start = current_end

# Combine all chunks
if chunks:
    final_df = pd.concat(chunks)
    print(f"Total rows fetched: {len(final_df)}")

    # Drop 'Adj Close' (our schema doesn't have it)
    if ('Adj Close', 'AAPL') in final_df.columns:
        final_df = final_df.drop(columns=[('Adj Close', 'AAPL')])

    # Flatten the MultiIndex by taking just the first level (the string name)
    final_df.columns = final_df.columns.get_level_values(0)
    
    # Convert the index into a standard column named 'Datetime'
    final_df.reset_index(inplace=True)
    final_df.rename(columns={'Datetime': 'datetime', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)

    # Apply the timezone fix we discussed earlier
    final_df['datetime'] = final_df['datetime'].dt.tz_convert('UTC').dt.tz_localize(None)
    
    # Convert the DataFrame into a list of tuples
    # We manually construct the tuple to add the 'ticker' string at the beginning
    data_tuples = [
        ('AAPL', row.datetime, row.open, row.high, row.low, row.close, row.volume)
        for row in final_df.itertuples(index=False)
    ]

    import psycopg2
    from psycopg2.extras import execute_values

    # 1. Connect to the DB
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        database=os.environ.get("DB_NAME", "market"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "admin"),
        port="5432"
    )

    # 2. Open a cursor
    cur = conn.cursor()

    # 3. The SQL Query (Use %s for the values)
    insert_query = """
        INSERT INTO stock_candles (ticker, datetime, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (ticker, datetime) DO NOTHING;
    """

    # 4. Execute the bulk insert using execute_values
    # execute_values(cur, sql, data_list)
    execute_values(cur, insert_query, data_tuples)

    # 5. Commit the transaction
    conn.commit()

    # 6. Close connections
    cur.close()
    conn.close()

else:
    print("No data fetched.")