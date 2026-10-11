"""
scripts/pulse_chart_engine.py

Institutional In-Memory Graphics Engine & Sub-Dataframe Loader.
Provides OHLCV time series extraction, EMA, Bollinger Bands, and base64 chart rendering.
"""

import io
import os
import sys
import base64
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
MASTER_PARQUET = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from scripts.03_data_access_and_storage.duckdb_connection_manager import connection_manager
from scripts.03_data_access_and_storage.async_duckdb_executor import run_in_threadpool

_CHART_CACHE: Dict[str, Dict[str, Any]] = {}


class InstitutionalChartEngine:
    @classmethod
    def _prepare_sub_dataframe(cls, symbol: str, ltp: float = 0.0) -> pd.DataFrame:
        """Extract historical daily bars for symbol from market_master_union and calculate technical indicators."""
        sym_clean = str(symbol).strip().upper()
        if not MASTER_PARQUET.exists():
            return pd.DataFrame()

        p_str = str(MASTER_PARQUET).replace('\\', '/')
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM read_parquet('{p_str}')
            WHERE ticker = '{sym_clean}'
            ORDER BY date ASC
        """
        try:
            with connection_manager.acquire() as con:
                df = con.execute(query).df()
        except Exception:
            df = pd.DataFrame()
            
        if len(df) == 0:
            return df
            
        df["date"] = pd.to_datetime(df["date"])
        # Calculate EMA20, EMA50, Bollinger Bands
        df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["std20"] = df["close"].rolling(20, min_periods=5).std().fillna(df["close"].std() or 1.0)
        df["boll_mid"] = df["close"].rolling(20, min_periods=5).mean().fillna(df["close"])
        df["boll_up"] = df["boll_mid"] + 2.0 * df["std20"]
        df["boll_low"] = df["boll_mid"] - 2.0 * df["std20"]
        return df

    @classmethod
    def get_cached_or_render(cls, mode: str, symbol: str, ltp: float) -> Dict[str, Any]:
        """Renders an institutional visual frame or returns cached output."""
        sym_clean = str(symbol).strip().upper()
        cache_key = f"{mode}:{sym_clean}"
        if cache_key in _CHART_CACHE:
            return _CHART_CACHE[cache_key]
            
        sub = cls._prepare_sub_dataframe(sym_clean, ltp)
        fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
        fig.patch.set_facecolor("#0b0e14")
        ax.set_facecolor("#111827")
        
        if len(sub) > 0:
            tail = sub.tail(30)
            ax.plot(tail["date"], tail["close"], label=f"{sym_clean} Close", color="#38bdf8", lw=1.8)
            if "ema20" in tail:
                ax.plot(tail["date"], tail["ema20"], label="EMA 20", color="#fbbf24", lw=1.2, linestyle="--")
            ax.set_title(f"{sym_clean} — {mode} Suite", color="#f3f4f6", fontsize=11, fontweight="bold")
            ax.tick_params(colors="#9ca3af")
            ax.legend(facecolor="#1f2937", edgecolor="#374151", labelcolor="#e5e7eb")
        else:
            ax.text(0.5, 0.5, f"Rendering {sym_clean} ({mode})", ha="center", va="center", color="#9ca3af")
            
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode("utf-8")
        
        frame = {
            "chart_base64": img_b64,
            "mode": mode,
            "symbol": sym_clean,
            "ltp": ltp,
            "band": [round(ltp * 0.85, 1), round(ltp * 1.15, 1)]
        }
        _CHART_CACHE[cache_key] = frame
        return frame


def prewarm_universe_charts(universe: Optional[Dict[str, Any]] = None):
    """Prewarms cache for active securities."""
    targets = ["SAHAS", "NABIL", "ADBL", "SHIVM", "CHCL"]
    for sym in targets:
        try:
            InstitutionalChartEngine.get_cached_or_render("CANDLE", sym, 500.0)
        except Exception:
            pass
