#!/usr/bin/env python3
"""
Chronos-Bolt Zero-Shot Probabilistic Forecasting Engine
======================================================
Generates 5-day probabilistic quantile trajectories (P10, P50, P90)
using Amazon Chronos-Bolt non-autoregressive foundation model.
Outputs to:
  03_feature_store/chronos_quantiles_5d.parquet
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
import torch

try:
    from chronos import ChronosBoltPipeline
except ImportError:
    ChronosBoltPipeline = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chronos_bolt")

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"
OUTPUT_PARQUET = FEATURE_DIR / "chronos_quantiles_5d.parquet"


class ChronosBoltEngine:
    def __init__(self, model_id: str = "amazon/chronos-bolt-small", device: str = "cpu"):
        self.model_id = model_id
        self.device = device
        self.pipeline = None

    def _load_pipeline(self):
        if self.pipeline is not None or getattr(self, "_load_attempted", False):
            return
        self._load_attempted = True
        if ChronosBoltPipeline is None:
            logger.warning("chronos-bolt package not available. Using Bayesian conformal fallback.")
            return

        logger.info(f"Checking for local Chronos-Bolt pipeline ({self.model_id})...")
        try:
            self.pipeline = ChronosBoltPipeline.from_pretrained(
                self.model_id,
                device_map=self.device,
                torch_dtype=torch.float32,
                local_files_only=True
            )
            logger.info("Local Chronos-Bolt pipeline loaded successfully.")
        except Exception as e:
            logger.info(f"Local Chronos-Bolt weights not pre-cached ({e}). Utilizing fast empirical conformal quantile engine.")
            self.pipeline = None

    def forecast_series(
        self,
        series: np.ndarray,
        dates: Optional[List[Any]] = None,
        prediction_length: int = 5,
    ) -> Dict[str, float]:
        """
        Runs inference on a 1D price series.
        Applies Calendar Continuity Guard if dates are provided:
        Truncates history if a halt > 10 calendar days is present.
        """
        if dates is not None and len(dates) == len(series):
            dts = pd.Series(pd.to_datetime(dates))
            gaps = dts.diff().dt.days
            large_gaps = gaps[gaps > 10]
            if not large_gaps.empty:
                latest_halt = large_gaps.index[-1]
                series = series[latest_halt:]
                if len(series) < 20:
                    curr_p = float(series[-1]) if len(series) > 0 else 0.0
                    return {
                        "p10": round(curr_p * 0.90, 2),
                        "p50": round(curr_p, 2),
                        "p90": round(curr_p * 1.10, 2),
                        "uncertainty_spread": 20.0,
                        "expected_return_pct": 0.0,
                        "status": "SUSPENDED_REOPEN_STABILIZING",
                        # Task 7.4 — consistent model_status across all return paths.
                        "model_status": "GBM_FALLBACK",
                    }

        if len(series) < 10:
            return {"p10": 0.0, "p50": 0.0, "p90": 0.0, "uncertainty_spread": 0.0,
                    "model_status": "INSUFFICIENT_DATA"}

        curr_p = float(series[-1])
        self._load_pipeline()

        if self.pipeline is not None:
            try:
                context = torch.tensor(series, dtype=torch.float32).unsqueeze(0)
                forecast = self.pipeline.predict(context, prediction_length=prediction_length)
                # Forecast quantiles: forecast shape is [batch_size, num_samples, prediction_length]
                samples = forecast[0].numpy()  # [num_samples, 5]
                # End of horizon (day 5)
                day5_samples = samples[:, -1]
                p10 = float(np.percentile(day5_samples, 10))
                p50 = float(np.percentile(day5_samples, 50))
                p90 = float(np.percentile(day5_samples, 90))
                spread = (p90 - p10) / curr_p * 100.0 if curr_p > 0 else 0.0
                # Task 7.7 — pipeline active log entry.
                logger.info("LIVE_CHRONOS model active")
                return {
                    "p10": round(p10, 2),
                    "p50": round(p50, 2),
                    "p90": round(p90, 2),
                    "uncertainty_spread": round(spread, 2),
                    "expected_return_pct": round((p50 - curr_p) / curr_p * 100.0, 2),
                    # Task 7.4 — explicit model status for downstream consumers.
                    "model_status": "LIVE_CHRONOS",
                }
            except Exception as e:
                # Task 7.7 — fallback activation log entry.
                logger.warning("GBM_FALLBACK activated: %s", str(e))
                logger.error(f"Error in Chronos forward pass: {e}")

        # Empirical Bayesian fallback based on historical volatility
        # Task 7.5 — GBM_FALLBACK activated when Chronos pipeline is unavailable
        # or throws an exception during the forward pass.
        ret = np.diff(np.log(series[-30:])) if len(series) >= 30 else np.diff(np.log(series))
        daily_vol = np.std(ret) if len(ret) > 1 else 0.02
        drift = np.mean(ret) * 5.0
        h_vol = daily_vol * np.sqrt(5.0)

        p50 = curr_p * np.exp(drift)
        p10 = curr_p * np.exp(drift - 1.28 * h_vol)
        p90 = curr_p * np.exp(drift + 1.28 * h_vol)
        spread = (p90 - p10) / curr_p * 100.0

        # Task 7.7 — fallback activation log (covers the no-pipeline path).
        logger.warning("GBM_FALLBACK activated: Chronos pipeline unavailable")

        return {
            "p10": round(p10, 2),
            "p50": round(p50, 2),
            "p90": round(p90, 2),
            "uncertainty_spread": round(spread, 2),
            "expected_return_pct": round((p50 - curr_p) / curr_p * 100.0, 2),
            # Task 7.5 — explicit GBM_FALLBACK status tag.
            "model_status": "GBM_FALLBACK",
        }

    def load_cached_quantiles(self) -> pd.DataFrame:
        """Loads cached quantiles parquet if available."""
        if OUTPUT_PARQUET.exists():
            return pd.read_parquet(OUTPUT_PARQUET)
        alt = BASE_DIR / "03_feature_store" / "chronos_forecast_5d_quantiles.parquet"
        if alt.exists():
            return pd.read_parquet(alt)
        return pd.DataFrame()


def main():
    engine = ChronosBoltEngine()
    test_prices = np.array([500.0 + 2.0 * i + np.random.normal(0, 3) for i in range(50)])
    fc = engine.forecast_series(test_prices)
    print("Test Forecast (5d):", fc)

    cached = engine.load_cached_quantiles()
    if not cached.empty:
        print(f"Loaded {len(cached)} cached Chronos quantiles. Columns: {list(cached.columns[:8])}")


if __name__ == "__main__":
    main()
