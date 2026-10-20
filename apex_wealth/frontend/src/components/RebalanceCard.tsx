/**
 * Layman-First "1-Tap Smart Rebalance" Card
 * Plain English: "Your portfolio has drifted slightly (+3.2%). Click once to rebalance 3 stocks across your 4 accounts."
 * Prominently shows tax savings: "Saves NPR 28,450 in taxes".
 * Progressive technical disclosure hides LOB cap and TWAP details until clicked.
 */

import React, { useState } from "react";
import { ArrowRight, CheckCircle2, ChevronDown, ChevronUp, Layers, Sparkles, TrendingUp, PiggyBank } from "lucide-react";

export interface AccountAllocationItem {
  sub_account_id: string;
  account_label: string;
  broker_code: string;
  tms_client_code: string;
  boid_id: string;
  available_equity: number;
  equity_share_ratio: number;
  allocated_quantity: number;
  notional_npr: number;
}

export interface ChildSliceItem {
  child_order_id: string;
  parent_order_id: string;
  slice_index: number;
  account_label: string;
  broker_code: string;
  symbol: string;
  side: string;
  quantity: number;
  execution_price: number;
  schedule_type: string;
  scheduled_offset_sec: number;
  top3_lob_depth: number;
  lob_depth_cap_qty: number;
  lob_consumption_pct: number;
  estimated_impact_bps: number;
  tax_bracket: string;
}

export interface TaxLotAllocationItem {
  lot_id: string;
  boid_id: string;
  broker_code: string;
  symbol: string;
  allocated_quantity: number;
  purchase_price: number;
  execution_price: number;
  holding_days: number;
  priority_tier: number;
  priority_label: string;
  tax_bracket_label: string;
  realized_pnl: number;
  realized_cgt: number;
  tax_savings_vs_naive_stcgt: number;
}

export interface ParentExecutionPlanItem {
  parent_order_id: string;
  symbol: string;
  side: string;
  current_weight: number;
  target_weight: number;
  weight_delta: number;
  decision_price: number;
  total_parent_quantity: number;
  total_notional_npr: number;
  execution_profile: string;
  estimated_market_impact_bps: number;
  account_allocations: AccountAllocationItem[];
  child_slices: ChildSliceItem[];
  tax_lot_allocations: TaxLotAllocationItem[];
}

export interface RebalanceCardProps {
  laymanCtaCopy: string;
  estimatedTaxSavingsNpr: number;
  projectedHealthScoreDelta: number;
  postTradeHealthScore: number;
  executionPlans: ParentExecutionPlanItem[];
  rebalanceExecutedCount: number;
  isExecuting?: boolean;
  onExecuteRebalance: (profile: "VWAP" | "TWAP") => void;
}

export const RebalanceCard: React.FC<RebalanceCardProps> = ({
  laymanCtaCopy,
  estimatedTaxSavingsNpr,
  projectedHealthScoreDelta,
  postTradeHealthScore,
  executionPlans,
  rebalanceExecutedCount,
  isExecuting = false,
  onExecuteRebalance,
}) => {
  const [showTechnicalBreakdown, setShowTechnicalBreakdown] = useState(false);

  return (
    <div className="bg-[#111622] rounded-3xl p-6 border border-blue-500/30 shadow-2xl relative overflow-hidden flex flex-col justify-between">
      {/* Background soft ambient blue glow */}
      <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full pointer-events-none blur-3xl opacity-20 bg-blue-500" />

      <div>
        {/* Header Pill */}
        <div className="flex items-center justify-between mb-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
            <Sparkles className="w-3.5 h-3.5" />
            Smart Optimization
          </span>
          <span className="text-xs text-slate-400">Automated across 4 accounts</span>
        </div>

        {/* Big Layman Headline */}
        <h3 className="text-xl font-bold text-white leading-snug mb-2">
          Keep your portfolio perfectly balanced
        </h3>
        <p className="text-sm text-slate-300 font-normal leading-relaxed mb-5">
          {laymanCtaCopy}
        </p>

        {/* 2 Clear Layman Benefit Cards */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/30">
            <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-semibold mb-1">
              <PiggyBank className="w-4 h-4" />
              Tax Savings
            </div>
            <div className="text-xl font-black text-emerald-300 font-mono">
              NPR {estimatedTaxSavingsNpr.toLocaleString("en-IN")}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              5.0% Long-Term tax rate applied
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-blue-950/40 border border-blue-500/30">
            <div className="flex items-center gap-1.5 text-xs text-blue-400 font-semibold mb-1">
              <TrendingUp className="w-4 h-4" />
              Score Boost
            </div>
            <div className="text-xl font-black text-blue-300 font-mono">
              +{projectedHealthScoreDelta} pts
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Improves to {postTradeHealthScore}/100
            </div>
          </div>
        </div>

        {/* Large, Zero-Friction Layman Button */}
        <button
          type="button"
          disabled={isExecuting}
          onClick={() => onExecuteRebalance("VWAP")}
          className="w-full py-4 px-6 rounded-2xl font-bold text-sm text-white bg-blue-600 hover:bg-blue-500 active:scale-[0.99] transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-600/30 cursor-pointer"
        >
          {isExecuting ? (
            <span>Applying smart rebalance across your accounts...</span>
          ) : (
            <>
              <span>Rebalance Portfolio in 1 Tap</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>

        {rebalanceExecutedCount > 0 && (
          <div className="mt-3 px-3 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between text-xs text-emerald-300 font-medium">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              Rebalance #{rebalanceExecutedCount} completed & verified
            </span>
            <span className="font-mono text-[11px]">Audit Proof Anchored</span>
          </div>
        )}
      </div>

      {/* Progressive Disclosure: Technical Order Routing Details */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowTechnicalBreakdown((v) => !v)}
          className="w-full flex items-center justify-between text-xs font-semibold text-slate-400 hover:text-slate-200 py-2 px-3 rounded-xl bg-slate-900/50 hover:bg-slate-900 border border-slate-800 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            {showTechnicalBreakdown ? "Hide Order Slicing Details" : "View Multi-Broker Execution Breakdown"}
          </span>
          {showTechnicalBreakdown ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showTechnicalBreakdown && (
          <div className="mt-3 p-4 rounded-2xl bg-[#1E2638] border border-slate-700/80 space-y-3 text-xs">
            <div className="text-slate-300 font-medium">
              Planned orders (capped at 15% order book volume to prevent slippage):
            </div>
            <div className="space-y-2">
              {executionPlans.map((plan) => (
                <div key={plan.parent_order_id} className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 font-mono">
                  <div className="flex justify-between items-center text-white font-bold">
                    <span>{plan.side} {plan.symbol}</span>
                    <span>{plan.total_parent_quantity} shares @ NPR {plan.decision_price.toFixed(2)}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1 flex justify-between">
                    <span>Broker routes: 4 TMS endpoints</span>
                    <span className="text-emerald-400">Impact: ≤ {plan.estimated_market_impact_bps.toFixed(1)} bps</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
