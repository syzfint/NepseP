#!/usr/bin/env python3
"""
scripts/00_control/release_manager.py

APEXMARKETENGINE — PRODUCTION RELEASE MANAGER (PHASE 9)
========================================================
Manages immutable release lifecycles:
  RESEARCH -> VALIDATION -> CERTIFICATION -> RELEASE CANDIDATE -> PRODUCTION
Assigns official institutional release IDs (e.g. AMME-2026.10.07-R04).
"""

import os
import sys
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path.cwd()
REGISTRY_RELEASES = BASE_DIR / "registry" / "releases"
REGISTRY_RELEASES.mkdir(parents=True, exist_ok=True)


class ReleaseManager:
    DEFAULT_RELEASE_ID = "AMME-2026.10.07-R04"

    def __init__(self, release_id: Optional[str] = None):
        self.release_id = release_id or self.DEFAULT_RELEASE_ID

    def get_release_metadata(self) -> Dict[str, Any]:
        """Loads or constructs metadata for the active release."""
        rel_file = REGISTRY_RELEASES / f"RELEASE-{self.release_id.replace('AMME-', '')}.json"
        if not rel_file.exists():
            rel_file = REGISTRY_RELEASES / "RELEASE-2026.10.07-R04.json"

        if rel_file.exists():
            with open(rel_file, "r", encoding="utf-8") as f:
                return json.load(f)

        return {
            "release_id": self.release_id,
            "status": "PRODUCTION_RELEASE",
            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    def verify_release_eligibility(self, governance_result: Dict[str, Any]) -> bool:
        """Verifies if the release candidate is approved for production deployment."""
        return governance_result.get("status") == "CERTIFIED"
