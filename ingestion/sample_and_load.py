"""Stage 1: sample the Home Credit tables and load them into schema `raw`.

Sampling: 50,000 SK_ID_CURR drawn from application_train with seed 42. Every
child table is filtered by those IDs (bureau_balance via the sampled
SK_ID_BUREAU), so referential integrity is preserved by the sampling itself.

Each raw table gets three audit columns (_loaded_at, _source_file, _batch_id)
and every load writes one row per table into audit.load_log.

Usage:
    python -m ingestion.sample_and_load            # reuse cached sample if present
    python -m ingestion.sample_and_load --resample # rebuild the sample from the full CSVs
"""
import argparse
import io
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from common.db import get_engine

DATA_DIR = Path("data")
SAMPLE_DIR = DATA_DIR / "sample"
SAMPLE_SIZE = 50_000
SEED = 42
CHUNK_ROWS = 1_000_000

# Load order matters only for readability; there are no FK constraints in raw.
TABLES = [
    "application_train",
    "bureau",
    "bureau_balance",
    "previous_application",
    "installments_payments",
]

PG_TYPES = {"int64": "bigint", "float64": "double precision", "bool": "boolean"}


def read_filtered(path: Path, key: str, keep: set) -> pd.DataFrame:
    """Read a large CSV in chunks, keeping only rows whose `key` is in `keep`."""
    parts = []
    for chunk in pd.read_csv(path, chunksize=CHUNK_ROWS, low_memory=False):
        parts.append(chunk[chunk[key].isin(keep)])
    return pd.concat(parts, ignore_index=True)


def build_sample() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    print("Sampling application_train ...")
    app = pd.read_csv(DATA_DIR / "application_train.csv", low_memory=False)
    ids = set(app["SK_ID_CURR"].drop_duplicates().sample(n=SAMPLE_SIZE, random_state=SEED))
    app = app[app["SK_ID_CURR"].isin(ids)]
    app.to_csv(SAMPLE_DIR / "application_train.csv", index=False)

    print("Filtering bureau ...")
    bureau = read_filtered(DATA_DIR / "bureau.csv", "SK_ID_CURR", ids)
    bureau.to_csv(SAMPLE_DIR / "bureau.csv", index=False)

    print("Filtering bureau_balance ...")
    bureau_ids = set(bureau["SK_ID_BUREAU"])
    read_filtered(DATA_DIR / "bureau_balance.csv", "SK_ID_BUREAU", bureau_ids).to_csv(
        SAMPLE_DIR / "bureau_balance.csv", index=False
    )

    for name in ("previous_application", "installments_payments"):
        print(f"Filtering {name} ...")
        read_filtered(DATA_DIR / f"{name}.csv", "SK_ID_CURR", ids).to_csv(
            SAMPLE_DIR / f"{name}.csv", index=False
        )


def create_table_sql(table: str, df: pd.DataFrame) -> str:
    cols = [f'"{c}" {PG_TYPES.get(str(t), "text")}' for c, t in df.dtypes.items()]
    cols += ['"_loaded_at" timestamptz', '"_source_file" text', '"_batch_id" text']
    return f'CREATE TABLE raw."{table}" ({", ".join(cols)})'


def load_table(conn, table: str, batch_id: str) -> tuple[int, int]:
    source_file = f"data/{table}.csv"
    df = pd.read_csv(SAMPLE_DIR / f"{table}.csv", low_memory=False)
    n_source_cols = df.shape[1]
    conn.execute(text(f'DROP TABLE IF EXISTS raw."{table}" CASCADE'))
    conn.execute(text(create_table_sql(table, df)))
    df = df.assign(
        _loaded_at=datetime.now(timezone.utc).isoformat(),
        _source_file=source_file,
        _batch_id=batch_id,
    )

    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    cursor = conn.connection.cursor()
    cursor.copy_expert(f'COPY raw."{table}" FROM STDIN WITH (FORMAT csv)', buf)
    return len(df), n_source_cols


def ensure_schemas(conn) -> None:
    for schema in ("raw", "audit", "dq"):
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audit.load_log (
                batch_id         text,
                table_name       text,
                row_count        bigint,
                column_count     int,
                loaded_at        timestamptz,
                duration_seconds numeric(10, 2),
                status           text,
                error_message    text
            )
            """
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resample", action="store_true", help="rebuild data/sample from the full CSVs")
    args = parser.parse_args()

    if args.resample or not all((SAMPLE_DIR / f"{t}.csv").exists() for t in TABLES):
        build_sample()

    engine = get_engine()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:6]
    print(f"Batch {batch_id}")

    with engine.begin() as conn:
        ensure_schemas(conn)

    failed = False
    for table in TABLES:
        started = time.perf_counter()
        loaded_at = datetime.now(timezone.utc)
        rows, cols, status, error = None, None, "success", None
        try:
            with engine.begin() as conn:
                rows, cols = load_table(conn, table, batch_id)
        except Exception as exc:  # logged to audit.load_log, then re-raised at the end
            status, error, failed = "failed", str(exc)[:1000], True
        duration = round(time.perf_counter() - started, 2)

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO audit.load_log VALUES "
                    "(:batch_id, :table_name, :row_count, :column_count, :loaded_at, :duration, :status, :error)"
                ),
                dict(batch_id=batch_id, table_name=table, row_count=rows, column_count=cols,
                     loaded_at=loaded_at, duration=duration, status=status, error=error),
            )
        print(f"  {table:<24} {status:<8} rows={rows} cols={cols} {duration}s")

    if failed:
        raise SystemExit("One or more tables failed to load, see audit.load_log")


if __name__ == "__main__":
    main()
