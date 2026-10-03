import os
from sqlalchemy import create_engine

# Use DATABASE_URL if provided (Cloud), otherwise fallback to
# individual vars (Local Docker)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql+psycopg2://"
    f"{os.environ.get('DB_USER')}:"
    f"{os.environ.get('DB_PASSWORD')}@"
    f"{os.environ.get('DB_HOST')}:5432/"
    f"{os.environ.get('DB_NAME')}"
)

# SQLAlchemy 2.1 defaults bare postgresql:// URLs to psycopg (v3).
# This project uses psycopg2, so explicitly select that driver.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1,
    )
# pool_pre_ping ensures connections are alive before use
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)