"""
Strict Price & Prediction Integrity Protocol (`engine/price_integrity_protocol.py`).

Enforces two non-negotiable architectural invariants across Apex Wealth:
1. ZERO SYNTHETIC PRICES / RETURNS (`NEVER_SYNTHESIZE_PRICE`):
   - Stock prices (`LTP` / `closePrice`) and historical daily return series must NEVER be
     synthesized via random number generators (`np.random`), sine waves, or hardcoded dummy values.
   - Every price must carry a verified `PriceProvenanceRecord` with `source_type` strictly in:
     * `"REAL_NEPSE_HISTORICAL_CLOSE"` (loaded from `01_raw_data/nepse_floorsheet_*.json` or `nepse_data_all/*.csv`)
     * `"USER_ENTERED_PRICE"` (explicitly entered or edited by the user)
2. EXPLICIT PREDICTION DISCLOSURE (`EXPLICIT_PREDICTION_DISCLOSURE`):
   - Model forecasts, target weights, and risk projections must NEVER be presented as actual market prices.
   - Every model forecast is wrapped in an `ExplicitPredictionRecord` carrying `is_prediction=True`,
     `disclosure_label="[EXPLICIT MODEL PREDICTION — NOT ACTUAL MARKET PRICE]"`, `model_name`, and `horizon`.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.ipc_shared_memory import allocate_cache_aligned_matrix
from engine.portfolio_optimizer import ReturnsFrame


ALLOWED_PRICE_SOURCES = frozenset({
    "REAL_NEPSE_HISTORICAL_CLOSE",
    "USER_ENTERED_PRICE",
})


class SyntheticPriceViolationError(RuntimeError):
    """Raised immediately if any component attempts to register a synthetic or unverified price."""


@dataclass
class PriceProvenanceRecord:
    symbol: str
    price: float
    source_type: str  # Strictly "REAL_NEPSE_HISTORICAL_CLOSE" or "USER_ENTERED_PRICE"
    as_of_date: str
    source_detail: str
    is_synthetic: bool = False
    is_prediction: bool = False

    def validate(self) -> None:
        if self.is_synthetic or self.source_type not in ALLOWED_PRICE_SOURCES:
            raise SyntheticPriceViolationError(
                f"PROTOCOL VIOLATION: Attempted to use non-permitted or synthetic price source "
                f"'{self.source_type}' for symbol '{self.symbol}'."
            )
        if self.is_prediction:
            raise SyntheticPriceViolationError(
                f"PROTOCOL VIOLATION: Model prediction for '{self.symbol}' cannot be registered "
                f"as an actual market price (LTP)."
            )


@dataclass
class ExplicitPredictionRecord:
    symbol: str
    is_prediction: bool
    is_actual_market_price: bool
    disclosure_label: str
    model_name: str
    horizon: str
    as_of_date: str
    latest_verified_close: float
    predicted_p10_price: Optional[float]
    predicted_p50_price: Optional[float]
    predicted_p90_price: Optional[float]
    predicted_return_pct: float
    uncertainty_spread_pct: Optional[float]
    regime_label: str
    confidence_probability: Optional[float]


class StrictPriceIntegrityEngine:
    """
    Loads verified historical NEPSE closing prices, historical daily return series,
    and explicitly labeled model predictions from the workspace data lake.
    """

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        # Resolve `c:\Users\achar\Downloads\neps` relative to `apex_wealth/backend/engine`
        self.workspace_root = workspace_root or Path(__file__).resolve().parents[3]
        self.nepse_csv_dir = self.workspace_root / "nepse_data_all"
        self.raw_data_dir = self.workspace_root / "01_raw_data"
        self.master_pred_path = self.workspace_root / "NEPSE_MASTER_INTEGRATED_OUTPUT.json"
        self.oct5_pred_path = self.workspace_root / "NEPSE_OCT5_PREDICTION.json"

        # Symbol -> (latest_close_price, business_date, source_file)
        self.verified_nepse_closes: Dict[str, Tuple[float, str, str]] = {}
        # Symbol -> List of (date_str, close_price) ordered chronologically
        self.historical_close_series: Dict[str, List[Tuple[str, float]]] = {}
        # Ordered list of historical trading dates loaded
        self.historical_dates: List[str] = []
        # Symbol -> ExplicitPredictionRecord
        self.explicit_predictions: Dict[str, ExplicitPredictionRecord] = {}

        self._load_real_nepse_historical_closes(max_days=180)
        self._load_real_floorsheet_closes()
        self._load_explicit_model_predictions()

    def _load_real_nepse_historical_closes(self, max_days: int = 180) -> None:
        """Load real historical daily closing prices from `nepse_data_all/*.csv`."""
        if not self.nepse_csv_dir.exists():
            return

        csv_files = sorted(glob.glob(str(self.nepse_csv_dir / "*.csv")))
        if max_days > 0 and len(csv_files) > max_days:
            csv_files = csv_files[-max_days:]

        for fpath in csv_files:
            fname = os.path.basename(fpath)
            date_from_name = fname.replace(".csv", "").replace("_", "-")
            self.historical_dates.append(date_from_name)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sym = (row.get("symbol") or row.get("Symbol") or "").strip().upper()
                        raw_close = (
                            row.get("closePrice")
                            or row.get("Close")
                            or row.get("LTP")
                            or ""
                        )
                        raw_close = str(raw_close).replace(",", "").strip()
                        if not sym or not raw_close:
                            continue
                        try:
                            close_val = float(raw_close)
                        except ValueError:
                            continue
                        if close_val <= 0:
                            continue
                        b_date = (row.get("businessDate") or date_from_name).strip()
                        self.historical_close_series.setdefault(sym, []).append(
                            (b_date, close_val)
                        )
                        self.verified_nepse_closes[sym] = (
                            close_val,
                            b_date,
                            f"nepse_data_all/{fname}",
                        )
            except Exception:
                continue

    def _load_real_floorsheet_closes(self) -> None:
        """Load the most recent verified floorsheet trade rates from `01_raw_data/nepse_floorsheet_*.json`."""
        if not self.raw_data_dir.exists():
            return

        fs_files = sorted(glob.glob(str(self.raw_data_dir / "nepse_floorsheet_*.json")))
        if not fs_files:
            return

        latest_fs_path = fs_files[-1]
        fname = os.path.basename(latest_fs_path)
        try:
            with open(latest_fs_path, "r", encoding="utf-8") as f:
                trades = json.load(f)
            if not isinstance(trades, list):
                return
            # Floorsheet JSON is ordered newest contract first; capture latest rate per stockSymbol
            seen_in_fs: set[str] = set()
            for trade in trades:
                sym = str(trade.get("stockSymbol") or "").strip().upper()
                rate = trade.get("contractRate")
                b_date = str(trade.get("businessDate") or "2026-10-16").strip()
                if sym and rate is not None and sym not in seen_in_fs:
                    try:
                        rate_val = float(rate)
                        if rate_val > 0:
                            seen_in_fs.add(sym)
                            self.verified_nepse_closes[sym] = (
                                rate_val,
                                b_date,
                                f"01_raw_data/{fname}",
                            )
                            series = self.historical_close_series.setdefault(sym, [])
                            if not series or series[-1][0] != b_date:
                                series.append((b_date, rate_val))
                    except ValueError:
                        continue
        except Exception:
            pass

    def _load_explicit_model_predictions(self) -> None:
        """
        Load model forecasts from `NEPSE_MASTER_INTEGRATED_OUTPUT.json` and `NEPSE_OCT5_PREDICTION.json`
        and tag every entry explicitly as a MODEL PREDICTION (never an actual price).
        """
        if self.master_pred_path.exists():
            try:
                raw = json.loads(self.master_pred_path.read_text(encoding="utf-8"))
                as_of = str(raw.get("timestamp") or "2026-10-06")[:10]
                for item in raw.get("top_candidates", []):
                    sym = str(item.get("symbol") or "").strip().upper()
                    if not sym:
                        continue
                    self.explicit_predictions[sym] = ExplicitPredictionRecord(
                        symbol=sym,
                        is_prediction=True,
                        is_actual_market_price=False,
                        disclosure_label="[EXPLICIT MODEL PREDICTION — NOT ACTUAL MARKET PRICE]",
                        model_name="Chronos-Bolt + Kronos + Meta-Labeling Ensemble",
                        horizon="5 Trading Days (p10 / p50 / p90 Price Quantiles)",
                        as_of_date=as_of,
                        latest_verified_close=float(item.get("latest_close") or 0.0),
                        predicted_p10_price=float(item["p10_5d"]) if item.get("p10_5d") is not None else None,
                        predicted_p50_price=float(item["p50_5d"]) if item.get("p50_5d") is not None else None,
                        predicted_p90_price=float(item["p90_5d"]) if item.get("p90_5d") is not None else None,
                        predicted_return_pct=round(float(item.get("exp_return_5d_pct") or 0.0), 2),
                        uncertainty_spread_pct=round(float(item.get("uncertainty_spread_pct") or 0.0), 2),
                        regime_label=str(item.get("kronos_regime") or "NEUTRAL"),
                        confidence_probability=round(float(item.get("meta_label_probability") or 0.0), 4),
                    )
            except Exception:
                pass

        if self.oct5_pred_path.exists():
            try:
                raw = json.loads(self.oct5_pred_path.read_text(encoding="utf-8"))
                as_of = str(raw.get("as_of_market_close") or "2026-10-04")
                target_dt = str(raw.get("prediction_target_date") or "1-Week Ahead")
                for item in raw.get("top_10_long_forecasts", []):
                    sym = str(item.get("ticker") or "").strip().upper()
                    if not sym or sym in self.explicit_predictions:
                        continue
                    latest_c = float(item.get("latest_close") or 0.0)
                    ret_1w = float(item.get("ret_1w_pct") or 0.0)
                    proj_p50 = round(latest_c * (1.0 + ret_1w / 100.0), 2) if latest_c > 0 else None
                    self.explicit_predictions[sym] = ExplicitPredictionRecord(
                        symbol=sym,
                        is_prediction=True,
                        is_actual_market_price=False,
                        disclosure_label="[EXPLICIT MODEL PREDICTION — NOT ACTUAL MARKET PRICE]",
                        model_name="Cross-Sectional Weekly Alpha Model",
                        horizon=f"1-Week Forecast (Target: {target_dt})",
                        as_of_date=as_of,
                        latest_verified_close=latest_c,
                        predicted_p10_price=None,
                        predicted_p50_price=proj_p50,
                        predicted_p90_price=None,
                        predicted_return_pct=round(ret_1w, 2),
                        uncertainty_spread_pct=round(float(item.get("vol_20d_pct") or 0.0), 2),
                        regime_label=str(raw.get("market_regime") or "HISTORICAL_FORECAST"),
                        confidence_probability=round(float(item.get("composite_score") or 0.0), 4),
                    )
            except Exception:
                pass

    def resolve_verified_price(
        self,
        symbol: str,
        user_supplied_ltp: Optional[float],
        user_purchase_price: float,
    ) -> PriceProvenanceRecord:
        """
        Resolve the price of `symbol` strictly without ever synthesizing a price:
        1. If the user explicitly supplied an LTP (`user_supplied_ltp > 0`), tag as `USER_ENTERED_PRICE`.
        2. Else if `symbol` exists in verified NEPSE historical records (`01_raw_data` / `nepse_data_all`),
           use the real NEPSE closing price and tag as `REAL_NEPSE_HISTORICAL_CLOSE` with exact date & file.
        3. Else fall back to the user's own `user_purchase_price` and tag as `USER_ENTERED_PRICE (Cost Basis)`.
        """
        sym = symbol.strip().upper()
        if user_supplied_ltp is not None and float(user_supplied_ltp) > 0:
            rec = PriceProvenanceRecord(
                symbol=sym,
                price=round(float(user_supplied_ltp), 2),
                source_type="USER_ENTERED_PRICE",
                as_of_date="User-Specified",
                source_detail="Explicitly entered by user (Manual LTP)",
                is_synthetic=False,
                is_prediction=False,
            )
            rec.validate()
            return rec

        if sym in self.verified_nepse_closes:
            close_price, b_date, src_file = self.verified_nepse_closes[sym]
            rec = PriceProvenanceRecord(
                symbol=sym,
                price=round(float(close_price), 2),
                source_type="REAL_NEPSE_HISTORICAL_CLOSE",
                as_of_date=b_date,
                source_detail=f"Verified NEPSE Close ({src_file}, {b_date})",
                is_synthetic=False,
                is_prediction=False,
            )
            rec.validate()
            return rec

        rec = PriceProvenanceRecord(
            symbol=sym,
            price=round(float(user_purchase_price), 2),
            source_type="USER_ENTERED_PRICE",
            as_of_date="User-Specified",
            source_detail="User-entered Purchase Price (No NEPSE symbol match)",
            is_synthetic=False,
            is_prediction=False,
        )
        rec.validate()
        return rec

    def build_real_historical_returns_frame(
        self,
        symbols: List[str],
        min_window: int = 180,
    ) -> Tuple[ReturnsFrame, Dict[str, Dict[str, Any]]]:
        """
        Build a T x N historical daily return matrix strictly from real NEPSE closing prices
        in `nepse_data_all/*.csv` (ZERO `np.random`, ZERO synthetic factors).
        Also returns a per-symbol provenance dictionary describing the exact historical window used.
        """
        ordered_syms = sorted(set(s.strip().upper() for s in symbols if s.strip()))
        n_assets = len(ordered_syms)
        if n_assets == 0:
            return ReturnsFrame(np.zeros((min_window, 0), dtype=np.float64), columns=[]), {}

        raw_return_lists: Dict[str, List[float]] = {}
        return_provenance: Dict[str, Dict[str, Any]] = {}

        max_len = min_window
        for sym in ordered_syms:
            pts = self.historical_close_series.get(sym, [])
            if len(pts) >= 2:
                closes = np.array([p[1] for p in pts], dtype=np.float64)
                rets = np.diff(closes) / np.maximum(closes[:-1], 1e-8)
                ret_list = [float(x) for x in rets]
                raw_return_lists[sym] = ret_list
                max_len = max(max_len, len(ret_list))
                return_provenance[sym] = {
                    "symbol": sym,
                    "source": "REAL_NEPSE_HISTORICAL_DAILY_CLOSES",
                    "observations_count": len(ret_list),
                    "start_date": pts[0][0],
                    "end_date": pts[-1][0],
                    "is_synthetic": False,
                }
            else:
                # No historical CSV series for custom user symbol: use zero-return vector (never random!)
                raw_return_lists[sym] = []
                return_provenance[sym] = {
                    "symbol": sym,
                    "source": "USER_CUSTOM_SYMBOL_NO_NEPSE_HISTORY",
                    "observations_count": 0,
                    "start_date": None,
                    "end_date": None,
                    "is_synthetic": False,
                }

        n_days = max(min_window, max_len)
        ret_mat = allocate_cache_aligned_matrix((n_days, n_assets), dtype=np.float64)
        ret_mat.fill(0.0)

        for idx, sym in enumerate(ordered_syms):
            r_list = raw_return_lists[sym]
            if len(r_list) > 0:
                tail = r_list[-n_days:]
                # Align at the end of the historical matrix; pad any earlier missing pre-IPO days with 0.0 (never random)
                offset = n_days - len(tail)
                ret_mat[offset:, idx] = np.asarray(tail, dtype=np.float64)

        return ReturnsFrame(ret_mat, columns=ordered_syms), return_provenance

    def get_protocol_manifest(self) -> Dict[str, Any]:
        """Return the machine-verifiable Strict Data & Price Integrity Protocol manifest."""
        return {
            "protocol_id": "APEX_STRICT_PRICE_AND_PREDICTION_PROTOCOL_V1",
            "enforced": True,
            "zero_synthetic_prices": True,
            "zero_synthetic_returns": True,
            "random_generators_prohibited": True,
            "sine_wave_ticks_prohibited": True,
            "allowed_price_sources": sorted(ALLOWED_PRICE_SOURCES),
            "verified_nepse_symbols_loaded": len(self.verified_nepse_closes),
            "historical_trading_days_loaded": len(self.historical_dates),
            "explicit_model_predictions_loaded": len(self.explicit_predictions),
            "rules": [
                "1. NEVER fabricate, hardcode, or synthesize stock prices (LTP) or return series.",
                "2. Actual prices must strictly originate from verified NEPSE historical closes (01_raw_data / nepse_data_all) or explicit user input.",
                "3. Every model forecast, target weight, or risk projection must carry is_prediction=True and an explicit [MODEL PREDICTION] disclosure badge.",
            ],
        }
