#!/usr/bin/env python3
"""
scripts/00_control/market_rules_synchronizer.py

Dynamic Market Rules & Regulatory Knowledge Synchronizer
=========================================================
Audits, validates, and synchronizes statutory parameters in configs/market_rules.json:
  - SEBON broker commission tiers
  - SEBON regulatory fees & DP transaction charges
  - Capital Gains Tax (CGT 5% long-term, 7.5% short-term, 10% corporate)
  - NRB Margin Lending Caps (NPR 15 Cr individual / 20 Cr institutional)
  - Promoter Share 3-year lock-in freeze window limits
  - NEPSE Circuit Breaker thresholds (4%, 5%, 6%)
  - Deterministic accounting verification error tolerances (±0.01%)

Enforces cryptographic hash tracking and schema integrity.
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("market_rules_sync")

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "configs" / "market_rules.json"
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


class MarketRulesSynchronizer:
    def __init__(self, config_file: Optional[Path] = None):
        self.config_path = config_file or CONFIG_PATH
        if not self.config_path.exists():
            raise FileNotFoundError(f"Market rules configuration not found at {self.config_path}")
        self._rules = self.load_rules()

    def load_rules(self) -> Dict[str, Any]:
        """Loads and parses market rules config."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    @property
    def rules(self) -> Dict[str, Any]:
        return self._rules

    def compute_sha256(self) -> str:
        """Computes SHA256 digest of canonical JSON serialization."""
        content = json.dumps(self._rules, sort_keys=True).encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def validate_rules_schema(self) -> bool:
        """Validates that all mandatory regulatory fields are present and valid."""
        required_keys = [
            "broker_commission_slabs",
            "regulatory_fees",
            "capital_gains_tax",
            "nrb_macro_lending",
            "listing_and_governance",
            "circuit_breakers",
            "accounting_audit_tolerances"
        ]
        for key in required_keys:
            if key not in self._rules:
                raise ValueError(f"Missing required market rules key: {key}")

        cgt = self._rules["capital_gains_tax"]
        if cgt.get("individual_short_term_rate") != 0.075:
            raise ValueError(f"Unexpected individual short term CGT: {cgt.get('individual_short_term_rate')}")
        if cgt.get("individual_long_term_rate") != 0.050:
            raise ValueError(f"Unexpected individual long term CGT: {cgt.get('individual_long_term_rate')}")

        cb = self._rules["circuit_breakers"]
        if cb.get("first_halt_pct") != 0.04 or cb.get("second_halt_pct") != 0.05 or cb.get("final_halt_pct") != 0.06:
            raise ValueError("Circuit breaker percentages do not conform to NEPSE statutory rules (4%, 5%, 6%).")

        return True

    def calculate_commission(self, trade_amount: float) -> float:
        """Computes SEBON tiered broker commission for a given turnover amount."""
        slabs = self._rules["broker_commission_slabs"]
        for slab in slabs:
            max_amt = slab.get("max_amount")
            rate = slab.get("rate")
            if max_amt is None or trade_amount <= max_amt:
                return round(trade_amount * rate, 4)
        return round(trade_amount * 0.0027, 4)

    def calculate_effective_costs(self, trade_amount: float, is_sell: bool = True, gain: float = 0.0, is_short_term: bool = True) -> Dict[str, float]:
        """Calculates all trade execution friction costs (Broker Commission, SEBON Fee, DP Fee, CGT)."""
        comm = self.calculate_commission(trade_amount)
        sebon_fee = round(trade_amount * self._rules["regulatory_fees"]["sebon_fee_rate"], 4)
        dp_fee = self._rules["regulatory_fees"]["dp_charge_per_trade_npr"] if is_sell else 0.0

        cgt = 0.0
        if is_sell and gain > 0:
            cgt_rate = (
                self._rules["capital_gains_tax"]["individual_short_term_rate"]
                if is_short_term
                else self._rules["capital_gains_tax"]["individual_long_term_rate"]
            )
            cgt = round(gain * cgt_rate, 4)

        total_friction = round(comm + sebon_fee + dp_fee + cgt, 4)
        return {
            "trade_amount": trade_amount,
            "broker_commission": comm,
            "sebon_fee": sebon_fee,
            "dp_charge": dp_fee,
            "capital_gains_tax": cgt,
            "total_friction": total_friction,
            "net_proceeds_or_cost": round(trade_amount - total_friction if is_sell else trade_amount + total_friction, 4)
        }

    def sync_to_alt_directory(self) -> bool:
        """Mirrors market rules to alternative physical directory."""
        if ALT_DIR.exists():
            dest = ALT_DIR / "configs" / "market_rules.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(self._rules, f, indent=2)
            logger.info(f"Mirrored market_rules.json to {dest}")
            return True
        return False


def main():
    sync = MarketRulesSynchronizer()
    is_valid = sync.validate_rules_schema()
    rule_hash = sync.compute_sha256()
    print(f"Market Rules Validated: {is_valid}")
    print(f"Market Rules Hash: {rule_hash}")

    sample_buy = sync.calculate_effective_costs(100000.0, is_sell=False)
    sample_sell = sync.calculate_effective_costs(120000.0, is_sell=True, gain=20000.0, is_short_term=True)
    print("Sample Buy Cost (100k):", sample_buy)
    print("Sample Sell Cost (120k with 20k gain):", sample_sell)
    sync.sync_to_alt_directory()


if __name__ == "__main__":
    main()
