from pathlib import Path

# src/digital_sales/paths.py -> parents[2] is the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_CSV = RAW_DIR / "hillstrom.csv"
SOURCE_JSON = RAW_DIR / "source.json"
DB_PATH = DATA_DIR / "warehouse.duckdb"
SQL_DIR = PROJECT_ROOT / "sql"
RESULTS_DIR = PROJECT_ROOT / "results"   # small tables the dashboard reads (committed)