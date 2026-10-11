import duckdb
from pathlib import Path

base = Path(r"c:\Users\achar\Downloads\neps")
targets = [
    base / "02_processed_parquet" / "market_master_union.parquet",
    base / "03_feature_store" / "technical_indicators.parquet",
    base / "03_feature_store" / "chronos_quantiles_5d.parquet",
    base / "03_feature_store" / "floorsheet_broker_signals.parquet",
    base / "01_raw_data" / "nepse_floorsheet_2026-10-07.parquet",
]

con = duckdb.connect()
for p in targets:
    print("=" * 60)
    print(p.name, "exists=", p.exists())
    if not p.exists():
        continue
    print("size_mb=", round(p.stat().st_size / 1e6, 2))
    cols = con.execute(
        "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet(?))",
        [str(p)],
    ).fetchall()
    colnames = [c[0].lower() for c in cols]
    print("cols=", colnames[:20])
    date_col = None
    for candidate in ("date", "trade_date", "as_of", "session_date"):
        if candidate in colnames:
            date_col = candidate
            break
    if date_col is None:
        continue
    r = con.execute(
        f'SELECT MIN("{date_col}"), MAX("{date_col}"), COUNT(*) FROM read_parquet(?)',
        [str(p)],
    ).fetchone()
    print("min=", r[0], "max=", r[1], "rows=", r[2])
    late = con.execute(
        f'SELECT DISTINCT "{date_col}" FROM read_parquet(?) WHERE "{date_col}" >= \'2026-09-25\' ORDER BY 1',
        [str(p)],
    ).fetchall()
    print("from_2026-09-25:")
    for x in late:
        d = x[0]
        wd = d.strftime("%A") if hasattr(d, "strftime") else ""
        print(" ", d, wd)
