"""Shared database connection settings, read from environment variables."""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

PG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": os.getenv("PGPORT", "5433"),
    "dbname": os.getenv("PGDATABASE", "lending"),
    "user": os.getenv("PGUSER", "dg"),
    "password": os.getenv("PGPASSWORD", "dg"),
}


def get_engine() -> Engine:
    url = (
        f"postgresql+psycopg2://{PG['user']}:{PG['password']}"
        f"@{PG['host']}:{PG['port']}/{PG['dbname']}"
    )
    return create_engine(url)
