/**
 * Section 5.5 — Cryptographic HMAC-SHA256 Merkle Audit Receipt Modal (`src/components/MerkleReceiptModal.tsx`)
 *
 * Displays:
 * - Merkle Proof Path, Leaf Hash H_i = HMAC-SHA256(K_audit, CanonicalJSON(E_i)),
 *   Sibling Hashes H_ij = SHA256(H_i || H_j), and Root Hash R_Merkle.
 * - Green "VERIFIED" cryptographic status badge (or Crimson "TAMPER DETECTED" when simulating payload tampering).
 */

import React, { useState } from "react";
import { AlertOctagon, CheckCircle2, KeyRound, Lock, ShieldCheck, X } from "lucide-react";
import { APEX_THEME_TOKENS } from "../theme/tokens";
import { ActivityFeedItem } from "./TaxActivityFeed";

export interface MerkleReceiptModalProps {
  item: ActivityFeedItem | null;
  onClose: () => void;
}

export const MerkleReceiptModal: React.FC<MerkleReceiptModalProps> = ({
  item,
  onClose,
}) => {
  const [tamperSimulated, setTamperSimulated] = useState<boolean>(false);

  if (!item) return null;

  const receipt = item.receipt;
  const isVerified = tamperSimulated ? false : receipt.is_verified;
  const displayedLeafHash = tamperSimulated
    ? `e9f4b2c1${receipt.leaf_hash.slice(8, 56)}deadbeef`
    : receipt.leaf_hash;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: APEX_THEME_TOKENS.colors.bgSurface2,
          boxShadow: APEX_THEME_TOKENS.elevation.surface2,
        }}
        className="w-full max-w-2xl rounded-2xl border border-slate-700 p-6 space-y-4 text-slate-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-start justify-between gap-4 border-b border-slate-700/80 pb-3">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-6 h-6 text-emerald-400" />
            <div>
              <h3 className="text-base font-bold tracking-wide uppercase">
                Cryptographic HMAC-SHA256 Merkle Audit Proof
              </h3>
              <p className="text-xs text-slate-400 font-mono-tabular">
                Receipt ID: {receipt.receipt_id} · Leaf Index #{receipt.leaf_index}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isVerified ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                VERIFIED
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-red-500/25 text-red-300 border border-red-500/50">
                <AlertOctagon className="w-4 h-4 text-red-400" />
                WARN_PAST_MERKLE_MISMATCH
              </span>
            )}

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              aria-label="Close Merkle Receipt Modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Formula & Zero-Knowledge Privacy Explanation */}
        <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-300 flex items-center justify-between gap-3">
          <div className="space-y-0.5">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <KeyRound className="w-3.5 h-3.5 text-blue-400" />
              Hᵢ = HMAC-SHA256(K_audit, CanonicalJSON(Eᵢ))
            </div>
            <div className="text-[11px] text-slate-400">
              Proves execution inclusion & CGT tax-lot compliance without exposing private sibling
              CDSC Demat BOID balances.
            </div>
          </div>

          <button
            type="button"
            onClick={() => setTamperSimulated((prev) => !prev)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border shrink-0 transition-colors ${
              tamperSimulated
                ? "bg-emerald-600/25 text-emerald-300 border-emerald-500/40"
                : "bg-red-500/15 text-red-300 border-red-500/35 hover:bg-red-500/25"
            }`}
          >
            {tamperSimulated ? "Restore Authentic Payload" : "Simulate 1-Bit Tamper"}
          </button>
        </div>

        {/* Leaf Hash H_i */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Leaf Node HMAC-SHA256 Hash (Hᵢ)
          </label>
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 font-mono-tabular text-xs text-emerald-400 break-all">
            {displayedLeafHash}
          </div>
        </div>

        {/* Sibling Proof Path H_ij = SHA256(H_i || H_j) */}
        <div className="space-y-1.5">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Merkle Inclusion Proof Path ({receipt.proof_path.length} Binary Levels)
          </label>
          <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
            {receipt.proof_path.map((step) => (
              <div
                key={`${step.level}-${step.sibling_hash}`}
                className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 font-mono-tabular text-xs flex flex-col gap-1"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-blue-400 font-semibold">
                    Tree Level L{step.level} · Sibling ({step.position.toUpperCase()})
                  </span>
                  <span className="text-slate-400">Hᵢⱼ = SHA256(H_left ∥ H_right)</span>
                </div>
                <div className="text-slate-200 break-all">{step.sibling_hash}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Anchored Merkle Root R_Merkle */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Lock className="w-3 h-3 text-emerald-400" />
            Immutable Anchored Merkle Root (R_Merkle)
          </label>
          <div
            className={`p-2.5 rounded-lg bg-slate-950 border font-mono-tabular text-xs break-all ${
              isVerified
                ? "border-emerald-500/40 text-emerald-300"
                : "border-red-500/50 text-red-300"
            }`}
          >
            {receipt.merkle_root}
          </div>
        </div>

        {/* Canonical JSON Payload E_i */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Canonical JSON Execution Payload (Eᵢ)
          </label>
          <pre className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 font-mono-tabular text-[11px] text-slate-300 overflow-x-auto max-h-28">
            {receipt.canonical_payload_json}
          </pre>
        </div>
      </div>
    </div>
  );
};
