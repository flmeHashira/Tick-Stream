import os
from sqlalchemy import create_engine

# Use DATABASE_URL if provided (Cloud), otherwise fallback to individual vars (Local Docker)
DATABASE_URL = os.environ.get("DATABASE_URL", f"postgresql+psycopg2://{os.environ.get('DB_USER')}:{os.environ.get('DB_PASSWORD')}@{os.environ.get('DB_HOST')}:5432/{os.environ.get('DB_NAME')}")
# pool_pre_ping ensures connections are alive before use
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)