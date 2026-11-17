"""Data quality checks. Each check is a SQL query that counts rule-breaking rows."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from digital_sales.paths import DB_PATH, SQL_DIR


def run_quality_checks(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Run sql/02_quality_checks.sql and return one row per check with pass/FAIL."""
    query = (SQL_DIR / "02_quality_checks.sql").read_text(encoding="utf-8")
    with duckdb.connect(str(db_path), read_only=True) as con:
        checks = con.execute(query).df()
    checks["status"] = checks["n_failing"].eq(0).map({True: "pass", False: "FAIL"})
    return checks


def assert_no_errors(checks: pd.DataFrame) -> None:
    """Stop the pipeline if an error-level check fails; warnings are only printed."""
    failed = checks[checks["status"] == "FAIL"]
    for row in failed[failed["severity"] == "warn"].itertuples():
        print(f"WARNING: {row.check_name} ({row.n_failing:,} rows)")
    errors = failed[failed["severity"] == "error"]
    if not errors.empty:
        raise ValueError("Data quality errors:\n" + errors.to_string(index=False))