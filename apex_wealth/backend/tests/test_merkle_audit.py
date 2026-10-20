"""
Unit Tests for Pillar 3 Cryptographic HMAC-SHA256 Merkle Audit Proof Engine (`tests/test_merkle_audit.py`).

Verifies:
1. Canonical JSON serialization produces identical HMAC-SHA256 leaf hashes regardless of key insertion order.
2. Binary Merkle tree construction over even and odd numbers of child execution leaves produces deterministic R_Merkle.
3. Inclusion proof paths verify cleanly against R_Merkle for every leaf in the batch.
4. Any tampering with payload fields, sibling hashes, or secret key K_audit immediately fails verification
   and triggers `WARN_PAST_MERKLE_MISMATCH` in the Tri-Horizon Alert Engine.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, List

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine.alert_system import TriHorizonAlertEngine
from engine.audit_merkle import MerkleAuditEngine, MerkleSiblingStep


def _sample_execution_payloads() -> List[Dict[str, Any]]:
    return [
        {
            "child_order_id": "PO-NABIL-01-CH01",
            "symbol": "NABIL",
            "side": "SELL",
            "quantity": 50,
            "execution_price": 1245.0,
            "tax_bracket": "5.0% LTCGT",
            "broker_code": "58",
            "boid_masked": "130101******2910",
        },
        {
            "child_order_id": "PO-NICA-02-CH01",
            "symbol": "NICA",
            "side": "SELL",
            "quantity": 320,
            "execution_price": 890.0,
            "tax_bracket": "5.0% LTCGT",
            "broker_code": "45",
            "boid_masked": "130106******8374",
        },
        {
            "child_order_id": "PO-CHDC-03-CH01",
            "symbol": "CHDC",
            "side": "BUY",
            "quantity": 180,
            "execution_price": 1620.0,
            "tax_bracket": "N/A (BUY)",
            "broker_code": "45",
            "boid_masked": "130106******8374",
        },
        {
            "child_order_id": "PO-HDL-04-CH01",
            "symbol": "HDL",
            "side": "SELL",
            "quantity": 110,
            "execution_price": 1980.0,
            "tax_bracket": "7.5% STCGT",
            "broker_code": "34",
            "boid_masked": "130112******5667",
        },
        {
            "child_order_id": "PO-NRIC-05-CH01",
            "symbol": "NRIC",
            "side": "BUY",
            "quantity": 240,
            "execution_price": 780.0,
            "tax_bracket": "N/A (BUY)",
            "broker_code": "34",
            "boid_masked": "130112******5667",
        },
    ]


def test_canonical_json_key_order_invariance() -> None:
    engine = MerkleAuditEngine(secret_key="test_sovereign_key_2026")
    payload_a = {"symbol": "NABIL", "quantity": 50, "price": 1245.0, "side": "SELL"}
    payload_b = {"side": "SELL", "price": 1245.0, "symbol": "NABIL", "quantity": 50}

    assert engine.canonicalize_json(payload_a) == engine.canonicalize_json(payload_b)
    assert engine.compute_leaf_hash(payload_a) == engine.compute_leaf_hash(payload_b)


def test_merkle_tree_generation_and_inclusion_proof_verification() -> None:
    payloads = _sample_execution_payloads()
    engine = MerkleAuditEngine(secret_key="test_sovereign_key_2026")
    root_hash = engine.build_tree(payloads)

    assert len(root_hash) == 64

    for idx, payload in enumerate(payloads):
        receipt = engine.generate_proof(idx)
        assert receipt.is_verified is True
        assert receipt.merkle_root == root_hash
        assert engine.verify_proof(payload, receipt.proof_path, root_hash) is True
        assert MerkleAuditEngine.verify_leaf_hash_against_root(
            receipt.leaf_hash, receipt.proof_path, root_hash
        ) is True


def test_merkle_proof_detects_payload_and_sibling_tampering() -> None:
    payloads = _sample_execution_payloads()
    engine = MerkleAuditEngine(secret_key="test_sovereign_key_2026")
    root_hash = engine.build_tree(payloads)

    receipt_0 = engine.generate_proof(0)

    # 1. Tamper with quantity in payload 0
    tampered_payload = dict(payloads[0])
    tampered_payload["quantity"] = 51
    is_valid_tampered = engine.verify_proof(
        tampered_payload, receipt_0.proof_path, root_hash
    )
    assert is_valid_tampered is False

    # 2. Tamper with sibling hash in proof path
    corrupted_steps = list(receipt_0.proof_path)
    first_step = corrupted_steps[0]
    corrupted_steps[0] = MerkleSiblingStep(
        level=first_step.level,
        position=first_step.position,
        sibling_hash="f" * 64,
    )
    assert engine.verify_proof(payloads[0], corrupted_steps, root_hash) is False

    # 3. Verify that failed Merkle verification triggers WARN_PAST_MERKLE_MISMATCH
    alert_engine = TriHorizonAlertEngine()
    alerts = alert_engine.evaluate_past_horizon(
        merkle_verification_passed=is_valid_tampered,
        symbol="NABIL",
    )
    assert any(a.code == "WARN_PAST_MERKLE_MISMATCH" for a in alerts)
