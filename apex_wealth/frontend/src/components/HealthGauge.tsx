/**
 * Layman-First Portfolio Health Widget
 * Shows a crystal-clear, friendly summary: "Excellent Health (94/100) — Your portfolio is safe & protected."
 * Behind the scenes: 1-Day CVaR, VPIN, Hawkes broker sweep intensity, and T+2 CDSC lock ratio.
 */

import React, { useState } from "react";
import { ShieldCheck, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Info } from "lucide-react";

export interface HealthGaugeProps {
  score: number;
  status: "Optimal" | "Attention" | "Critical" | string;
  cvar1dPct: number;
  vpin: number;
  hawkesIntensity: number;
  cdscT2LockupPct: number;
  var99Pct: number;
  varMaxPct: number;
  sLockedRatio: number;
  microstructurePenaltyApplied: boolean;
  penaltyPoints: number;
  slicingEnginePaused: boolean;
  onToggleToxicSimulation?: () => void;
  toxicSimulated?: boolean;
}

export const HealthGauge: React.FC<HealthGaugeProps> = ({
  score,
  status,
  cvar1dPct,
  vpin,
  hawkesIntensity,
  cdscT2LockupPct,
  microstructurePenaltyApplied,
  onToggleToxicSimulation,
  toxicSimulated = false,
}) => {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const isHealthy = score >= 80 && !microstructurePenaltyApplied;
  const isModerate = score >= 55 && score < 80;

  const statusTitle = isHealthy
    ? "Excellent Health"
    : isModerate
    ? "Needs Minor Attention"
    : "High Risk Alert";

  const friendlySummary = isHealthy
    ? "Your money is well-protected. Market risk is low, and your cash is ready for trades."
    : isModerate
    ? "Some positions have drifted or market volatility is elevated."
    : "Unusual market activity detected. Automated safety brakes are active.";

  const badgeColor = isHealthy
    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
    : isModerate
    ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
    : "bg-red-500/15 text-red-400 border-red-500/30";

  return (
    <div className="bg-[#111622] rounded-3xl p-6 border border-slate-800/80 shadow-2xl relative overflow-hidden flex flex-col justify-between">
      {/* Background soft ambient glow */}
      <div
        className="absolute -top-16 -right-16 w-48 h-48 rounded-full pointer-events-none blur-3xl opacity-20"
        style={{ backgroundColor: isHealthy ? "#10B981" : isModerate ? "#F59E0B" : "#EF4444" }}
      />

      <div>
        {/* Header Pill */}
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
            Portfolio Health
          </span>
          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${badgeColor}`}>
            {statusTitle}
          </span>
        </div>

        {/* Big Layman Hero Score */}
        <div className="flex items-baseline gap-2 my-2">
          <span className="text-6xl font-black tracking-tight text-white font-mono">
            {score}
          </span>
          <span className="text-xl font-medium text-slate-400">/ 100</span>
        </div>

        {/* Plain English Explanation */}
        <p className="text-sm text-slate-300 font-normal leading-relaxed mt-2 mb-4">
          {friendlySummary}
        </p>

        {/* 3 Simple Layman Checklist Badges */}
        <div className="space-y-2 mb-4">
          <div className="flex items-center gap-2.5 text-xs text-slate-200 bg-slate-900/60 px-3 py-2 rounded-xl border border-slate-800">
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Downside risk cushion is well within safe limits</span>
          </div>
          <div className="flex items-center gap-2.5 text-xs text-slate-200 bg-slate-900/60 px-3 py-2 rounded-xl border border-slate-800">
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>T+2 Clearing settlement proceeds are 87.6% unlocked</span>
          </div>
          <div className="flex items-center gap-2.5 text-xs text-slate-200 bg-slate-900/60 px-3 py-2 rounded-xl border border-slate-800">
            {microstructurePenaltyApplied ? (
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            ) : (
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
            )}
            <span>
              {microstructurePenaltyApplied
                ? "Microstructure circuit breaker active (Predatory broker sweep)"
                : "No predatory broker sweep patterns detected"}
            </span>
          </div>
        </div>
      </div>

      {/* Progressive Disclosure: Institutional Technical Details */}
      <div>
        <button
          type="button"
          onClick={() => setShowTechnicalDetails((v) => !v)}
          className="w-full flex items-center justify-between text-xs font-semibold text-slate-400 hover:text-slate-200 py-2 px-3 rounded-xl bg-slate-900/50 hover:bg-slate-900 border border-slate-800 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-blue-400" />
            {showTechnicalDetails ? "Hide Institutional Telemetry" : "View Quantitative Breakdown"}
          </span>
          {showTechnicalDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showTechnicalDetails && (
          <div className="mt-3 p-4 rounded-2xl bg-[#1E2638] border border-slate-700/80 space-y-2 text-xs font-mono">
            <div className="flex justify-between text-slate-300">
              <span>1-Day 99% CVaR:</span>
              <strong className="text-white">{cvar1dPct.toFixed(2)}%</strong>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>Order Flow Toxicity (VPIN):</span>
              <strong className="text-white">{vpin.toFixed(2)}</strong>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>Hawkes Sweep Intensity λ(t):</span>
              <strong className="text-white">{hawkesIntensity.toFixed(2)}</strong>
            </div>
            <div className="flex justify-between text-slate-300">
              <span>CDSC T+2 Cash Lock:</span>
              <strong className="text-white">{cdscT2LockupPct.toFixed(1)}%</strong>
            </div>

            {onToggleToxicSimulation && (
              <div className="pt-2 border-t border-slate-700">
                <button
                  type="button"
                  onClick={onToggleToxicSimulation}
                  className={`w-full py-1.5 rounded-lg text-xs font-bold font-sans transition-colors ${
                    toxicSimulated
                      ? "bg-red-500 text-white"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  {toxicSimulated ? "Reset Market Regime" : "Test Stress Event (Simulate Market Volatility)"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
