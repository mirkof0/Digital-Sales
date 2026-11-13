"""Download the Hillstrom CSV and build the DuckDB warehouse."""
from __future__ import annotations

import gzip
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from digital_sales.paths import DB_PATH, RAW_CSV, RAW_DIR, SOURCE_JSON, SQL_DIR

PRIMARY_URL = (
    "http://www.minethatdata.com/"
    "Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
)
# Copy hosted by the scikit-uplift maintainers (used by sklift.datasets.fetch_hillstrom).
FALLBACK_URL = "https://hillstorm1.s3.us-east-2.amazonaws.com/hillstorm_no_indices.csv.gz"

EXPECTED_ROWS = 64_000
EXPECTED_COLUMNS = [
    "recency", "history_segment", "history", "mens", "womens", "zip_code",
    "newbie", "channel", "segment", "visit", "conversion", "spend",
]


def _fetch(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (data-download)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _looks_like_hillstrom(data: bytes) -> bool:
    # A dead domain can still answer "200 OK" with an HTML page, so check the header line.
    header = data.split(b"\n", 1)[0].decode("utf-8", errors="ignore").lower()
    return "recency" in header and "spend" in header


def download_raw(force: bool = False) -> Path:
    """Download the CSV once: original source first, mirror as fallback."""
    if RAW_CSV.exists() and not force:
        print(f"Using existing file: {RAW_CSV}")
        return RAW_CSV

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data, source = _fetch(PRIMARY_URL), PRIMARY_URL
        if not _looks_like_hillstrom(data):
            raise ValueError("original source did not return the expected CSV")
    except (OSError, ValueError) as err:
        print(f"Original source failed ({err}). Trying the scikit-uplift mirror.")
        data, source = gzip.decompress(_fetch(FALLBACK_URL)), FALLBACK_URL
        if not _looks_like_hillstrom(data):
            raise ValueError("mirror did not return the expected CSV either") from err

    RAW_CSV.write_bytes(data)
    SOURCE_JSON.write_text(json.dumps({
        "source_url": source,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }, indent=2))
    print(f"Saved {len(data):,} bytes from {source}")
    return RAW_CSV


def build_database(csv_path: Path = RAW_CSV, db_path: Path = DB_PATH) -> None:
    """Rebuild the warehouse from scratch, so every run gives the same database."""
    for path in (db_path, db_path.with_name(db_path.name + ".wal")):
        path.unlink(missing_ok=True)  # fails on Windows if a notebook still holds the file

    script = (SQL_DIR / "01_load.sql").read_text(encoding="utf-8")
    script = script.replace("__RAW_CSV__", csv_path.as_posix())

    with duckdb.connect(str(db_path)) as con:
        con.execute(script)
        _check_load(con)
    print(f"Built {db_path}")


def _check_load(con: duckdb.DuckDBPyConnection) -> None:
    """Smoke test only. The full data quality checks are the next step."""
    columns = [row[0] for row in con.execute("DESCRIBE raw_hillstrom").fetchall()]
    if columns != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected columns: {columns}")

    for table in ("raw_hillstrom", "customers", "campaign_assignment", "campaign_outcomes"):
        (n,) = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        if n != EXPECTED_ROWS:
            raise ValueError(f"{table} has {n:,} rows, expected {EXPECTED_ROWS:,}")