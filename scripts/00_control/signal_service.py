#!/usr/bin/env python3
"""
scripts/00_control/signal_service.py

APEXMARKETENGINE — INSTITUTIONAL SIGNAL SERVICE & CLIENT BOUNDARY (PHASE 7)
===========================================================================
Transforms internal complex quant pipeline representations into clean,
standardized, institutional external signals:
{
  "instrument": "H8020",
  "as_of": "2026-10-07",
  "direction": "BULLISH",
  "confidence": 0.81,
  "regime": "CONFIRMED_FLOOR_BOUNCE",
  "horizon": "5D",
  "hrp_allocation_pct": 3.13,
  "expected_return_5d_pct": 1.55,
  "uncertainty_spread_pct": 5.55,
  "release": "AMME-2026.10.07-R04",
  "system_status": "CERTIFIED_PASS"
}
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

BASE_DIR = Path.cwd()
SCRIPTS_DIR = BASE_DIR / "scripts"
CONTROL_DIR = SCRIPTS_DIR / "00_control"

for p in [str(BASE_DIR), str(SCRIPTS_DIR), str(CONTROL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from apex_engine import ApexEngine


class InstitutionalSignal(BaseModel):
    instrument: str = Field(description="NEPSE Scrip Symbol")
    as_of: str = Field(description="Trading session date")
    direction: str = Field(description="BULLISH / DEFENSIVE / NEUTRAL")
    confidence: float = Field(description="Calibrated Bayesian Meta-Probability [0.0, 1.0]")
    regime: str = Field(description="Kronos Candlestick Sequence Regime")
    horizon: str = Field(default="5D", description="Forward forecast horizon")
    hrp_allocation_pct: float = Field(description="Optimal portfolio weight (%)")
    expected_return_5d_pct: float = Field(description="5-day forward expected return (%)")
    uncertainty_spread_pct: float = Field(description="Predictive uncertainty spread (%)")
    release: str = Field(description="Production release ID")
    system_status: str = Field(description="System and release governance status")


class SignalService:
    def __init__(self, engine: Optional[ApexEngine] = None):
        self.engine = engine or ApexEngine()

    def get_signals(
        self,
        as_of: str = "2026-10-07",
        universe: str = "NEPSE",
        top_n: int = 10
    ) -> List[InstitutionalSignal]:
        """Generates clean institutional signals from ApexEngine output."""
        engine_res = self.engine.predict(as_of=as_of, universe=universe)
        release_id = engine_res.get("release_id", "AMME-2026.10.07-R04")
        system_status = engine_res.get("overall_gate_status", "CERTIFIED_PASS")

        signals = []
        for cand in engine_res.get("top_candidates", [])[:top_n]:
            exp_ret = float(cand.get("exp_return_5d_pct", 0.0))
            meta_prob = float(cand.get("meta_label_probability", 0.50))
            direction = "BULLISH" if exp_ret > 0 and meta_prob >= 0.55 else "NEUTRAL"

            sig = InstitutionalSignal(
                instrument=cand["symbol"],
                as_of=as_of,
                direction=direction,
                confidence=round(meta_prob, 4),
                regime=cand.get("kronos_regime", "CONFIRMED_FLOOR_BOUNCE"),
                horizon="5D",
                hrp_allocation_pct=float(cand.get("hrp_allocation_pct", 0.0)),
                expected_return_5d_pct=round(exp_ret, 2),
                uncertainty_spread_pct=round(float(cand.get("uncertainty_spread_pct", 0.0)), 2),
                release=release_id,
                system_status=system_status
            )
            signals.append(sig)

        return signals

    def get_signals_dict(self, as_of: str = "2026-10-07", top_n: int = 10) -> List[Dict[str, Any]]:
        return [s.model_dump() for s in self.get_signals(as_of=as_of, top_n=top_n)]


if __name__ == "__main__":
    service = SignalService()
    sigs = service.get_signals_dict(as_of="2026-10-07", top_n=5)
    print(json.dumps(sigs, indent=2))
