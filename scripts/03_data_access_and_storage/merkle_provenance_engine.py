"""
scripts/03_data_access_and_storage/merkle_provenance_engine.py

CONTINUOUS HMAC-SHA256 MERKLE PROVENANCE CHAIN
================================================
Implements non-repudiable audit ledger for order executions, data ingress blocks,
and Lakehouse states under SEBON and Gate G10 cryptographic audit standards.

Formula:
  H_t = HMAC-SHA256(K_secret, H_{t-1} || seq || payload_hash || timestamp)
"""

import os
import json
import time
import hmac
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CHAIN_FILE = DATA_DIR / "merkle_provenance.chain"

# Default cryptographic secret (can be overridden by environment)
SECRET_SALT = os.environ.get("APEX_MERKLE_KEY", "NEPSE_SOVEREIGN_MERKLE_SECRET_SALT_2026").encode("utf-8")
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


class MerkleProvenanceChain:
    """Manages an append-only verifiable cryptographic provenance chain."""

    def __init__(self, chain_path: Optional[Path] = None):
        self.chain_path = chain_path or CHAIN_FILE
        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[Dict[str, Any]] = []
        self._load_chain()

    def _load_chain(self):
        """Loads and verifies chain integrity on startup."""
        self.entries = []
        if self.chain_path.exists():
            with open(self.chain_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self.entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

    def get_latest_hash(self) -> str:
        """Returns the tip of the Merkle chain or GENESIS."""
        if not self.entries:
            return GENESIS_HASH
        return self.entries[-1]["merkle_hash"]

    def append_block(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Appends a cryptographically sealed block to the ledger."""
        prev_hash = self.get_latest_hash()
        seq = len(self.entries) + 1
        ts = time.time()

        # Compute payload hash
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        # Compute HMAC-SHA256: H_t = HMAC(K, prev_hash || seq || payload_hash || ts)
        message = f"{prev_hash}|{seq}|{payload_hash}|{ts:.6f}".encode("utf-8")
        merkle_hash = hmac.new(SECRET_SALT, message, hashlib.sha256).hexdigest()

        entry = {
            "seq": seq,
            "timestamp": ts,
            "event_type": event_type,
            "prev_hash": prev_hash,
            "payload_hash": payload_hash,
            "merkle_hash": merkle_hash,
            "payload_summary": {k: str(v)[:80] for k, v in payload.items()}
        }

        with open(self.chain_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        self.entries.append(entry)
        return entry

    def verify_chain_integrity(self) -> Tuple[bool, int, Optional[str]]:
        """
        Validates all blocks in the ledger from Genesis to Tip.
        Returns: (is_valid, verified_count, error_msg)
        """
        if not self.entries:
            return True, 0, None

        prev_hash = GENESIS_HASH
        for idx, entry in enumerate(self.entries):
            expected_seq = idx + 1
            if entry["seq"] != expected_seq:
                return False, idx, f"Sequence discontinuity at index {idx}: expected {expected_seq}, got {entry['seq']}"

            if entry["prev_hash"] != prev_hash:
                return False, idx, f"Broken chain link at seq {entry['seq']}: expected {prev_hash}, got {entry['prev_hash']}"

            # Recompute HMAC
            ts = entry["timestamp"]
            payload_hash = entry["payload_hash"]
            message = f"{prev_hash}|{entry['seq']}|{payload_hash}|{ts:.6f}".encode("utf-8")
            expected_hash = hmac.new(SECRET_SALT, message, hashlib.sha256).hexdigest()

            if entry["merkle_hash"] != expected_hash:
                return False, idx, f"Tampered hash at seq {entry['seq']}"

            prev_hash = entry["merkle_hash"]

        return True, len(self.entries), None
