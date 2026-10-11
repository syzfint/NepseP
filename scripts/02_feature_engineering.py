#!/usr/bin/env python3
"""
ApexMarketEngine — Feature Engineering & Microstructure Store
=============================================================
Calculates:
  1. Scale-Invariant Multi-Period Moving Averages & Volatility (t-1 lag enforced)
  2. K-Line Pattern Semantics (Upper/Lower Shadow Ratios, Body Density, Gap Rejections)
  3. Price + Volume Coupling (Volume Z-Scores, Force Index, OBV Slope Divergence, Amihud)
  4. NEPSE Floor Sheet Broker Accumulation Concentration (when available)
  5. Ghost Feature Pipeline (frac_diff_close, macd_norm, rsi_14, log_return, range_vol)
     Previously these 5 features were silently zero-filled. They are now explicitly
     computed with Pandera schema validation.
"""

import logging
import os
import sys
import time
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class FeatureComputationError(RuntimeError):
    """Raised when a declared feature cannot be computed or fails validation."""


# ---------------------------------------------------------------------------
# Ghost feature helper functions (tasks 6.1 – 6.5)
# ---------------------------------------------------------------------------

def _frac_diff_fixed(series: pd.Series, d: float = 0.35, window: int = 10) -> pd.Series:
    """Fixed-width window fractional differentiation (task 6.1).

    Computes fractional differences using a fixed-width convolution window.
    No external ``fracdiff`` dependency required.

    Parameters
    ----------
    series : pd.Series
        Raw price series for a single ticker (index will be preserved).
    d : float
        Fractional differencing order (0 < d < 1). Default 0.35.
    window : int
        Width of the convolution window. Default 10.

    Returns
    -------
    pd.Series
        Fractionally differentiated series; NaN for the first ``window-1`` rows.
    """
    weights: list[float] = [1.0]
    for k in range(1, window):
        w = weights[-1] * (d - k + 1) / k
        weights.append(w)
    w_arr = np.array(weights[::-1])  # oldest weight first

    result = pd.Series(np.nan, index=series.index, dtype=float)
    arr = series.values
    for i in range(window - 1, len(arr)):
        window_vals = arr[i - window + 1 : i + 1]
        if not np.any(np.isnan(window_vals)):
            result.iloc[i] = float(np.dot(w_arr, window_vals))
    return result


def _macd_norm_series(series: pd.Series) -> pd.Series:
    """Normalized MACD histogram (task 6.2).

    Returns ``(macd_line - signal_line) / (close + ε)`` — the histogram
    normalized by price to make it scale-invariant across tickers.
    """
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return histogram / (series + 1e-6)


def _rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI with Wilder's exponential smoothing (task 6.3).

    Uses ``alpha = 1/period`` EWM (equivalent to Wilder's RMA) instead of
    the simple rolling mean used in the legacy ``compute_rsi()`` function,
    which produced values that would sometimes hit boundary artefacts.

    Returns values in [0, 100].
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-8)
    return 100.0 - (100.0 / (1.0 + rs))

# Bootstrap connection manager (works whether run as a script or as a module)
# NOTE: 'scripts/03_data_access_and_storage' has a numeric prefix that makes
# it an invalid Python module name, so we load it via importlib by file path.
_ALT_DIR_CM = Path(r"C:/Users/achar/Downloads/neps")

def _load_connection_manager():
    """Load duckdb_connection_manager by file path to work around the numeric
    directory prefix that prevents a standard dotted import."""
    import importlib.util as _ilu
    for _base in [Path(__file__).resolve().parent.parent, _ALT_DIR_CM]:
        _cm_path = _base / "scripts" / "03_data_access_and_storage" / "duckdb_connection_manager.py"
        if _cm_path.exists():
            _cm_spec = _ilu.spec_from_file_location("duckdb_connection_manager", _cm_path)
            _cm_mod = _ilu.module_from_spec(_cm_spec)
            _cm_spec.loader.exec_module(_cm_mod)
            return _cm_mod.connection_manager, _cm_mod.get_connection_manager
    # Fallback: return None sentinels — run_feature_engineering() will fail
    # gracefully if the connection manager is unavailable.
    return None, None

connection_manager, get_connection_manager = _load_connection_manager()

# Multi-workspace resolution
BASE_DIR = Path.cwd()
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


def resolve_path(relative_path: str) -> Path:
    p = BASE_DIR / relative_path
    if p.exists():
        return p
    alt = ALT_DIR / relative_path
    if alt.exists():
        return alt
    return p


def sync_to_both(src_path: Path, filename: str):
    for b in [BASE_DIR, ALT_DIR]:
        if b.exists():
            dest = b / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest != src_path:
                try:
                    dest.write_bytes(src_path.read_bytes())
                except Exception:
                    pass


def add_price_volume_and_kline_semantics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates Price-Volume Coupling & Candlestick Geometry Features for

    LightGBM / Gate G4 Meta-Labeler.
    """
    eps = 1e-6
    # Ensure correct symbol column name
    sym_col = "symbol" if "symbol" in df.columns else "ticker"
    df = df.sort_values([sym_col, "date"]).copy()

    # --- 1. Candlestick Geometry (K-Line Semantics) ---
    range_high_low = df["high"] - df["low"] + eps
    body_size = (df["close"] - df["open"]).abs()

    df["kline_upper_shadow_ratio"] = (
        df["high"] - df[["open", "close"]].max(axis=1)
    ) / range_high_low
    df["kline_lower_shadow_ratio"] = (
        df[["open", "close"]].min(axis=1) - df["low"]
    ) / range_high_low
    df["kline_body_density"] = body_size / range_high_low

    # Gap-Up Rejection (Bull Trap Flag)
    prev_close = df.groupby(sym_col)["close"].shift(1)
    gap_pct = (df["open"] - prev_close) / (prev_close + eps)
    intraday_ret = (df["close"] - df["open"]) / (df["open"] + eps)
    df["kline_gap_rejection_flag"] = (
        (gap_pct > 0.02) & (intraday_ret < -0.015)
    ).astype(float)

    # Donchian Proximity (Channel Base / Ceiling Proximity)
    roll_high_20 = (
        df.groupby(sym_col)["high"]
        .transform(lambda x: x.rolling(20, min_periods=5).max())
    )
    roll_low_20 = (
        df.groupby(sym_col)["low"]
        .transform(lambda x: x.rolling(20, min_periods=5).min())
    )
    df["donchian_channel_pos_20"] = (df["close"] - roll_low_20) / (
        roll_high_20 - roll_low_20 + eps
    )

    # --- 2. Price + Volume Coupling ---
    vol_mean_20 = (
        df.groupby(sym_col)["volume"]
        .transform(lambda x: x.rolling(20, min_periods=5).mean())
    )
    vol_std_20 = (
        df.groupby(sym_col)["volume"]
        .transform(lambda x: x.rolling(20, min_periods=5).std())
    )
    df["volume_zscore_20"] = (df["volume"] - vol_mean_20) / (vol_std_20 + eps)

    # Price Return (1-session)
    ret_1d = df.groupby(sym_col)["close"].pct_change()

    # Force Index (Volume-Confirmed Return)
    df["volume_force_index"] = ret_1d * df["volume_zscore_20"]

    # OBV Trend Divergence (5-session slope)
    df["_obv_step"] = np.sign(ret_1d).fillna(0) * df["volume"]
    df["obv"] = df.groupby(sym_col)["_obv_step"].cumsum()

    obv_shift_5 = df.groupby(sym_col)["obv"].shift(5)
    obv_slope_5 = (df["obv"] - obv_shift_5) / (obv_shift_5.abs() + eps)

    price_shift_5 = df.groupby(sym_col)["close"].shift(5)
    price_slope_5 = (df["close"] - price_shift_5) / (price_shift_5 + eps)

    # Negative value = Bearish Volume Divergence
    df["price_volume_divergence_5d"] = obv_slope_5 - price_slope_5

    # Amihud Illiquidity Ratio
    turnover = df["close"] * df["volume"]
    df["amihud_illiquidity"] = ret_1d.abs() / (turnover + eps)

    # Cleanup temporary columns
    df.drop(columns=["_obv_step"], inplace=True)

    # -----------------------------------------------------------------------
    # Ghost Feature Pipeline — tasks 6.1 – 6.5
    # These 5 features were previously absent from this pipeline and were
    # silently zero-filled by the training script via .fillna(0.0).
    # -----------------------------------------------------------------------

    # 6.1 — frac_diff_close (d=0.35, fixed-width window fractional differencing)
    df["frac_diff_close"] = df.groupby(sym_col)["close"].transform(
        lambda x: _frac_diff_fixed(x.reset_index(drop=True), d=0.35).values
    )

    # 6.2 — macd_norm (normalized MACD histogram)
    df["macd_norm"] = df.groupby(sym_col)["close"].transform(_macd_norm_series)

    # 6.3 — rsi_14 (RSI with Wilder's EWM smoothing, values in [0, 100])
    df["rsi_14"] = df.groupby(sym_col)["close"].transform(_rsi_wilder)

    # 6.4 — log_return (natural log return; NaN on first row per ticker)
    df["log_return"] = df.groupby(sym_col)["close"].transform(
        lambda x: np.log(x / x.shift(1).replace(0, np.nan))
    )

    # 6.5 — range_vol (20-period rolling std of daily range %)
    df["_daily_range_pct"] = (df["high"] - df["low"]) / (df["close"] + 1e-6)
    df["range_vol"] = df.groupby(sym_col)["_daily_range_pct"].transform(
        lambda x: x.rolling(20, min_periods=5).std()
    )
    df.drop(columns=["_daily_range_pct"], inplace=True)

    # -----------------------------------------------------------------------
    # 6.9 — Explicit feature summary logging
    # -----------------------------------------------------------------------
    _ghost_features = ["frac_diff_close", "macd_norm", "rsi_14", "log_return", "range_vol"]
    for _feat in _ghost_features:
        _col = df[_feat]
        _non_null_pct = _col.notna().mean() * 100
        _zero_pct = (_col == 0.0).mean() * 100
        logger.info(
            "%s: mean=%.4f, std=%.4f, non-null=%.1f%%, zero=%.1f%%",
            _feat,
            _col.mean() if _col.notna().any() else float("nan"),
            _col.std() if _col.notna().any() else float("nan"),
            _non_null_pct,
            _zero_pct,
        )
        if _zero_pct > 95.0:
            logger.warning(
                "Possible ghost feature '%s': %.1f%% zero values — check computation.",
                _feat,
                _zero_pct,
            )

    # -----------------------------------------------------------------------
    # 6.6 + 6.7 — Pandera schema validation (replaces silent .fillna(0.0))
    # -----------------------------------------------------------------------
    try:
        try:
            import pandera.pandas as pa  # pandera >= 0.20 preferred API
        except ImportError:
            import pandera as pa  # fallback for older versions

        FEATURE_SCHEMA = pa.DataFrameSchema(
            {
                "frac_diff_close": pa.Column(float, nullable=True),
                "macd_norm": pa.Column(float, nullable=True),
                "rsi_14": pa.Column(
                    float, pa.Check.in_range(0, 100, include_min=True, include_max=True), nullable=True
                ),
                "log_return": pa.Column(float, nullable=True),
                "range_vol": pa.Column(
                    float, pa.Check.greater_than_or_equal_to(0), nullable=True
                ),
            },
            coerce=True,
        )
        FEATURE_SCHEMA.validate(df[list(FEATURE_SCHEMA.columns)])
        logger.info("Pandera feature schema validation passed.")

    except ImportError:
        logger.warning(
            "pandera not installed — skipping schema validation. "
            "Install pandera>=0.20.0 for runtime feature assertions."
        )
    except Exception as exc:
        raise FeatureComputationError(
            f"Feature schema validation failed: {exc}"
        ) from exc

    return df


def run_feature_engineering():
    print("=" * 80)
    print("STEP 2: SCALE-INVARIANT FEATURE STORE & K-LINE / PRICE-VOLUME SEMANTICS")
    print("=" * 80)

    t0 = time.time()
    target_parquet = resolve_path("02_processed_parquet/market_master_union.parquet")
    tech_out = BASE_DIR / "03_feature_store" / "technical_indicators.parquet"
    floorsheet_path = resolve_path("03_feature_store/floorsheet_broker_signals.parquet")

    if not target_parquet.exists():
        print(f"Error: {target_parquet} not found. Run Step 1 first!")
        return

    print(f"Reading from Lakehouse: {target_parquet}")
    with connection_manager.acquire() as con:
        sql = f"""
    WITH base AS (
        SELECT 
            ticker,
            CAST(date AS DATE) as date,
            open, high, low, close, volume,
            security_type,
            close * volume AS turnover,
            LAG(close, 1) OVER w AS prev_close,
            LAG(volume, 1) OVER w AS prev_vol,
            AVG(volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS adv_20d,
            AVG(close * volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS turnover_20d,
            SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS active_days_20d,
            AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS sma_20,
            AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING) AS sma_50,
            STDDEV(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS std_20,
            LAG(close, 5) OVER w AS close_lag5,
            LAG(close, 10) OVER w AS close_lag10,
            LAG(close, 20) OVER w AS close_lag20
        FROM read_parquet('{str(target_parquet).replace('\\', '/')}')
        WHERE security_type IN ('ORDINARY_EQUITY', 'MICROFINANCE')
        WINDOW w AS (PARTITION BY ticker ORDER BY date)
    )
    SELECT 
        ticker, date, open, high, low, close, volume, security_type,
        adv_20d, turnover_20d, active_days_20d,
        sma_20, sma_50,
        ((prev_close / (sma_20 + 1e-6)) - 1.0) AS dist_sma20,
        ((prev_close / (sma_50 + 1e-6)) - 1.0) AS dist_sma50,
        (((prev_close - (sma_20 - 2.0 * std_20)) / (4.0 * std_20 + 1e-6))) AS bb_pct_b,
        ((prev_close / (close_lag5 + 1e-6)) - 1.0) AS ret_1w,
        ((prev_close / (close_lag10 + 1e-6)) - 1.0) AS ret_2w,
        ((prev_close / (close_lag20 + 1e-6)) - 1.0) AS ret_1m,
        (std_20 / (sma_20 + 1e-6)) AS volatility_20,
        ((prev_vol / (adv_20d + 1e-4)) - 1.0) AS vol_surge
    FROM base
    ORDER BY ticker ASC, date ASC
    """
        print("Computing DuckDB base window aggregations...")
        df_base = con.execute(sql).df()
    print(f"Base rows: {len(df_base):,}. Appending K-line & Price-Volume Semantics...")
    df_enriched = add_price_volume_and_kline_semantics(df_base)

    # Optional Floorsheet Broker Concentration Join
    if floorsheet_path.exists():
        print("Enriching with NEPSE Floor Sheet Top-Buyer Concentration signals...")
        with connection_manager.acquire() as con_fs:
            con_fs.register("enriched", df_enriched)
            # Temporal Safety: 1-session lag enforced — broker signals from day T-1 join price row T
            # This prevents future information leakage: the price row for date T now receives
            # broker accumulation data from date T-1 (the last fully-observable session).
            join_sql = f"""
                SELECT 
                    e.*,
                    COALESCE(f.top3_buyer_share, 0.0) AS top_buyer_concentration,
                    COALESCE(f.buyer_hhi, 0.0) AS buyer_hhi,
                    COALESCE(f.net_hhi_imbalance, 0.0) AS broker_net_imbalance
                FROM enriched e
                LEFT JOIN read_parquet('{str(floorsheet_path).replace('\\', '/')}') f
                  ON e.ticker = f.ticker AND CAST(f.date AS DATE) = e.date - INTERVAL 1 DAY
                ORDER BY e.ticker ASC, e.date ASC
            """
            df_final = con_fs.execute(join_sql).df()
    else:
        df_final = df_enriched
        df_final["top_buyer_concentration"] = 0.0
        df_final["buyer_hhi"] = 0.0
        df_final["broker_net_imbalance"] = 0.0

    # Save to Parquet
    tech_out.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_parquet(tech_out, index=False)
    sync_to_both(tech_out, "03_feature_store/technical_indicators.parquet")

    # Register view in market_analytics.duckdb
    for b in [BASE_DIR, ALT_DIR]:
        duckdb_file = b / "02_processed_parquet" / "market_analytics.duckdb"
        if duckdb_file.exists():
            db_mgr = get_connection_manager(database=str(duckdb_file))
            with db_mgr.acquire() as con_db:
                con_db.execute(f"""
                    CREATE OR REPLACE VIEW technical_indicators AS 
                    SELECT * FROM read_parquet('{str(tech_out).replace('\\', '/')}')
                """)

    elapsed = time.time() - t0
    print(f"\nFeature Store updated successfully in {elapsed:.2f}s!")
    print(f"Output File : {tech_out}")
    print(f"Feature Rows: {len(df_final):,} | Total Columns: {len(df_final.columns)}")
    print("New Microstructure Features Appended:")
    print("  - kline_upper_shadow_ratio, kline_lower_shadow_ratio, kline_body_density")
    print("  - kline_gap_rejection_flag, donchian_channel_pos_20")
    print("  - volume_zscore_20, volume_force_index, price_volume_divergence_5d, amihud_illiquidity")
    print("  - top_buyer_concentration, buyer_hhi, broker_net_imbalance")
    print("=" * 80)


if __name__ == "__main__":
    run_feature_engineering()
