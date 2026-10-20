/**
 * Layman-First Activity Feed
 * Clean narrative receipts: "Sold 50 shares of NABIL at NPR 1,245 — Locked in 5.0% Long-Term Tax Rate (Saved NPR 1,125)".
 * "Verify Audit Receipt" opens the Merkle cryptographic verification dialog.
 */

import React from "react";
import { CheckCircle2, ShieldCheck, Tag } from "lucide-react";

export interface MerkleStepItem {
  level: number;
  position: "left" | "right" | string;
  sibling_hash: string;
}

export interface MerkleReceiptPayload {
  receipt_id: string;
  leaf_index: number;
  leaf_hash: string;
  merkle_root: string;
  proof_path: MerkleStepItem[];
  canonical_payload_json: string;
  is_verified: boolean;
  algorithm?: string;
}

export interface ActivityFeedItem {
  execution_id: string;
  child_order_id: string;
  symbol: string;
  side: "BUY" | "SELL" | string;
  quantity: number;
  execution_price: number;
  purchase_price: number;
  realized_gain_npr: number;
  tax_bracket: "5.0% LTCGT" | "7.5% STCGT" | string;
  tax_rate: number;
  cgt_paid_npr: number;
  tax_saved_npr: number;
  holding_days: number;
  broker_code: string;
  tms_client_code: string;
  boid_masked: string;
  timestamp: string;
  narrative: string;
  leaf_index: number;
  leaf_hash: string;
  merkle_root: string;
  receipt: MerkleReceiptPayload;
}

export interface TaxActivityFeedProps {
  items: ActivityFeedItem[];
  merkleRoot: string;
  onInspectReceipt: (item: ActivityFeedItem) => void;
}

export const TaxActivityFeed: React.FC<TaxActivityFeedProps> = ({
  items,
  onInspectReceipt,
}) => {
  return (
    <div className="bg-[#111622] rounded-3xl p-6 border border-slate-800/80 shadow-2xl flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
              Recent Activity & Tax Savings
            </span>
          </div>
          <span className="text-xs text-slate-400">Cryptographically Audited</span>
        </div>

        {/* Clean, Human-Friendly Activity Cards */}
        <div className="space-y-3">
          {items.slice(0, 4).map((item) => {
            const isLongTerm = item.tax_bracket.includes("5.0%");
            return (
              <div
                key={item.execution_id}
                className="p-4 rounded-2xl bg-[#1E2638] border border-slate-700/60 hover:border-blue-500/40 transition-colors flex flex-col justify-between"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded-lg text-xs font-bold font-mono ${
                          item.side === "SELL"
                            ? "bg-purple-500/20 text-purple-300"
                            : "bg-blue-500/20 text-blue-300"
                        }`}
                      >
                        {item.side} {item.symbol}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        {item.quantity} shares @ NPR {item.execution_price.toFixed(0)}
                      </span>
                    </div>

                    {/* Friendly plain English sentence */}
                    <p className="text-sm font-medium text-slate-100 leading-snug pt-1">
                      {item.narrative}
                    </p>
                  </div>

                  {/* 1-Click Verify Receipt Button */}
                  <button
                    type="button"
                    onClick={() => onInspectReceipt(item)}
                    className="shrink-0 px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-400 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Verify Proof
                  </button>
                </div>

                {/* Footer Tax Bracket Badge */}
                <div className="mt-3 pt-2.5 border-t border-slate-700/50 flex justify-between items-center text-xs">
                  <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                    <Tag className="w-3 h-3 text-slate-400" />
                    {item.tax_bracket} (Held {item.holding_days} days)
                  </span>
                  <span className="text-emerald-400 font-semibold font-mono text-xs">
                    Saved NPR {item.tax_saved_npr.toLocaleString("en-IN")}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
