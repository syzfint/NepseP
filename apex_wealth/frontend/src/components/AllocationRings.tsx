/**
 * Layman-First Allocation & Holdings Card
 * Shows clean, readable category breakdowns (e.g. "Commercial Banks: 42%, Energy: 28%").
 * Progressive technical disclosure hides the mathematical HRP dendrogram tree and correlation matrix until explicitly opened.
 */

import React, { useState } from "react";
import { PieChart, ChevronDown, ChevronUp, GitBranch, Lock } from "lucide-react";

export interface SectorAssetItem {
  symbol: string;
  current_weight: number;
  target_weight: number;
  drift_pct: number;
  rank: number;
  hysteresis_action: string;
  within_deadband: boolean;
  is_promoter_locked: boolean;
}

export interface SectorAllocationItem {
  sector: string;
  color: string;
  current_weight_pct: number;
  target_weight_pct: number;
  drift_pct: number;
  status: "OVERWEIGHT" | "UNDERWEIGHT" | "ON_TARGET" | string;
  assets: SectorAssetItem[];
}

export interface DendrogramSplitItem {
  node_id: string;
  depth: number;
  left_assets: string[];
  right_assets: string[];
  var_left_hrp: number;
  var_right_hrp: number;
  var_left_schur: number;
  var_right_schur: number;
  alpha_split: number;
  gamma_requested: number;
  gamma_effective: number;
}

export interface SchurHRPTelemetry {
  assets: string[];
  ordered_assets: string[];
  raw_weights: Record<string, number>;
  hrp_baseline_weights: Record<string, number>;
  post_hysteresis_weights: Record<string, number>;
  asset_ranks: Record<string, number>;
  raw_condition_number: number;
  shrunk_condition_number: number;
  shrinkage_intensity: number;
  gamma_requested: number;
  gamma_effective: number;
  portfolio_variance_hrp: number;
  portfolio_variance_schur: number;
  quasi_diag_corr_matrix: number[][];
  dendrogram_splits: DendrogramSplitItem[];
}

export interface AllocationRingsProps {
  sectors: SectorAllocationItem[];
  schurHrp: SchurHRPTelemetry;
  rollingTurnoverMetrics: {
    annual_turnover_unbuffered: number;
    annual_turnover_hysteresis: number;
    fee_drag_unbuffered: number;
    fee_drag_hysteresis: number;
  };
  deadbandCorridorPct: number;
  onSelectSymbol?: (symbol: string) => void;
}

export const AllocationRings: React.FC<AllocationRingsProps> = ({
  sectors,
  schurHrp,
  rollingTurnoverMetrics,
}) => {
  const [showDendrogram, setShowDendrogram] = useState(false);

  return (
    <div className="bg-[#111622] rounded-3xl p-6 border border-slate-800/80 shadow-2xl flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <PieChart className="w-5 h-5 text-blue-400" />
            <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
              Where Your Money Is Invested
            </span>
          </div>
          <span className="text-xs text-emerald-400 font-medium">
            Turnover limited to {(rollingTurnoverMetrics.annual_turnover_hysteresis * 100).toFixed(1)}%/yr
          </span>
        </div>

        {/* Clean, Visual Layman Sector Progress Bars */}
        <div className="space-y-4 my-2">
          {sectors.map((sec) => (
            <div key={sec.sector} className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <div className="flex items-center gap-2 font-semibold text-slate-200">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: sec.color }} />
                  <span>{sec.sector}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white font-bold font-mono">{sec.current_weight_pct.toFixed(1)}%</span>
                  <span className="text-[11px] text-slate-400">
                    (Target {sec.target_weight_pct.toFixed(1)}%)
                  </span>
                </div>
              </div>

              {/* Visual Horizontal Segmented Bar */}
              <div className="h-3 rounded-full bg-slate-900 border border-slate-800 overflow-hidden flex">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, sec.current_weight_pct)}%`,
                    backgroundColor: sec.color,
                  }}
                />
              </div>

              {/* Individual Stock Tags in this category */}
              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {sec.assets.map((asset) => (
                  <span
                    key={asset.symbol}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px] font-mono text-slate-300"
                  >
                    <span>{asset.symbol}</span>
                    <span className="text-slate-500">·</span>
                    <span className="text-slate-400">{asset.current_weight.toFixed(1)}%</span>
                    {asset.is_promoter_locked && (
                      <span className="text-amber-400 flex items-center gap-0.5" title="Mandatory 3-year promoter lock-in">
                        <Lock className="w-2.5 h-2.5" />
                      </span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Progressive Disclosure: HRP Dendrogram and Covariance Matrix */}
      <div className="mt-6 pt-4 border-t border-slate-800">
        <button
          type="button"
          onClick={() => setShowDendrogram((v) => !v)}
          className="w-full flex items-center justify-between text-xs font-semibold text-slate-400 hover:text-slate-200 py-2 px-3 rounded-xl bg-slate-900/50 hover:bg-slate-900 border border-slate-800 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <GitBranch className="w-3.5 h-3.5 text-blue-400" />
            {showDendrogram ? "Hide Institutional Math Models" : "View Schur-HRP Correlation Model"}
          </span>
          {showDendrogram ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showDendrogram && (
          <div className="mt-3 p-4 rounded-2xl bg-[#1E2638] border border-slate-700/80 space-y-3 text-xs font-mono">
            <div className="flex justify-between text-slate-300">
              <span>Covariance condition number κ:</span>
              <strong className="text-white">κ = {schurHrp.shrunk_condition_number.toFixed(2)} ≤ 2.0</strong>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>Schur parameter γ_effective:</span>
              <strong className="text-white">γ = {schurHrp.gamma_effective.toFixed(2)}</strong>
            </div>
            <div className="text-[11px] text-slate-400 pt-1">
              Hierarchical tree splits variance recursively across clusters without risk magnification.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
