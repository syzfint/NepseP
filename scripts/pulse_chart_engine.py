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
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
MASTER_PARQUET = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from scripts.db_connection import connection_manager
from scripts.db_connection import run_in_threadpool

import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

_CHART_CACHE: Dict[str, Dict[str, Any]] = {}
_CHART_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ChartAggWorker")


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
        """
        Renders an institutional visual frame or returns cached output using state-shift thresholding.
        Decoupled from unnecessary re-renders when price delta < 0.20% and cache age < 5.0s.
        """
        sym_clean = str(symbol).strip().upper()
        cache_key = f"{mode}:{sym_clean}"
        now = time.time()

        if cache_key in _CHART_CACHE:
            cached_item = _CHART_CACHE[cache_key]
            cached_ltp = cached_item.get("ltp", 0.0)
            cached_ts = cached_item.get("timestamp", 0.0)
            if cached_ltp > 0:
                delta_pct = abs(ltp - cached_ltp) / cached_ltp
                if delta_pct < 0.0020 and (now - cached_ts) < 5.0:
                    return cached_item["frame"]

        sub = cls._prepare_sub_dataframe(sym_clean, ltp)
        fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
        fig.patch.set_facecolor("#0b0e14")
        ax.set_facecolor("#111827")
        
        buf = io.BytesIO()
        try:
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
            
            plt.tight_layout()
            plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        finally:
            # Enforce instance-level figure handle destruction (thread-safe; avoids destroying concurrent figures)
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
        _CHART_CACHE[cache_key] = {
            "frame": frame,
            "ltp": ltp,
            "timestamp": now
        }
        return frame

    @classmethod
    async def render_chart_async(cls, mode: str, symbol: str, ltp: float) -> Dict[str, Any]:
        """Asynchronously dispatches chart rendering to background worker thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_CHART_EXECUTOR, cls.get_cached_or_render, mode, symbol, ltp)

    @classmethod
    def render_institutional_probability_corridor_png(
        cls,
        symbol: str,
        base_price: float,
        p2_5: List[float],
        p10: List[float],
        p25: List[float],
        p50: List[float],
        p75: List[float],
        p90: List[float],
        p97_5: List[float],
        mc_paths: Optional[List[List[float]]] = None,
        calendar_events: Optional[List[Dict[str, Any]]] = None,
        terminal_kde: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Renders a multi-band shaded fan chart with spaghetti paths, discrete event kinks,
        and a right-hand terminal KDE density plot via Matplotlib/Agg into Base64 PNG.
        """
        n = len(p50)
        days = np.arange(1, n + 1)

        # 2-column layout: Corridor (85% width) + KDE (15% width)
        fig = plt.figure(figsize=(10, 4.5), dpi=120)
        fig.patch.set_facecolor("#080b10")
        gs = fig.add_gridspec(1, 2, width_ratios=[8.5, 1.5], wspace=0.04)

        ax_main = fig.add_subplot(gs[0])
        ax_kde = fig.add_subplot(gs[1], sharey=ax_main)

        ax_main.set_facecolor("#0b0e14")
        ax_kde.set_facecolor("#0b0e14")

        buf = io.BytesIO()
        try:
            # 1. Multi-band shaded confidence intervals
            ax_main.fill_between(days, p2_5, p97_5, color="#00e5ff", alpha=0.08, label="95% Tail Boundary (P2.5–P97.5)")
            ax_main.fill_between(days, p10, p90, color="#00b4d8", alpha=0.22, label="80% Outer Interval (P10–P90)")
            ax_main.fill_between(days, p25, p75, color="#0077b6", alpha=0.40, label="50% Core Interval (P25–P75)")

            # 2. Monte Carlo Spaghetti Paths
            if mc_paths:
                for path in mc_paths[:60]:
                    if len(path) == n:
                        ax_main.plot(days, path, color="#00e5ff", alpha=0.12, lw=0.6)

            # 3. Discrete Event Kinks Markers
            if calendar_events:
                for ev in calendar_events:
                    day_idx = ev.get("day", 5)
                    ax_main.axvline(x=day_idx, color="#ffb703", linestyle="--", lw=1.2, alpha=0.7)
                    ax_main.text(day_idx, max(p97_5) * 0.99, f" ⚡ {ev.get('label')}", color="#ffb703",
                                 fontsize=7.5, rotation=90, va="top", ha="right")

            # 4. Quantile Curves
            ax_main.plot(days, p90, color="#00e676", linestyle="--", lw=1.5, label="P90 Bull Target")
            ax_main.plot(days, p10, color="#ff1744", linestyle="--", lw=1.5, label="P10 Bear Floor")
            ax_main.plot(days, p50, color="#00e5ff", lw=2.4, label="P50 Median Path")

            ax_main.set_title(f"{symbol} Institutional Probability Corridor (Chronos-Bolt + G4 Multi-Band)",
                              color="#f0f6fc", fontsize=10.5, fontweight="bold", pad=10)
            ax_main.set_xlabel("Forecast Horizon (Sessions)", color="#8b949e", fontsize=8.5)
            ax_main.set_ylabel("Price (NPR)", color="#8b949e", fontsize=8.5)
            ax_main.tick_params(colors="#8b949e", labelsize=8)
            ax_main.grid(True, color="#161b22", linestyle=":", lw=0.8)
            ax_main.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=7.5)

            # 5. Right-Hand Terminal KDE Density Plot
            if terminal_kde and "grid_prices" in terminal_kde and "norm_density" in terminal_kde:
                gp = np.array(terminal_kde["grid_prices"])
                nd = np.array(terminal_kde["norm_density"])
                ax_kde.fill_betweenx(gp, 0, nd, color="#00e5ff", alpha=0.25)
                ax_kde.plot(nd, gp, color="#00e5ff", lw=1.2)
                ax_kde.axhline(y=p90[-1], color="#00e676", linestyle=":", lw=1.0)
                ax_kde.axhline(y=p50[-1], color="#00e5ff", linestyle=":", lw=1.2)
                ax_kde.axhline(y=p10[-1], color="#ff1744", linestyle=":", lw=1.0)

            ax_kde.set_title("D+20 KDE", color="#8b949e", fontsize=8.5, pad=10)
            ax_kde.set_xlabel("Density", color="#8b949e", fontsize=8)
            ax_kde.tick_params(colors="#8b949e", labelsize=7.5)
            ax_kde.grid(True, color="#161b22", linestyle=":", lw=0.8)
            plt.setp(ax_kde.get_yticklabels(), visible=False)

            plt.tight_layout()
            plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        finally:
            plt.close(fig)

        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")


def prewarm_universe_charts(universe: Optional[Dict[str, Any]] = None):
    """Prewarms cache for active securities."""
    targets = ["SAHAS", "NABIL", "ADBL", "SHIVM", "CHCL"]
    for sym in targets:
        try:
            InstitutionalChartEngine.get_cached_or_render("CANDLE", sym, 500.0)
        except Exception:
            pass
