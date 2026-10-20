"""
Pillar 3 — Cryptographic HMAC-SHA256 Merkle Audit Proof Engine (`engine/audit_merkle.py`).

Implements:
1. Leaf Node Hashing:
   For every child-order execution payload E_i, computes leaf hash using private audit key K_audit
   over canonical JSON string (sorted keys, compact separators, UTF-8):
       H_i = HMAC-SHA256(K_audit, CanonicalJSON(E_i))
2. Binary Merkle Tree Construction:
   Concatenates and hashes child pairs:
       H_ij = SHA256(H_i || H_j)
   up to Merkle Root R_Merkle. Odd leaf nodes at any level are duplicated with themselves
   to form a balanced binary level.
3. Cryptographic Proof Generation & Tamper Verification:
   - Generates inclusion proof paths (sibling hash + position `left` / `right`) for any leaf index.
   - Verifies any payload E_i + proof path against the committed R_Merkle without revealing
     private BOID balances of sibling executions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from typing import Any, Dict, List, Optional, Sequence


DEFAULT_AUDIT_SECRET_KEY = os.getenv(
    "APEX_WEALTH_AUDIT_KEY",
    "apex_sovereign_institutional_merkle_audit_hmac_key_2026_v1",
)


@dataclass(frozen=True)
class MerkleSiblingStep:
    """Single step in a Merkle inclusion proof path."""

    level: int
    position: str  # "left" or "right" indicating where the sibling sits relative to current hash
    sibling_hash: str


@dataclass
class MerkleAuditReceipt:
    """Complete cryptographic audit receipt for a child order execution payload."""

    receipt_id: str
    leaf_index: int
    leaf_hash: str
    merkle_root: str
    proof_path: List[MerkleSiblingStep] = field(default_factory=list)
    canonical_payload_json: str = ""
    is_verified: bool = True
    algorithm: str = "HMAC-SHA256 / SHA256-MERKLE"


class MerkleAuditEngine:
    """
    Cryptographic HMAC-SHA256 Merkle Tree Generator & Proof Verifier.
    """

    def __init__(self, secret_key: str = DEFAULT_AUDIT_SECRET_KEY) -> None:
        if not secret_key:
            raise ValueError("Audit secret key K_audit must be non-empty.")
        self._key_bytes: bytes = secret_key.encode("utf-8")
        self.leaves: List[str] = []
        self.payloads: List[Dict[str, Any]] = []
        self.tree_levels: List[List[str]] = []

    @staticmethod
    def canonicalize_json(payload: Dict[str, Any]) -> str:
        """
        Convert execution payload E_i into a deterministic Canonical JSON string:
        lexicographically sorted keys, no extraneous whitespace, UTF-8 safe.
        """
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def compute_leaf_hash(self, payload: Dict[str, Any]) -> str:
        """
        Compute HMAC-SHA256 leaf hash over canonical JSON representation of E_i:
            H_i = HMAC-SHA256(K_audit, CanonicalJSON(E_i))
        """
        canonical_str = self.canonicalize_json(payload)
        return hmac.new(
            self._key_bytes,
            canonical_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def combine_pair_hash(left_hash: str, right_hash: str) -> str:
        """
        Compute parent node hash from concatenated child hashes:
            H_ij = SHA256(H_i || H_j)
        """
        concatenated = f"{left_hash}{right_hash}".encode("utf-8")
        return hashlib.sha256(concatenated).hexdigest()

    def build_tree(self, payloads: Sequence[Dict[str, Any]]) -> str:
        """
        Build a complete Merkle tree from a sequence of child order execution payloads
        and return the anchored Merkle Root R_Merkle.
        """
        if not payloads:
            empty_root = hashlib.sha256(b"APEX_EMPTY_MERKLE_TREE").hexdigest()
            self.leaves = []
            self.payloads = []
            self.tree_levels = [[empty_root]]
            return empty_root

        self.payloads = [dict(p) for p in payloads]
        self.leaves = [self.compute_leaf_hash(p) for p in self.payloads]
        self.tree_levels = [list(self.leaves)]

        current_level = list(self.leaves)
        while len(current_level) > 1:
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])

            next_level: List[str] = []
            for idx in range(0, len(current_level), 2):
                parent_hash = self.combine_pair_hash(
                    current_level[idx], current_level[idx + 1]
                )
                next_level.append(parent_hash)

            self.tree_levels.append(next_level)
            current_level = next_level

        return self.merkle_root

    @property
    def merkle_root(self) -> str:
        """Return the current Merkle Root R_Merkle."""
        if not self.tree_levels:
            return hashlib.sha256(b"APEX_EMPTY_MERKLE_TREE").hexdigest()
        return self.tree_levels[-1][0]

    def generate_proof(self, leaf_index: int) -> MerkleAuditReceipt:
        """
        Generate the Merkle Proof Path (Leaf Hash H_i, Sibling Hashes, Root Hash R_Merkle)
        for the execution payload at `leaf_index`.
        """
        if not self.leaves or leaf_index < 0 or leaf_index >= len(self.leaves):
            raise IndexError(
                f"Leaf index {leaf_index} out of range for Merkle tree with {len(self.leaves)} leaves."
            )

        idx = int(leaf_index)
        leaf_hash = self.leaves[idx]
        proof_steps: List[MerkleSiblingStep] = []

        for level_num in range(len(self.tree_levels) - 1):
            level_nodes = list(self.tree_levels[level_num])
            if len(level_nodes) % 2 == 1:
                level_nodes.append(level_nodes[-1])

            if idx % 2 == 0:
                sibling_idx = idx + 1
                sibling_pos = "right"
            else:
                sibling_idx = idx - 1
                sibling_pos = "left"

            proof_steps.append(
                MerkleSiblingStep(
                    level=level_num,
                    position=sibling_pos,
                    sibling_hash=level_nodes[sibling_idx],
                )
            )
            idx //= 2

        payload = self.payloads[leaf_index]
        receipt_id = str(
            payload.get("child_order_id")
            or payload.get("execution_id")
            or f"AUDIT-LEAF-{leaf_index:04d}"
        )
        is_valid = self.verify_proof(
            payload=payload,
            proof_path=proof_steps,
            expected_merkle_root=self.merkle_root,
        )

        return MerkleAuditReceipt(
            receipt_id=receipt_id,
            leaf_index=leaf_index,
            leaf_hash=leaf_hash,
            merkle_root=self.merkle_root,
            proof_path=proof_steps,
            canonical_payload_json=self.canonicalize_json(payload),
            is_verified=is_valid,
        )

    def verify_proof(
        self,
        payload: Dict[str, Any],
        proof_path: Sequence[MerkleSiblingStep],
        expected_merkle_root: str,
    ) -> bool:
        """
        Cryptographically verify whether `payload` (hashed with K_audit) and `proof_path`
        reconstruct `expected_merkle_root`. Any single-character tampering in `payload`,
        any sibling hash modification, or any root mismatch returns False.
        """
        computed_hash = self.compute_leaf_hash(payload)
        for step in proof_path:
            if step.position == "right":
                computed_hash = self.combine_pair_hash(computed_hash, step.sibling_hash)
            elif step.position == "left":
                computed_hash = self.combine_pair_hash(step.sibling_hash, computed_hash)
            else:
                raise ValueError(f"Invalid sibling position: {step.position}")

        return hmac.compare_digest(computed_hash, expected_merkle_root)

    @classmethod
    def verify_leaf_hash_against_root(
        cls,
        leaf_hash: str,
        proof_path: Sequence[MerkleSiblingStep],
        expected_merkle_root: str,
    ) -> bool:
        """Verify an already-computed leaf hash H_i against expected R_Merkle without exposing payload."""
        computed_hash = str(leaf_hash)
        for step in proof_path:
            if step.position == "right":
                computed_hash = cls.combine_pair_hash(computed_hash, step.sibling_hash)
            elif step.position == "left":
                computed_hash = cls.combine_pair_hash(step.sibling_hash, computed_hash)
            else:
                raise ValueError(f"Invalid sibling position: {step.position}")

        return hmac.compare_digest(computed_hash, expected_merkle_root)
