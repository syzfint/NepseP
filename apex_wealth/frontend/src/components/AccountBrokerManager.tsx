import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronDown,
  Edit3,
  ExternalLink,
  Layers,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";

export interface SubAccountSummary {
  account_id: string;
  account_type: string;
  account_label: string;
  broker_code: string;
  broker_name?: string;
  tms_client_code: string;
  boid_id: string;
  dp_name?: string;
  cash_balance: number;
  unsettled_cash_locked: number;
  available_cash: number;
  available_equity: number;
}

export interface NepseBrokerEntry {
  broker_no: string;
  broker_name: string;
  tms_url: string;
  total_turnover_npr: number;
  net_amount_npr: number;
  buy_amount_npr: number;
  sell_amount_npr: number;
  total_contracts: number;
  market_share_pct: number;
  net_stance: string;
}

export interface BrokerActivityPayload {
  business_date: string;
  data_source: string;
  is_synthetic: boolean;
  total_contracts: number;
  total_shares_traded: number;
  total_market_turnover_npr: number;
  active_brokers_count: number;
  connected_broker_nos: string[];
  connected_brokers_profiles: any[];
  focused_broker_profile: any;
  top_turnover_brokers: any[];
  top_net_buying_brokers: any[];
  top_net_selling_brokers: any[];
  held_symbols_broker_radar: any[];
  broker_directory: NepseBrokerEntry[];
}

interface AccountBrokerManagerProps {
  subAccounts: SubAccountSummary[];
  apiBase: string;
  executiveLightMode: boolean;
  onRefresh: () => Promise<void> | void;
  onOpenPortfolioManager: () => void;
  cardBg: string;
  subCardBg: string;
  mutedText: string;
  heldSymbols?: string[];
}

export const AccountBrokerManager: React.FC<AccountBrokerManagerProps> = ({
  subAccounts,
  apiBase,
  executiveLightMode,
  onRefresh,
  onOpenPortfolioManager,
  cardBg,
  subCardBg,
  mutedText,
}) => {
  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState<string | null>(null);

  // Form states for creating / editing account
  const [formLabel, setFormLabel] = useState("");
  const [formType, setFormType] = useState("PERSONAL");
  const [formBrokerNo, setFormBrokerNo] = useState("58");
  const [formBoid, setFormBoid] = useState("");
  const [formCash, setFormCash] = useState("0");
  const [formDpName, setFormDpName] = useState("");
  const [brokerSearchQuery, setBrokerSearchQuery] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  // Inline cash balance edit state
  const [inlineEditingCashId, setInlineEditingCashId] = useState<string | null>(null);
  const [inlineCashValue, setInlineCashValue] = useState("");

  // Broker Directory & Activity State
  const [brokerDirectory, setBrokerDirectory] = useState<NepseBrokerEntry[]>([]);
  const [brokerActivity, setBrokerActivity] = useState<BrokerActivityPayload | null>(null);
  const [focusedBrokerNo, setFocusedBrokerNo] = useState<string>("58");
  const [activityTab, setActivityTab] = useState<"connected" | "market" | "portfolio_radar">("connected");
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);

  // Fetch official broker directory
  useEffect(() => {
    fetch(`${apiBase}/api/v1/pms/brokers`)
      .then((res) => res.json())
      .then((data) => {
        if (data.brokers) setBrokerDirectory(data.brokers);
      })
      .catch(() => {});
  }, [apiBase]);

  // Fetch floorsheet broker intelligence
  const fetchBrokerActivity = async (focusNo?: string) => {
    setIsLoadingActivity(true);
    try {
      const targetNo = focusNo || focusedBrokerNo;
      const res = await fetch(
        `${apiBase}/api/v1/pms/broker_activity?focus_broker=${encodeURIComponent(targetNo)}`
      );
      if (res.ok) {
        const data = await res.json();
        setBrokerActivity(data);
        if (data.focused_broker_profile?.broker_no) {
          setFocusedBrokerNo(data.focused_broker_profile.broker_no);
        }
      }
    } catch {
      // offline fallback
    } finally {
      setIsLoadingActivity(false);
    }
  };

  useEffect(() => {
    const initialBroker = subAccounts[0]?.broker_code || "58";
    setFocusedBrokerNo(initialBroker);
    fetchBrokerActivity(initialBroker);
  }, [subAccounts.length, subAccounts[0]?.broker_code]);

  // Filtered brokers for auto-complete dropdown
  const filteredBrokers = useMemo(() => {
    if (!brokerSearchQuery.trim()) return brokerDirectory.slice(0, 12);
    const q = brokerSearchQuery.toLowerCase().trim();
    return brokerDirectory
      .filter(
        (b) =>
          b.broker_no.toLowerCase().includes(q) ||
          b.broker_name.toLowerCase().includes(q)
      )
      .slice(0, 15);
  }, [brokerDirectory, brokerSearchQuery]);

  const selectedBrokerObj = useMemo(() => {
    const cleanNo = formBrokerNo.replace(/\D/g, "");
    return brokerDirectory.find((b) => b.broker_no === cleanNo);
  }, [brokerDirectory, formBrokerNo]);

  // Open Create Account Modal
  const openCreateModal = () => {
    setFormLabel("");
    setFormType("PERSONAL");
    setFormBrokerNo("58");
    setFormBoid("");
    setFormCash("0");
    setFormDpName("");
    setBrokerSearchQuery("");
    setFormError(null);
    setFormSuccess(null);
    setEditingAccountId(null);
    setIsCreateModalOpen(true);
  };

  // Open Edit Account Modal
  const openEditModal = (acc: SubAccountSummary) => {
    setEditingAccountId(acc.account_id);
    setFormLabel(acc.account_label);
    setFormType(acc.account_type);
    setFormBrokerNo(acc.broker_code);
    setFormBoid(acc.boid_id);
    setFormCash(String(acc.cash_balance));
    setFormDpName(acc.dp_name || "");
    setBrokerSearchQuery(acc.broker_code);
    setFormError(null);
    setFormSuccess(null);
    setIsCreateModalOpen(true);
  };

  // Submit Create or Edit Account
  const handleSubmitAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    setFormSuccess(null);

    const cleanBrokerNo = formBrokerNo.replace(/\D/g, "");
    if (!cleanBrokerNo) {
      setFormError("Please enter or select a valid NEPSE Broker Number (e.g. 58).");
      setIsSubmitting(false);
      return;
    }

    try {
      if (editingAccountId) {
        // Update account
        const res = await fetch(`${apiBase}/api/v1/pms/accounts/${editingAccountId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            account_label: formLabel.trim() || undefined,
            account_type: formType,
            broker_no: cleanBrokerNo,
            boid_id: formBoid.trim() || undefined,
            dp_name: formDpName.trim() || undefined,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          setFormError(data.detail || "Failed to update account.");
          return;
        }
        setFormSuccess("✓ Account updated successfully!");
      } else {
        // Create new account
        const res = await fetch(`${apiBase}/api/v1/pms/accounts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            account_label: formLabel.trim() || `Account (TMS #${cleanBrokerNo})`,
            account_type: formType,
            broker_no: cleanBrokerNo,
            boid_id: formBoid.trim() || undefined,
            cash_balance: parseFloat(formCash) || 0,
            dp_name: formDpName.trim() || undefined,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          setFormError(data.detail || "Failed to create account.");
          return;
        }
        setFormSuccess(`✓ Account created & linked to Broker #${cleanBrokerNo}!`);
      }

      await onRefresh();
      fetchBrokerActivity(cleanBrokerNo);
      setTimeout(() => {
        setIsCreateModalOpen(false);
      }, 700);
    } catch {
      setFormError("Network error. Please ensure PMS backend server is running.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Delete Account
  const handleDeleteAccount = async (accId: string, label: string) => {
    if (
      !window.confirm(
        `Are you sure you want to remove account "${label}"? Any stock holdings attached to this account will be pruned.`
      )
    ) {
      return;
    }
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/accounts/${accId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await onRefresh();
        fetchBrokerActivity();
      }
    } catch {
      alert("Failed to delete account.");
    }
  };

  // Save Inline Cash Balance
  const handleSaveInlineCash = async (accId: string) => {
    const val = parseFloat(inlineCashValue);
    if (isNaN(val) || val < 0) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/update_cash`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sub_account_id: accId, cash_balance: val }),
      });
      if (res.ok) {
        setInlineEditingCashId(null);
        await onRefresh();
      }
    } catch {}
  };

  const focusedProfile = brokerActivity?.focused_broker_profile;

  return (
    <div className="space-y-6">
      {/* =====================================================================
          HEADER BAR: TITLE + ADD ACCOUNT + ADD STOCK
         ===================================================================== */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-[#0062A8]" />
            <h2 className="text-base font-extrabold tracking-tight">
              Connected PMS Sub-Accounts &amp; NEPSE Broker Desks
            </h2>
          </div>
          <p className={`text-xs ${mutedText} mt-0.5`}>
            Create your custom trading accounts, apply any NEPSE Broker Number (#1–#101), and
            auto-inspect verified floorsheet broker trading activity.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openCreateModal}
            className="px-4 py-2 rounded-xl bg-[#0062A8] hover:bg-[#00518a] text-white text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-md transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>+ Create Account &amp; Link Broker</span>
          </button>
          <button
            type="button"
            onClick={onOpenPortfolioManager}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-md transition-all"
          >
            <Layers className="w-4 h-4" />
            <span>Add Stock Holding</span>
          </button>
        </div>
      </div>

      {/* =====================================================================
          EMPTY STATE: WHEN 0 SUB-ACCOUNTS EXIST
         ===================================================================== */}
      {subAccounts.length === 0 && (
        <div className={`p-8 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-800 ${cardBg} text-center space-y-4`}>
          <div className="w-14 h-14 mx-auto rounded-2xl bg-blue-500/10 text-blue-600 flex items-center justify-center">
            <Building2 className="w-7 h-7" />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h3 className="text-base font-extrabold">No PMS Client Accounts Created Yet</h3>
            <p className={`text-xs ${mutedText}`}>
              Your portfolio starts with 0 accounts. Create your first sub-account (Personal,
              Family, or Corporate) and enter your NEPSE Broker Number to link your trading desk!
            </p>
          </div>
          <div className="pt-2">
            <button
              type="button"
              onClick={openCreateModal}
              className="px-5 py-2.5 rounded-xl bg-[#0062A8] hover:bg-[#00518a] text-white text-xs font-extrabold inline-flex items-center gap-2 cursor-pointer shadow-lg transition-transform hover:scale-105"
            >
              <Plus className="w-4 h-4" />
              <span>Create Your First Account Now</span>
            </button>
          </div>
        </div>
      )}

      {/* =====================================================================
          ACCOUNTS GRID: CONNECTED SUB-ACCOUNTS
         ===================================================================== */}
      {subAccounts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {subAccounts.map((sub) => {
            const isFocused = focusedBrokerNo === sub.broker_code;
            return (
              <div
                key={sub.account_id}
                className={`p-5 rounded-xl border transition-all ${
                  isFocused
                    ? "border-blue-500 ring-2 ring-blue-500/20 shadow-md"
                    : "border-slate-200 dark:border-slate-800"
                } ${cardBg} space-y-4`}
              >
                {/* Account Header */}
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/15 text-blue-600 uppercase">
                        {sub.account_type} ENTITY
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-600 uppercase flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> BROKER #{sub.broker_code}
                      </span>
                    </div>

                    <h3 className="text-base font-extrabold mt-1">
                      {sub.account_label}
                    </h3>

                    <p className={`text-xs font-mono-tabular ${mutedText} mt-0.5`}>
                      16-Digit BOID:{" "}
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {sub.boid_id}
                      </span>{" "}
                      · TMS Client:{" "}
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {sub.tms_client_code}
                      </span>
                    </p>

                    <div className="text-[11px] text-blue-600 dark:text-blue-400 font-semibold mt-1 flex items-center gap-1.5">
                      <span>
                        Broker #{sub.broker_code}: {sub.broker_name || `NEPSE Broker #${sub.broker_code}`}
                      </span>
                      <a
                        href={`https://tms${sub.broker_code}.nepsetms.com.np`}
                        target="_blank"
                        rel="noreferrer"
                        title="Open NEPSE TMS Portal"
                        className="hover:underline inline-flex items-center gap-0.5 text-[10px]"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>TMS Portal</span>
                      </a>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      title="Inspect this Broker in Floorsheet Activity Radar"
                      onClick={() => {
                        setFocusedBrokerNo(sub.broker_code);
                        fetchBrokerActivity(sub.broker_code);
                      }}
                      className={`p-1.5 rounded-lg border text-xs font-bold flex items-center gap-1 cursor-pointer transition-colors ${
                        isFocused
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-blue-50 dark:hover:bg-blue-900/30"
                      }`}
                    >
                      <Activity className="w-3.5 h-3.5" />
                      <span className="text-[10px]">Radar</span>
                    </button>
                    <button
                      type="button"
                      title="Edit Account / Broker"
                      onClick={() => openEditModal(sub)}
                      className="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs cursor-pointer"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      title="Delete Account"
                      onClick={() => handleDeleteAccount(sub.account_id, sub.account_label)}
                      className="p-1.5 rounded-lg bg-red-100 dark:bg-red-900/30 hover:bg-red-200 text-red-600 dark:text-red-400 text-xs cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Financial KPI Cards */}
                <div className="grid grid-cols-3 gap-3 font-mono-tabular">
                  <div className={`p-3 rounded-lg border ${subCardBg}`}>
                    <div className={`text-[10px] font-sans uppercase ${mutedText}`}>
                      Available Equity
                    </div>
                    <div className="text-sm font-extrabold mt-0.5">
                      NPR {(sub.available_equity / 1_000_000).toFixed(2)}M
                    </div>
                  </div>
                  <div className={`p-3 rounded-lg border ${subCardBg}`}>
                    <div className={`text-[10px] font-sans uppercase ${mutedText}`}>
                      Settled Cash
                    </div>
                    <div className="text-sm font-extrabold text-emerald-600 mt-0.5">
                      NPR {sub.available_cash.toLocaleString("en-IN")}
                    </div>
                  </div>
                  <div className={`p-3 rounded-lg border ${subCardBg}`}>
                    <div className={`text-[10px] font-sans uppercase ${mutedText}`}>
                      T+2 Locked Cash
                    </div>
                    <div className="text-sm font-extrabold text-amber-500 mt-0.5">
                      NPR {sub.unsettled_cash_locked.toLocaleString("en-IN")}
                    </div>
                  </div>
                </div>

                {/* Inline Cash Balance Editor */}
                <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
                  {inlineEditingCashId === sub.account_id ? (
                    <div className="flex items-center gap-2 w-full">
                      <input
                        type="number"
                        value={inlineCashValue}
                        onChange={(e) => setInlineCashValue(e.target.value)}
                        placeholder="New cash balance (NPR)"
                        className={`px-3 py-1.5 rounded-lg border text-xs font-mono-tabular flex-1 ${subCardBg}`}
                      />
                      <button
                        type="button"
                        onClick={() => handleSaveInlineCash(sub.account_id)}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-bold cursor-pointer"
                      >
                        Save Cash
                      </button>
                      <button
                        type="button"
                        onClick={() => setInlineEditingCashId(null)}
                        className="px-2.5 py-1.5 rounded-lg bg-slate-200 dark:bg-slate-800 text-xs font-semibold cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className={`text-xs ${mutedText}`}>
                        Total Cash Ledger: NPR {sub.cash_balance.toLocaleString("en-IN")}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setInlineEditingCashId(sub.account_id);
                          setInlineCashValue(String(sub.cash_balance));
                        }}
                        className="px-3 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-blue-600 hover:text-white text-xs font-bold flex items-center gap-1 cursor-pointer transition-colors"
                      >
                        <Edit3 className="w-3 h-3" /> Edit Cash Balance
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* =====================================================================
          FLOORSHEET BROKER INTELLIGENCE SECTION ("AUTO SEES THAT BROKER & OTHER BROKER ACTIVITIES")
         ===================================================================== */}
      <div className={`p-6 rounded-2xl border ${cardBg} space-y-6 shadow-sm`}>
        {/* Radar Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <h3 className="text-base font-extrabold">
                NEPSE Real Floorsheet Broker Intelligence &amp; Counterparty Radar
              </h3>
            </div>
            <p className={`text-xs ${mutedText} mt-0.5`}>
              Verified floorsheet activity from <strong>2026-10-16</strong> (39,295 real contracts).
              Strictly zero synthetic broker trades.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fetchBrokerActivity(focusedBrokerNo)}
              disabled={isLoadingActivity}
              className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-bold flex items-center gap-1 cursor-pointer"
              title="Refresh Floorsheet Data"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingActivity ? "animate-spin" : ""}`} />
            </button>

            {/* Sub-Tabs */}
            <div className="flex items-center p-1 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-bold">
              <button
                type="button"
                onClick={() => setActivityTab("connected")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  activityTab === "connected"
                    ? "bg-[#0062A8] text-white shadow-sm"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                }`}
              >
                Your Applied Broker (#{focusedBrokerNo})
              </button>
              <button
                type="button"
                onClick={() => setActivityTab("market")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  activityTab === "market"
                    ? "bg-[#0062A8] text-white shadow-sm"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                }`}
              >
                Other Brokers in Market
              </button>
              <button
                type="button"
                onClick={() => setActivityTab("portfolio_radar")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  activityTab === "portfolio_radar"
                    ? "bg-[#0062A8] text-white shadow-sm"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                }`}
              >
                Portfolio Stocks Radar
              </button>
            </div>
          </div>
        </div>

        {/* TAB 1: YOUR APPLIED BROKER INTELLIGENCE */}
        {activityTab === "connected" && (
          <div className="space-y-6">
            {/* Quick Switcher among connected accounts / brokers */}
            {subAccounts.length > 1 && (
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                <span className={`text-xs font-bold ${mutedText}`}>Inspect Connected Broker:</span>
                {subAccounts.map((s) => (
                  <button
                    key={s.account_id}
                    type="button"
                    onClick={() => {
                      setFocusedBrokerNo(s.broker_code);
                      fetchBrokerActivity(s.broker_code);
                    }}
                    className={`px-3 py-1 rounded-lg text-xs font-bold border transition-all cursor-pointer ${
                      focusedBrokerNo === s.broker_code
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700"
                    }`}
                  >
                    Broker #{s.broker_code} ({s.account_label})
                  </button>
                ))}
              </div>
            )}

            {focusedProfile ? (
              <div className="space-y-5">
                {/* 4 Top KPI Cards for the Broker */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono-tabular">
                  <div className={`p-4 rounded-xl border ${subCardBg}`}>
                    <div className={`text-[10px] font-sans uppercase font-bold ${mutedText}`}>
                      Total Turnover (NPR)
                    </div>
                    <div className="text-base font-extrabold mt-1">
                      NPR {(focusedProfile.total_turnover_npr / 1_000_000).toFixed(2)}M
                    </div>
                    <div className="text-[10px] text-blue-600 font-semibold mt-0.5">
                      {focusedProfile.market_share_pct}% NEPSE Market Share
                    </div>
                  </div>

                  <div className={`p-4 rounded-xl border ${subCardBg}`}>
                    <div className={`text-[10px] font-sans uppercase font-bold ${mutedText}`}>
                      Net Flow Stance
                    </div>
                    <div
                      className={`text-sm font-extrabold mt-1 flex items-center gap-1 ${
                        focusedProfile.net_amount_npr >= 0
                          ? "text-emerald-600"
                          : "text-rose-600"
                      }`}
                    >
                      {focusedProfile.net_amount_npr >= 0 ? (
                        <TrendingUp className="w-4 h-4" />
                      ) : (
                        <TrendingDown className="w-4 h-4" />
                      )}
                      <span>
                        {focusedProfile.net_amount_npr >= 0 ? "+" : ""}
                        NPR {(focusedProfile.net_amount_npr / 1_000_000).toFixed(2)}M
                      </span>
                    </div>
                    <div className="text-[10px] font-sans font-bold uppercase mt-0.5 text-slate-500">
                      {focusedProfile.net_stance.replace(/_/g, " ")}
                    </div>
                  </div>

                  <div className={`p-4 rounded-xl border ${subCardBg}`}>
                    <div className={`text-[10px] font-sans uppercase font-bold ${mutedText}`}>
                      Buy vs Sell Breakdown
                    </div>
                    <div className="text-xs font-bold mt-1">
                      <span className="text-emerald-600 font-bold">
                        B: NPR {(focusedProfile.buy_amount_npr / 1_000_000).toFixed(1)}M
                      </span>{" "}
                      /{" "}
                      <span className="text-rose-600 font-bold">
                        S: NPR {(focusedProfile.sell_amount_npr / 1_000_000).toFixed(1)}M
                      </span>
                    </div>
                    <div className="text-[10px] font-sans text-slate-500 mt-0.5">
                      {focusedProfile.buy_ratio_pct}% Buy Bias Ratio
                    </div>
                  </div>

                  <div className={`p-4 rounded-xl border ${subCardBg}`}>
                    <div className={`text-[10px] font-sans uppercase font-bold ${mutedText}`}>
                      Floorsheet Contracts
                    </div>
                    <div className="text-base font-extrabold mt-1">
                      {focusedProfile.total_contracts.toLocaleString("en-IN")}
                    </div>
                    <div className="text-[10px] text-slate-500 font-sans mt-0.5">
                      {focusedProfile.active_symbols_count} Distinct Stocks Traded
                    </div>
                  </div>
                </div>

                {/* 2 Tables: Top Accumulated vs Top Distributed Stocks */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  {/* Top Accumulated Stocks */}
                  <div className={`p-4 rounded-xl border ${subCardBg} space-y-3`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <TrendingUp className="w-4 h-4 text-emerald-600" />
                        <h4 className="text-xs font-extrabold uppercase">
                          Top Accumulated Stocks (Net Inflow)
                        </h4>
                      </div>
                      <span className="text-[10px] font-bold text-emerald-600 uppercase">
                        Broker #{focusedProfile.broker_no}
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono-tabular">
                        <thead>
                          <tr className="border-b border-slate-200 dark:border-slate-800 text-[10px] font-sans text-slate-500 uppercase">
                            <th className="py-1.5 font-bold">Stock</th>
                            <th className="py-1.5 font-bold text-right">Net Qty</th>
                            <th className="py-1.5 font-bold text-right">Net NPR</th>
                            <th className="py-1.5 font-bold text-right">Buy VWAP</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                          {focusedProfile.top_accumulated_stocks?.slice(0, 6).map((item: any) => (
                            <tr key={item.symbol} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                              <td className="py-2">
                                <span className="font-extrabold text-blue-600">{item.symbol}</span>
                                <div className="text-[10px] font-sans text-slate-500 truncate max-w-[120px]">
                                  {item.security_name}
                                </div>
                              </td>
                              <td className="py-2 text-right font-bold text-emerald-600">
                                +{item.net_qty.toLocaleString("en-IN")}
                              </td>
                              <td className="py-2 text-right font-extrabold text-emerald-600">
                                NPR {(item.net_amount_npr / 1000).toFixed(0)}K
                              </td>
                              <td className="py-2 text-right text-slate-600 dark:text-slate-400">
                                {item.vwap_buy > 0 ? `NPR ${item.vwap_buy.toFixed(1)}` : "—"}
                              </td>
                            </tr>
                          ))}
                          {(!focusedProfile.top_accumulated_stocks ||
                            focusedProfile.top_accumulated_stocks.length === 0) && (
                            <tr>
                              <td colSpan={4} className="py-4 text-center text-xs text-slate-400">
                                No net accumulation detected for this broker today.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Top Distributed Stocks */}
                  <div className={`p-4 rounded-xl border ${subCardBg} space-y-3`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <TrendingDown className="w-4 h-4 text-rose-600" />
                        <h4 className="text-xs font-extrabold uppercase">
                          Top Distributed Stocks (Net Outflow)
                        </h4>
                      </div>
                      <span className="text-[10px] font-bold text-rose-600 uppercase">
                        Broker #{focusedProfile.broker_no}
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono-tabular">
                        <thead>
                          <tr className="border-b border-slate-200 dark:border-slate-800 text-[10px] font-sans text-slate-500 uppercase">
                            <th className="py-1.5 font-bold">Stock</th>
                            <th className="py-1.5 font-bold text-right">Net Qty</th>
                            <th className="py-1.5 font-bold text-right">Net NPR</th>
                            <th className="py-1.5 font-bold text-right">Sell VWAP</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                          {focusedProfile.top_distributed_stocks?.slice(0, 6).map((item: any) => (
                            <tr key={item.symbol} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                              <td className="py-2">
                                <span className="font-extrabold text-rose-600">{item.symbol}</span>
                                <div className="text-[10px] font-sans text-slate-500 truncate max-w-[120px]">
                                  {item.security_name}
                                </div>
                              </td>
                              <td className="py-2 text-right font-bold text-rose-600">
                                {item.net_qty.toLocaleString("en-IN")}
                              </td>
                              <td className="py-2 text-right font-extrabold text-rose-600">
                                NPR {(item.net_amount_npr / 1000).toFixed(0)}K
                              </td>
                              <td className="py-2 text-right text-slate-600 dark:text-slate-400">
                                {item.vwap_sell > 0 ? `NPR ${item.vwap_sell.toFixed(1)}` : "—"}
                              </td>
                            </tr>
                          ))}
                          {(!focusedProfile.top_distributed_stocks ||
                            focusedProfile.top_distributed_stocks.length === 0) && (
                            <tr>
                              <td colSpan={4} className="py-4 text-center text-xs text-slate-400">
                                No net distribution detected for this broker today.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {/* Counterparties Flow */}
                {focusedProfile.top_counterparties?.length > 0 && (
                  <div className={`p-4 rounded-xl border ${subCardBg} space-y-3`}>
                    <h4 className="text-xs font-extrabold uppercase flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-purple-600" />
                      <span>Counterparty Broker Flows for Broker #{focusedProfile.broker_no}</span>
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 font-mono-tabular">
                      {focusedProfile.top_counterparties.map((cp: any) => (
                        <div
                          key={cp.counterparty_broker_no}
                          className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60"
                        >
                          <div className="text-[10px] font-sans font-bold text-blue-600">
                            Broker #{cp.counterparty_broker_no}
                          </div>
                          <div className="text-xs font-bold truncate text-slate-800 dark:text-slate-200 mt-0.5">
                            {cp.counterparty_broker_name}
                          </div>
                          <div className="text-[11px] font-extrabold mt-1 text-slate-700 dark:text-slate-300">
                            NPR {(cp.total_flow_npr / 1_000_000).toFixed(2)}M
                          </div>
                          <div className="text-[9px] font-sans text-slate-500 mt-0.5">
                            {cp.contracts} contracts
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                Loading floorsheet profile for Broker #{focusedBrokerNo}...
              </div>
            )}
          </div>
        )}

        {/* TAB 2: MARKET-WIDE OTHER BROKERS */}
        {activityTab === "market" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top Accumulators Across NEPSE */}
              <div className={`p-4 rounded-xl border ${subCardBg} space-y-3`}>
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <h4 className="text-xs font-extrabold uppercase">
                    Top 10 Net Accumulating Brokers across NEPSE
                  </h4>
                </div>
                <div className="space-y-2 font-mono-tabular">
                  {brokerActivity?.top_net_buying_brokers?.slice(0, 8).map((b: any, idx: number) => (
                    <div
                      key={b.broker_no}
                      onClick={() => {
                        setFocusedBrokerNo(b.broker_no);
                        fetchBrokerActivity(b.broker_no);
                        setActivityTab("connected");
                      }}
                      className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-blue-500 bg-white dark:bg-slate-900/60 flex items-center justify-between cursor-pointer transition-all hover:scale-[1.01]"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-600 font-bold text-[10px] flex items-center justify-center font-sans">
                          #{idx + 1}
                        </span>
                        <div>
                          <div className="text-xs font-bold text-slate-800 dark:text-slate-200">
                            Broker #{b.broker_no} · {b.broker_name}
                          </div>
                          <div className="text-[10px] font-sans text-slate-500">
                            {b.total_contracts} trades · {b.buy_ratio_pct}% Buy Bias
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-extrabold text-emerald-600">
                          +NPR {(b.net_amount_npr / 1_000_000).toFixed(2)}M
                        </div>
                        <div className="text-[10px] font-sans text-slate-500">
                          {b.market_share_pct}% market share
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Top Distributors Across NEPSE */}
              <div className={`p-4 rounded-xl border ${subCardBg} space-y-3`}>
                <div className="flex items-center gap-2">
                  <TrendingDown className="w-4 h-4 text-rose-600" />
                  <h4 className="text-xs font-extrabold uppercase">
                    Top 10 Net Selling Brokers across NEPSE
                  </h4>
                </div>
                <div className="space-y-2 font-mono-tabular">
                  {brokerActivity?.top_net_selling_brokers?.slice(0, 8).map((b: any, idx: number) => (
                    <div
                      key={b.broker_no}
                      onClick={() => {
                        setFocusedBrokerNo(b.broker_no);
                        fetchBrokerActivity(b.broker_no);
                        setActivityTab("connected");
                      }}
                      className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-blue-500 bg-white dark:bg-slate-900/60 flex items-center justify-between cursor-pointer transition-all hover:scale-[1.01]"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-5 h-5 rounded-full bg-rose-500/10 text-rose-600 font-bold text-[10px] flex items-center justify-center font-sans">
                          #{idx + 1}
                        </span>
                        <div>
                          <div className="text-xs font-bold text-slate-800 dark:text-slate-200">
                            Broker #{b.broker_no} · {b.broker_name}
                          </div>
                          <div className="text-[10px] font-sans text-slate-500">
                            {b.total_contracts} trades · {b.buy_ratio_pct}% Buy Bias
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-extrabold text-rose-600">
                          NPR {(b.net_amount_npr / 1_000_000).toFixed(2)}M
                        </div>
                        <div className="text-[10px] font-sans text-slate-500">
                          {b.market_share_pct}% market share
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Complete 91 Brokers Searchable Directory */}
            <div className={`p-4 rounded-xl border ${subCardBg} space-y-3`}>
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-extrabold uppercase flex items-center gap-1.5">
                  <Building2 className="w-4 h-4 text-blue-600" />
                  <span>Official NEPSE Licensed Stock Brokers Directory ({brokerDirectory.length})</span>
                </h4>
                <div className="relative w-48">
                  <input
                    type="text"
                    value={brokerSearchQuery}
                    onChange={(e) => setBrokerSearchQuery(e.target.value)}
                    placeholder="Search broker # or name..."
                    className="w-full pl-7 pr-3 py-1 rounded-lg border text-xs bg-white dark:bg-slate-900 focus:outline-none"
                  />
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2 top-2" />
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
                {filteredBrokers.map((b) => (
                  <button
                    key={b.broker_no}
                    type="button"
                    onClick={() => {
                      setFocusedBrokerNo(b.broker_no);
                      fetchBrokerActivity(b.broker_no);
                      setActivityTab("connected");
                    }}
                    className="p-2 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-blue-500 bg-white dark:bg-slate-900/60 text-left cursor-pointer transition-all hover:scale-[1.02]"
                  >
                    <div className="text-[10px] font-bold text-blue-600">Broker #{b.broker_no}</div>
                    <div className="text-[11px] font-bold truncate text-slate-800 dark:text-slate-200">
                      {b.broker_name}
                    </div>
                    <div className="text-[9px] text-slate-500 font-mono-tabular mt-0.5">
                      {b.total_turnover_npr > 0
                        ? `NPR ${(b.total_turnover_npr / 1_000_000).toFixed(1)}M`
                        : "Inactive"}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: PORTFOLIO STOCKS BROKER RADAR */}
        {activityTab === "portfolio_radar" && (
          <div className="space-y-4">
            <p className={`text-xs ${mutedText}`}>
              Examines how your connected broker(s) and top institutional market brokers traded the
              stocks you currently hold in your portfolio on <strong>2026-10-16</strong>.
            </p>

            {brokerActivity?.held_symbols_broker_radar?.length ? (
              <div className="space-y-4">
                {brokerActivity.held_symbols_broker_radar.map((radar: any) => (
                  <div
                    key={radar.symbol}
                    className={`p-4 rounded-xl border ${subCardBg} space-y-3 font-mono-tabular`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm font-extrabold text-blue-600">{radar.symbol}</span>
                        <span className="ml-2 text-xs font-sans text-slate-500">
                          {radar.security_name}
                        </span>
                      </div>
                      <div className="text-xs text-right font-semibold">
                        Total Turnover: NPR {(radar.total_turnover_npr / 1_000_000).toFixed(2)}M ({radar.total_contracts} trades)
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Top Buyers */}
                      <div className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
                        <div className="text-[10px] font-sans font-bold text-emerald-600 uppercase mb-1">
                          Top Accumulating Brokers for {radar.symbol}
                        </div>
                        <div className="space-y-1 text-xs">
                          {radar.top_accumulating_brokers?.slice(0, 3).map((b: any) => (
                            <div key={b.broker_no} className="flex justify-between">
                              <span className="font-semibold text-slate-700 dark:text-slate-300">
                                Broker #{b.broker_no} ({b.broker_name})
                              </span>
                              <span className="font-extrabold text-emerald-600">
                                +{b.net_qty} sh (NPR {(b.net_amount_npr / 1000).toFixed(0)}K)
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Top Sellers */}
                      <div className="p-3 rounded-lg border border-rose-500/20 bg-rose-500/5">
                        <div className="text-[10px] font-sans font-bold text-rose-600 uppercase mb-1">
                          Top Distributing Brokers for {radar.symbol}
                        </div>
                        <div className="space-y-1 text-xs">
                          {radar.top_distributing_brokers?.slice(0, 3).map((b: any) => (
                            <div key={b.broker_no} className="flex justify-between">
                              <span className="font-semibold text-slate-700 dark:text-slate-300">
                                Broker #{b.broker_no} ({b.broker_name})
                              </span>
                              <span className="font-extrabold text-rose-600">
                                {b.net_qty} sh (NPR {(b.net_amount_npr / 1000).toFixed(0)}K)
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                Your portfolio currently has 0 holdings. Feed stocks to see institutional broker
                flows for your specific portfolio assets!
              </div>
            )}
          </div>
        )}
      </div>

      {/* =====================================================================
          CREATE / EDIT ACCOUNT MODAL DIALOG
         ===================================================================== */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            className={`w-full max-w-lg rounded-2xl border ${cardBg} shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150`}
          >
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-extrabold">
                  {editingAccountId ? "Edit Sub-Account & Broker" : "Create New Sub-Account"}
                </h3>
                <p className={`text-xs ${mutedText}`}>
                  Link an official NEPSE broker number and legal entity structure.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                className="p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body / Form */}
            <form onSubmit={handleSubmitAccount} className="p-5 space-y-4">
              {formError && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}
              {formSuccess && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>{formSuccess}</span>
                </div>
              )}

              {/* Account Label */}
              <div>
                <label className="block text-xs font-bold text-slate-600 dark:text-slate-300 uppercase mb-1">
                  Account Name / Label
                </label>
                <input
                  type="text"
                  value={formLabel}
                  onChange={(e) => setFormLabel(e.target.value)}
                  placeholder="e.g. Personal Alpha Desk, Family Endowment, Trading #1"
                  className={`w-full px-3.5 py-2.5 rounded-xl border text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 ${subCardBg}`}
                />
              </div>

              {/* Entity Type & Initial Cash */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-600 dark:text-slate-300 uppercase mb-1">
                    Entity Type
                  </label>
                  <select
                    value={formType}
                    onChange={(e) => setFormType(e.target.value)}
                    className={`w-full px-3.5 py-2.5 rounded-xl border text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 ${subCardBg}`}
                  >
                    <option value="PERSONAL">PERSONAL (5%/7.5% CGT)</option>
                    <option value="FAMILY">FAMILY (5%/7.5% CGT)</option>
                    <option value="CORPORATE">CORPORATE (10% CGT)</option>
                    <option value="TRUST">TRUST / INSTITUTIONAL</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-600 dark:text-slate-300 uppercase mb-1">
                    Initial Settled Cash (NPR)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="1000"
                    value={formCash}
                    onChange={(e) => setFormCash(e.target.value)}
                    placeholder="0"
                    className={`w-full px-3.5 py-2.5 rounded-xl border text-xs font-mono-tabular font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 ${subCardBg}`}
                  />
                </div>
              </div>

              {/* NEPSE Broker Selection */}
              <div>
                <label className="block text-xs font-bold text-slate-600 dark:text-slate-300 uppercase mb-1">
                  Apply NEPSE Broker Number (#1 to #101)
                </label>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={formBrokerNo}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFormBrokerNo(val);
                        setBrokerSearchQuery(val);
                      }}
                      placeholder="e.g. 58, 45, 34, 49, 42..."
                      className={`w-28 px-3.5 py-2.5 rounded-xl border text-xs font-mono-tabular font-bold focus:outline-none focus:ring-2 focus:ring-blue-500 ${subCardBg}`}
                    />
                    <select
                      value={formBrokerNo.replace(/\D/g, "")}
                      onChange={(e) => {
                        setFormBrokerNo(e.target.value);
                        setBrokerSearchQuery(e.target.value);
                      }}
                      className={`flex-1 px-3.5 py-2.5 rounded-xl border text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 ${subCardBg}`}
                    >
                      {brokerDirectory.map((b) => (
                        <option key={b.broker_no} value={b.broker_no}>
                          Broker #{b.broker_no} — {b.broker_name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {selectedBrokerObj && (
                    <div className="p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs flex items-center justify-between">
                      <span className="font-bold text-blue-600 dark:text-blue-400">
                        ✓ Selected: Broker #{selectedBrokerObj.broker_no} — {selectedBrokerObj.broker_name}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono-tabular">
                        tms{selectedBrokerObj.broker_no}.nepsetms.com.np
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* 16-Digit CDSC Demat BOID */}
              <div>
                <label className="block text-xs font-bold text-slate-600 dark:text-slate-300 uppercase mb-1">
                  16-Digit CDSC Demat BOID (Optional)
                </label>
                <input
                  type="text"
                  maxLength={16}
                  value={formBoid}
                  onChange={(e) => setFormBoid(e.target.value.replace(/\D/g, ""))}
                  placeholder="e.g. 1301010000482910 (Leave blank to auto-generate valid ID)"
                  className={`w-full px-3.5 py-2.5 rounded-xl border text-xs font-mono-tabular font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 ${subCardBg}`}
                />
                <span className="text-[10px] text-slate-400 mt-1 block">
                  {formBoid ? `${formBoid.length}/16 digits entered` : "Auto-generated if left blank."}
                </span>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 rounded-xl border text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-xl bg-[#0062A8] hover:bg-[#00518a] text-white text-xs font-extrabold cursor-pointer shadow-md transition-all"
                >
                  {isSubmitting
                    ? "Saving..."
                    : editingAccountId
                    ? "Save Changes"
                    : "Create Account & Link Broker"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
