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
import {
  Plus,
  Upload,
  Trash2,
  X,
  CheckCircle,
  FileText,
  Building2,
  Lock,
  Download,
  FileSpreadsheet,
  AlertCircle,
} from "lucide-react";

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

  // Bulk Import Form & Local File Upload State
  const [importText, setImportText] = useState("");
  const [selectedModalLotIds, setSelectedModalLotIds] = useState<string[]>([]);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploadedFileBase64, setUploadedFileBase64] = useState<string | null>(null);
  const [parsedPreviewItems, setParsedPreviewItems] = useState<any[]>([]);
  const [detectedFormat, setDetectedFormat] = useState<string | null>(null);
  const [isParsingFile, setIsParsingFile] = useState(false);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  if (!isOpen) return null;

  const toggleModalLotSelection = (lotId: string) => {
    setSelectedModalLotIds((prev) =>
      prev.includes(lotId) ? prev.filter((id) => id !== lotId) : [...prev, lotId]
    );
  };

  const toggleSelectAllModalLots = () => {
    const allIds = taxLots.map((l) => l.lot_id);
    const allSelected = allIds.length > 0 && allIds.every((id) => selectedModalLotIds.includes(id));
    setSelectedModalLotIds(allSelected ? [] : allIds);
  };

  const handleModalBatchRemove = async () => {
    if (selectedModalLotIds.length === 0) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/batch_remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lot_ids: selectedModalLotIds,
          clear_all: false,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setFeedback(`✓ Removed ${data.removed_count} selected stock lots!`);
        setSelectedModalLotIds([]);
        onRefresh();
      }
    } catch {
      setFeedback("Network error removing selected lots.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleModalClearAll = async () => {
    if (!window.confirm("Wipe all holdings and reset vault back to 0?")) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/clear_all`, {
        method: "POST",
      });
      if (res.ok) {
        setFeedback("✓ All holdings wiped. Vault is now at 0.");
        setSelectedModalLotIds([]);
        onRefresh();
      }
    } catch {
      setFeedback("Network error clearing holdings.");
    } finally {
      setIsSubmitting(false);
    }
  };

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
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/lot/${lotId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSelectedModalLotIds((prev) => prev.filter((id) => id !== lotId));
        onRefresh();
      }
    } catch {}
  };

  const handleBulkImport = async () => {
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const lines = importText
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean);

      if (lines.length === 0) {
        setFeedback("Please paste at least one line (e.g. NABIL, 500, 485).");
        setIsSubmitting(false);
        return;
      }

      const items = lines
        .map((line) => {
          const parts = line
            .split(/[,\t;|]+/)
            .map((p) => p.trim())
            .filter(Boolean);
          return {
            symbol: (parts[0] || "").toUpperCase(),
            quantity: parseInt(parts[1] || "0", 10),
            purchase_price: parseFloat(parts[2] || "0"),
            ltp: parts[3] ? parseFloat(parts[3]) : null,
            holding_days: parts[4] ? parseInt(parts[4], 10) : 180,
            sub_account_id: parts[5] || accountId || subAccounts[0]?.account_id,
            is_promoter_locked: false,
          };
        })
        .filter((it) => it.symbol && it.quantity > 0 && it.purchase_price > 0);

      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/batch_add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });

      if (res.ok) {
        const data = await res.json();
        setFeedback(`✓ Successfully imported ${data.added_count} stock positions!`);
        setImportText("");
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

  const handleFileSelected = (file: File) => {
    if (!file) return;
    setIsParsingFile(true);
    setFeedback(null);
    setUploadedFileName(file.name);

    const reader = new FileReader();
    reader.onload = async () => {
      const base64Data = (reader.result as string) || "";
      setUploadedFileBase64(base64Data);
      try {
        const res = await fetch(`${apiBase}/api/v1/pms/portfolio/upload_local_file`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: file.name,
            content_base64: base64Data,
            default_sub_account_id: accountId || subAccounts[0]?.account_id || "Personal",
            auto_commit: false,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          setParsedPreviewItems(data.items || []);
          setDetectedFormat(data.detected_format || file.name);
          setFeedback(
            `✓ Parsed ${data.count} holdings from "${file.name}" (${data.detected_format}). Review below before importing.`
          );
        } else {
          setFeedback(`Error parsing file: ${data.detail || "Invalid format"}`);
          setParsedPreviewItems([]);
        }
      } catch {
        setFeedback("Network error connecting to file parsing engine.");
      } finally {
        setIsParsingFile(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleCommitUploadedFile = async () => {
    if (!uploadedFileName || !uploadedFileBase64 || parsedPreviewItems.length === 0) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/upload_local_file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: uploadedFileName,
          content_base64: uploadedFileBase64,
          default_sub_account_id: accountId || subAccounts[0]?.account_id || "Personal",
          auto_commit: true,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setFeedback(
          `✓ Successfully imported ${data.imported_count} positions from "${uploadedFileName}"!`
        );
        setUploadedFileName(null);
        setUploadedFileBase64(null);
        setParsedPreviewItems([]);
        setDetectedFormat(null);
        onRefresh();
      } else {
        setFeedback(`Import failed: ${data.detail || "Unknown error"}`);
      }
    } catch {
      setFeedback("Network error during file import commit.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownloadSampleCsv = () => {
    const csvContent =
      "Symbol,Quantity,Purchase Price,LTP,Holding Days,Sub Account,Promoter Locked\n" +
      "NABIL,250,520,547,420,Personal,false\n" +
      "NICA,180,310,320.9,180,Family,false\n" +
      "CHDC,50,2250,2329,90,Personal,false\n" +
      "UPPER,300,185,193,500,Corporate,false\n";
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "sample_nepse_portfolio.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleExportCurrentCsv = () => {
    window.open(`${apiBase}/api/v1/pms/portfolio/export_csv`, "_blank");
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
              My Portfolio Manager (Batch Add & Remove)
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              View, batch remove, add, or bulk import your stocks across all 4 broker accounts
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-800 bg-slate-950/60 px-6 pt-3 gap-2">
          <button
            type="button"
            onClick={() => {
              setActiveTab("view");
              setFeedback(null);
            }}
            className={`pb-3 px-4 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 cursor-pointer ${
              activeTab === "view"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="w-4 h-4" />
            Current Holdings & Batch Remove ({taxLots.length} Lots)
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab("add");
              setFeedback(null);
            }}
            className={`pb-3 px-4 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 cursor-pointer ${
              activeTab === "add"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Plus className="w-4 h-4" />
            Add Single Stock
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab("import");
              setFeedback(null);
            }}
            className={`pb-3 px-4 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 cursor-pointer ${
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

        {/* Tab 1: Current Holdings Table & Batch Remove */}
        {activeTab === "view" && (
          <div className="p-6 overflow-y-auto flex-1 space-y-3">
            <div className="text-xs text-slate-400 flex flex-wrap justify-between items-center gap-2 mb-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={toggleSelectAllModalLots}
                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold cursor-pointer"
                >
                  {taxLots.length > 0 && selectedModalLotIds.length === taxLots.length
                    ? "Deselect All"
                    : `Select All (${taxLots.length})`}
                </button>
                {selectedModalLotIds.length > 0 && (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={handleModalBatchRemove}
                    className="px-3 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold cursor-pointer"
                  >
                    Delete Selected ({selectedModalLotIds.length})
                  </button>
                )}
                {taxLots.length > 0 && (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={handleModalClearAll}
                    className="px-2.5 py-1 rounded-lg bg-rose-500/15 hover:bg-rose-600 hover:text-white text-rose-400 border border-rose-500/30 text-xs font-bold cursor-pointer"
                  >
                    Wipe All Holdings
                  </button>
                )}
              </div>
              <span className="text-slate-300 font-mono">
                Total shares: {taxLots.reduce((acc, l) => acc + l.quantity, 0).toLocaleString()}
              </span>
            </div>

            {taxLots.length === 0 ? (
              <div className="p-8 rounded-2xl bg-[#1E2638]/50 border border-slate-800 text-center space-y-2">
                <div className="text-sm font-bold text-slate-200">
                  0 Stock Holdings in Portfolio
                </div>
                <p className="text-xs text-slate-400">
                  Your portfolio is completely clean. Switch to the{" "}
                  <strong>Bulk Import (CSV / Text)</strong> tab or use the{" "}
                  <strong>Batch Add Mode</strong> spreadsheet on the main grid to feed your holdings.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {taxLots.map((lot) => {
                  const isChecked = selectedModalLotIds.includes(lot.lot_id);
                  return (
                    <div
                      key={lot.lot_id}
                      className={`p-3.5 rounded-2xl border flex items-center justify-between text-xs ${
                        isChecked
                          ? "bg-rose-500/10 border-rose-500/40"
                          : "bg-[#1E2638] border-slate-700/60"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleModalLotSelection(lot.lot_id)}
                          className="w-4 h-4 accent-rose-600 cursor-pointer"
                        />
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white text-sm font-mono">
                              {lot.symbol}
                            </span>
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-slate-900 text-slate-300">
                              {lot.quantity} shares
                            </span>
                            <span className="text-slate-400">
                              @ NPR {lot.purchase_price.toFixed(0)}
                            </span>
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
                      </div>

                      <button
                        type="button"
                        onClick={() => handleDeleteLot(lot.lot_id)}
                        className="p-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors cursor-pointer"
                        title="Remove this holding lot"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
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

        {/* Tab 3: Local File Upload & Bulk Import */}
        {activeTab === "import" && (
          <div className="p-6 space-y-5 flex-1 overflow-y-auto">
            {/* Top Toolbar: Template & Export */}
            <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-2xl bg-[#182030] border border-slate-800">
              <div className="text-xs text-slate-300 font-semibold flex items-center gap-1.5">
                <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                <span>Import from your local computer (.csv, .xlsx, .xls, .tsv, .json)</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDownloadSampleCsv}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 inline-flex items-center gap-1.5 cursor-pointer transition-colors"
                >
                  <Download className="w-3.5 h-3.5 text-blue-400" />
                  <span>Download Sample CSV</span>
                </button>
                <button
                  type="button"
                  onClick={handleExportCurrentCsv}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 inline-flex items-center gap-1.5 cursor-pointer transition-colors"
                >
                  <Download className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Export Portfolio CSV</span>
                </button>
              </div>
            </div>

            {/* Local Device File Dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDraggingOver(true);
              }}
              onDragLeave={() => setIsDraggingOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDraggingOver(false);
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  handleFileSelected(e.dataTransfer.files[0]);
                }
              }}
              className={`p-6 rounded-2xl border-2 border-dashed transition-all text-center space-y-3 ${
                isDraggingOver
                  ? "border-emerald-500 bg-emerald-500/10 scale-[1.01]"
                  : "border-slate-700 bg-[#161D2B] hover:border-slate-500"
              }`}
            >
              <div className="w-12 h-12 mx-auto rounded-xl bg-blue-500/15 text-blue-400 flex items-center justify-center">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-bold text-white">
                  Drag and drop your portfolio file here
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  Supports MeroShare exports, TMS downloads, and Excel spreadsheets (.csv, .xlsx, .xls, .tsv, .json)
                </p>
              </div>
              <label className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold cursor-pointer shadow-lg transition-transform hover:scale-105">
                <FileSpreadsheet className="w-4 h-4" />
                <span>Browse Local File</span>
                <input
                  type="file"
                  accept=".csv,.tsv,.txt,.json,.xlsx,.xls"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileSelected(e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />
              </label>
              {isParsingFile && (
                <div className="text-xs text-blue-400 animate-pulse font-semibold">
                  Parsing and verifying closing prices via Strict Price Integrity Engine...
                </div>
              )}
            </div>

            {/* Interactive Preview Table for Parsed File */}
            {parsedPreviewItems.length > 0 && (
              <div className="p-4 rounded-2xl bg-[#161D2B] border border-slate-700 space-y-3 font-mono-tabular">
                <div className="flex items-center justify-between border-b border-slate-700/80 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-emerald-400 uppercase">
                      ✓ Previewing {parsedPreviewItems.length} Holdings
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-sans">
                      {detectedFormat || uploadedFileName}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleCommitUploadedFile}
                    disabled={isSubmitting}
                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-extrabold cursor-pointer shadow-md inline-flex items-center gap-1.5 transition-all"
                  >
                    <Upload className="w-4 h-4" />
                    <span>{isSubmitting ? "Importing..." : `Commit All ${parsedPreviewItems.length} Holdings Now`}</span>
                  </button>
                </div>

                <div className="max-h-56 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] font-sans text-slate-400 uppercase">
                        <th className="py-1.5">Symbol</th>
                        <th className="py-1.5 text-right">Shares</th>
                        <th className="py-1.5 text-right">WACC / Cost</th>
                        <th className="py-1.5 text-right">Closing LTP</th>
                        <th className="py-1.5">Provenance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {parsedPreviewItems.slice(0, 30).map((item, idx) => (
                        <tr key={`${item.symbol}-${idx}`} className="hover:bg-slate-800/40">
                          <td className="py-2 font-bold text-blue-400">{item.symbol}</td>
                          <td className="py-2 text-right">{item.quantity}</td>
                          <td className="py-2 text-right">
                            NPR {item.purchase_price}
                            {item.buy_price_note && (
                              <div className="text-[9px] text-amber-400 font-sans truncate max-w-[120px]">
                                {item.buy_price_note}
                              </div>
                            )}
                          </td>
                          <td className="py-2 text-right font-bold text-emerald-400">
                            NPR {item.resolved_ltp || item.ltp || "—"}
                          </td>
                          <td className="py-2 text-[10px] font-sans text-slate-400 truncate max-w-[160px]">
                            {item.ltp_source_detail || item.ltp_source_type || "Verified Close"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Quick Text / Manual Paste Fallback */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <div className="space-y-0.5">
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Or Paste Text Rows Directly (Symbol, Shares, Price)
                </label>
                <p className="text-xs text-slate-400">
                  Format: <code>SYMBOL, SHARES, PRICE</code> (one per line). Example: <code>NABIL, 500, 485</code>
                </p>
              </div>

              <textarea
                rows={4}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder="NABIL, 200, 520&#10;NICA, 150, 310"
                className="w-full bg-[#1E2638] border border-slate-700 rounded-2xl p-3.5 text-sm text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
              />

              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleBulkImport}
                className="w-full py-3 rounded-xl font-bold text-xs text-white bg-blue-600 hover:bg-blue-500 transition-colors shadow-md flex items-center justify-center gap-2 cursor-pointer"
              >
                <Upload className="w-4 h-4" />
                <span>Import Pasted Rows</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
