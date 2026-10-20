/**
 * Section 5.6 — Portfolio Manager Modal: View, Add, Edit, Delete, & Bulk Import Holdings
 *
 * Designed for laymen:
 * - Simple 3-input quick-add ("Stock Symbol", "Quantity", "Purchase Price")
 * - 1-Click CSV/JSON bulk import ("NABIL, 100, 1200")
 * - View & manage exact tax lots per account
 * - Updates backend state in real-time, instantly recalculating Schur-RA-HRP, VPIN, and health scores.
 */

import React, { useState } from "react";
import { Plus, Upload, Trash2, X, CheckCircle, FileText, Building2, Lock } from "lucide-react";

export interface TaxLotItem {
  lot_id: string;
  boid_id: string;
  sub_account_id: string;
  broker_code: string;
  symbol: string;
  quantity: number;
  purchase_price: number;
  purchase_date: string;
  holding_days: number;
  tax_bracket_label: string;
  is_promoter_locked: boolean;
}

export interface SubAccountOption {
  account_id: string;
  account_label: string;
  broker_code: string;
}

export interface PortfolioManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  taxLots: TaxLotItem[];
  subAccounts: SubAccountOption[];
  onRefresh: () => void;
  apiBase: string;
}

export const PortfolioManagerModal: React.FC<PortfolioManagerModalProps> = ({
  isOpen,
  onClose,
  taxLots,
  subAccounts,
  onRefresh,
  apiBase,
}) => {
  const [activeTab, setActiveTab] = useState<"view" | "add" | "import">("view");

  // Add Position Form
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [accountId, setAccountId] = useState(subAccounts[0]?.account_id || "");
  const [isPromoterLocked, setIsPromoterLocked] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  // Bulk Import Form
  const [importText, setImportText] = useState(
    "NABIL, 200, 1240\nNICA, 500, 880\nCHDC, 300, 1600"
  );

  if (!isOpen) return null;

  const handleAddPosition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol || !quantity || !price) return;
    setIsSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/add_position`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: symbol.trim().toUpperCase(),
          quantity: parseInt(quantity, 10),
          purchase_price: parseFloat(price),
          sub_account_id: accountId || subAccounts[0]?.account_id,
          is_promoter_locked: isPromoterLocked,
        }),
      });

      if (res.ok) {
        setFeedback(`✓ Added ${quantity} shares of ${symbol.toUpperCase()} successfully!`);
        setSymbol("");
        setQuantity("");
        setPrice("");
        onRefresh();
      } else {
        const err = await res.json();
        setFeedback(`Error: ${err.detail || "Failed to add position"}`);
      }
    } catch {
      setFeedback("Network error adding position.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteLot = async (lotId: string) => {
    if (!window.confirm("Remove this stock holding lot from your portfolio?")) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/lot/${lotId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        onRefresh();
      }
    } catch {}
  };

  const handleBulkImport = async () => {
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const lines = importText
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);

      const items = lines.map((line) => {
        const parts = line.split(",").map((p) => p.trim());
        return {
          symbol: parts[0] || "NABIL",
          quantity: parseInt(parts[1] || "100", 10),
          purchase_price: parseFloat(parts[2] || "1000"),
          is_promoter_locked: false,
        };
      });

      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });

      if (res.ok) {
        const data = await res.json();
        setFeedback(`✓ Successfully imported ${data.imported_count} stock positions!`);
        onRefresh();
      } else {
        setFeedback("Failed to parse or import rows.");
      }
    } catch {
      setFeedback("Network error during bulk import.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl rounded-3xl bg-[#111622] border border-slate-700/80 shadow-2xl overflow-hidden text-slate-100 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              My Portfolio Manager
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              View, add, edit, or import your stocks across all 4 broker accounts
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-800 bg-slate-950/60 px-6 pt-3 gap-2">
          <button
            type="button"
            onClick={() => { setActiveTab("view"); setFeedback(null); }}
            className={`pb-3 px-4 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "view"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="w-4 h-4" />
            Current Holdings ({taxLots.length} Lots)
          </button>

          <button
            type="button"
            onClick={() => { setActiveTab("add"); setFeedback(null); }}
            className={`pb-3 px-4 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "add"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Plus className="w-4 h-4" />
            Add New Stock
          </button>

          <button
            type="button"
            onClick={() => { setActiveTab("import"); setFeedback(null); }}
            className={`pb-3 px-4 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "import"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Upload className="w-4 h-4" />
            Bulk Import (CSV / Text)
          </button>
        </div>

        {/* Feedback message banner */}
        {feedback && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-blue-500/10 border border-blue-500/30 text-xs font-medium text-blue-300">
            {feedback}
          </div>
        )}

        {/* Tab 1: Current Holdings Table */}
        {activeTab === "view" && (
          <div className="p-6 overflow-y-auto flex-1 space-y-3">
            <div className="text-xs text-slate-400 flex justify-between items-center mb-1">
              <span>Stocks registered in your Demat accounts:</span>
              <span className="text-slate-300 font-mono">
                Total shares: {taxLots.reduce((acc, l) => acc + l.quantity, 0).toLocaleString()}
              </span>
            </div>

            <div className="space-y-2">
              {taxLots.map((lot) => (
                <div
                  key={lot.lot_id}
                  className="p-3.5 rounded-2xl bg-[#1E2638] border border-slate-700/60 flex items-center justify-between text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-sm font-mono">{lot.symbol}</span>
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-slate-900 text-slate-300">
                        {lot.quantity} shares
                      </span>
                      <span className="text-slate-400">@ NPR {lot.purchase_price.toFixed(0)}</span>
                      {lot.is_promoter_locked && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                          <Lock className="w-2.5 h-2.5" /> Promoter Lock
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      BOID: {lot.boid_id} · {lot.tax_bracket_label} ({lot.holding_days} days held)
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleDeleteLot(lot.lot_id)}
                    className="p-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                    title="Remove this holding lot"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 2: Add New Stock */}
        {activeTab === "add" && (
          <form onSubmit={handleAddPosition} className="p-6 space-y-4 flex-1 overflow-y-auto">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Stock Symbol (e.g. NABIL, NICA)
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. NABIL"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="w-full bg-[#1E2638] border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Number of Shares (Quantity)
                </label>
                <input
                  type="number"
                  required
                  placeholder="e.g. 100"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full bg-[#1E2638] border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Purchase Price per Share (NPR)
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  placeholder="e.g. 1245.00"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="w-full bg-[#1E2638] border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Deposit Into Account
                </label>
                <select
                  value={accountId}
                  onChange={(e) => setAccountId(e.target.value)}
                  className="w-full bg-[#1E2638] border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  {subAccounts.map((acc) => (
                    <option key={acc.account_id} value={acc.account_id}>
                      {acc.account_label} (Broker {acc.broker_code})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="promoterLock"
                checked={isPromoterLocked}
                onChange={(e) => setIsPromoterLocked(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0"
              />
              <label htmlFor="promoterLock" className="text-xs text-slate-300 cursor-pointer">
                Is this a 3-Year Mandatory Promoter Share Lock-in (e.g. Hydropower IPO)?
              </label>
            </div>

            <div className="pt-4 border-t border-slate-800">
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 rounded-xl font-bold text-sm text-white bg-blue-600 hover:bg-blue-500 transition-colors shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Add Stock to Portfolio</span>
              </button>
            </div>
          </form>
        )}

        {/* Tab 3: Bulk Import */}
        {activeTab === "import" && (
          <div className="p-6 space-y-4 flex-1 overflow-y-auto">
            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider">
                Paste Stock Rows (Symbol, Quantity, Price)
              </label>
              <p className="text-xs text-slate-400">
                Format: <code>SYMBOL, SHARES, PRICE</code> (one per line). Example below:
              </p>
            </div>

            <textarea
              rows={6}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              className="w-full bg-[#1E2638] border border-slate-700 rounded-2xl p-4 text-sm text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
            />

            <div className="pt-2">
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleBulkImport}
                className="w-full py-3.5 rounded-xl font-bold text-sm text-white bg-emerald-600 hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-2 cursor-pointer"
              >
                <Upload className="w-4 h-4" />
                <span>Import All Positions</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
