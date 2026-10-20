/**
 * Apex Wealth — Dual-Layer Institutional Multi-Account Portfolio Management System (PMS)
 * Enterprise Executive Suite & Multi-Workspace Workstation (`src/App.tsx`)
 *
 * Unifies:
 * 1. Left Collapsible Enterprise Navigation Sidebar (9 Modules: Dashboard, Portfolio Grid,
 *    Smart Rebalancer, PMS Client Accounts, Stock Tracker, Risk & Alerts, Audit Receipts,
 *    Performance Scorecard, Quant Pro Lab)
 * 2. Top Royal Executive Header (`#0062A8` / `#080B11` Dark Mode toggle) + Live Scrolling NEPSE Ticker Ribbon
 * 3. 6-Card Executive KPI Strip (Total Invested Amount, Active Positions, Rate of Return,
 *    Health Score, Risks Identified, Tax Savings Approved)
 * 4. Multi-View Workspace Engine:
 *    - Executive Dashboard (KPI Strip + 3x2 Executive Panels + 9-Tile Action Launchpad)
 *    - Portfolio Grid (Triskell-Style Grouped RAG Traffic-Light Table with Inline Edit/Add/Import/Delete)
 *    - Smart 1-Tap Rebalancer (VWAP/TWAP 15% LOB Cap Slicing + CGT Waterfall)
 *    - PMS Client Accounts (4 Sub-Accounts + 16-Digit CDSC Demat BOIDs + Editable Cash)
 *    - Stock Tracker & Base Price Calculator (Live LTP, WACC, Bonus/Right Price Adjustment)
 *    - Risk & Alerts Radar (Tri-Horizon Past/Present/Future + Stress Simulator)
 *    - Tax & Merkle Audit Ledger (Plain-English Receipts + HMAC-SHA256 Merkle Proof Inspector)
 *    - Performance Scorecard (Actual vs Target SVG Line Charts, Cash Flow & Revenue Trends, KRI Commentary)
 *    - Quant Pro Lab (Schur-RA-HRP Dendrogram, Correlation Heatmap, 64-Byte Shared Memory Matrix)
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  BarChart3,
  Briefcase,
  Building2,
  Calculator,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  Edit3,
  Eye,
  FileCheck2,
  FolderKanban,
  GitBranch,
  LayoutDashboard,
  Layers,
  Lock,
  Moon,
  PieChart,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Settings,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Sun,
  Table,
  Target,
  Terminal,
  Trash2,
  TrendingUp,
  Upload,
  Users,
  Wallet,
} from "lucide-react";
import { HealthGauge } from "./components/HealthGauge";
import { RebalanceCard, ParentExecutionPlanItem } from "./components/RebalanceCard";
import {
  AllocationRings,
  SectorAllocationItem,
  SchurHRPTelemetry,
} from "./components/AllocationRings";
import { TaxActivityFeed, ActivityFeedItem } from "./components/TaxActivityFeed";
import { MerkleReceiptModal } from "./components/MerkleReceiptModal";
import { PortfolioManagerModal, TaxLotItem } from "./components/PortfolioManagerModal";
import {
  HighFrequencyTelemetryBuffer,
  initFDC3DesktopBridge,
} from "./fdc3_and_memory";

type ActiveModuleId =
  | "dashboard"
  | "grid"
  | "rebalance"
  | "accounts"
  | "tracker"
  | "risk"
  | "audit"
  | "scorecard"
  | "quant";

interface SubAccountSummary {
  account_id: string;
  account_type: string;
  account_label: string;
  broker_code: string;
  tms_client_code: string;
  boid_id: string;
  cash_balance: number;
  unsettled_cash_locked: number;
  available_cash: number;
  available_equity: number;
}

interface TriHorizonAlertItem {
  alert_id: string;
  code: string;
  horizon: "PAST" | "PRESENT" | "FUTURE" | string;
  severity: "INFO" | "WARNING" | "CRITICAL" | string;
  symbol: string | null;
  title: string;
  message: string;
  metric_value: number;
  threshold_value: number;
  remediation_action: string;
  timestamp: string;
}

interface KRICommentItem {
  id: string;
  author: string;
  role: string;
  date: string;
  text: string;
}

interface BatchAddRowDraft {
  id: string;
  sub_account_id: string;
  symbol: string;
  quantity: string;
  purchase_price: string;
  ltp: string;
  holding_days: string;
  is_promoter_locked: boolean;
}

const createEmptyBatchRows = (count = 5, defaultAccount = "Personal"): BatchAddRowDraft[] =>
  Array.from({ length: count }, (_, idx) => ({
    id: `row-${Date.now()}-${idx}-${Math.random().toString(36).slice(2, 6)}`,
    sub_account_id: defaultAccount,
    symbol: "",
    quantity: "",
    purchase_price: "",
    ltp: "",
    holding_days: "400",
    is_promoter_locked: false,
  }));

export const App: React.FC = () => {
  // Navigation & Theme State
  const [activeModule, setActiveModule] = useState<ActiveModuleId>("dashboard");
  const [executiveLightMode, setExecutiveLightMode] = useState<boolean>(true);
  const [isPortfolioManagerOpen, setIsPortfolioManagerOpen] = useState<boolean>(false);
  const [toxicSimulated, setToxicSimulated] = useState<boolean>(false);
  const [pmsState, setPmsState] = useState<any>(null);
  const [isExecutingRebalance, setIsExecutingRebalance] = useState<boolean>(false);
  const [selectedReceiptItem, setSelectedReceiptItem] = useState<ActivityFeedItem | null>(null);
  const [fdc3LastEvent, setFdc3LastEvent] = useState<string>("FDC3 2.0 Ready");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  // Portfolio Grid Mode: "batch_add" | "single_add" | "batch_remove"
  const [gridOperationMode, setGridOperationMode] = useState<"batch_add" | "single_add" | "batch_remove">("batch_add");
  const [showBatchPasteBox, setShowBatchPasteBox] = useState<boolean>(false);

  // Quick Inline Add State inside Grid View
  const [quickSymbol, setQuickSymbol] = useState<string>("");
  const [quickQty, setQuickQty] = useState<string>("");
  const [quickPrice, setQuickPrice] = useState<string>("");
  const [quickLtp, setQuickLtp] = useState<string>("");
  const [quickHoldingDays, setQuickHoldingDays] = useState<string>("400");
  const [quickAccount, setQuickAccount] = useState<string>("Personal");
  const [gridFeedback, setGridFeedback] = useState<string | null>(null);

  // Batch Add Mode State (Multi-Row Spreadsheet + Fast Paste)
  const [batchAddRows, setBatchAddRows] = useState<BatchAddRowDraft[]>(() => createEmptyBatchRows(5, "Personal"));
  const [batchPasteText, setBatchPasteText] = useState<string>("");
  const [isSubmittingBatchAdd, setIsSubmittingBatchAdd] = useState<boolean>(false);
  const [isSubmittingBatchRemove, setIsSubmittingBatchRemove] = useState<boolean>(false);
  const [isWipingAll, setIsWipingAll] = useState<boolean>(false);

  // Batch Remove Mode State (Multi-Select Lot IDs)
  const [selectedLotIds, setSelectedLotIds] = useState<string[]>([]);

  // Cash Balance Inline Edit State
  const [editingCashAccountId, setEditingCashAccountId] = useState<string | null>(null);
  const [editingCashValue, setEditingCashValue] = useState<string>("");

  // Base Price / Bonus & Right Share Calculator State (Screen 1 "Base Price" tool)
  const [calcMarketPrice, setCalcMarketPrice] = useState<string>("1245");
  const [calcBonusPct, setCalcBonusPct] = useState<string>("15");
  const [calcRightPct, setCalcRightPct] = useState<string>("10");
  const [calcPaidUpPrice, setCalcPaidUpPrice] = useState<string>("100");

  // Executive KRI Commentary State (Clean slate — user feeds notes)
  const [kriComments, setKriComments] = useState<KRICommentItem[]>([]);
  const [newCommentText, setNewCommentText] = useState<string>("");

  const [livePrices, setLivePrices] = useState<Record<string, number>>({
    NABIL: 1245.0,
    NICA: 890.0,
    SCB: 612.0,
    CHDC: 1620.0,
    HIDCL: 324.0,
    UPPER: 215.0,
    SHIVM: 595.0,
    NTC: 945.0,
    NRIC: 780.0,
    HDL: 1980.0,
    GBIME: 248.0,
    SANIMA: 312.0,
    EBL: 584.0,
    CIT: 2340.0,
    BPCL: 410.0,
    API: 204.0,
  });
  const [flashClasses, setFlashClasses] = useState<Record<string, string>>({});
  const hfBufferRef = useRef<HighFrequencyTelemetryBuffer>(new HighFrequencyTelemetryBuffer(128));

  const apiBase = useMemo(() => {
    if (typeof window === "undefined") return "http://127.0.0.1:8888";
    if (window.location.port === "5173" || window.location.port === "4173") {
      return "http://127.0.0.1:8888";
    }
    return window.location.origin;
  }, []);

  useEffect(() => {
    initFDC3DesktopBridge((intent) => {
      setFdc3LastEvent(`FDC3: ${intent}`);
    });
  }, []);

  const fetchPmsState = async (simToxic = toxicSimulated) => {
    try {
      const res = await fetch(
        `${apiBase}/api/v1/pms/state?simulate_toxic_vpin=${simToxic ? "true" : "false"}`
      );
      if (!res.ok) return;
      const data = await res.json();
      setPmsState(data);
      if (data.market_prices) {
        setLivePrices(data.market_prices);
      }
    } catch {
      // Offline fallback
    }
  };

  useEffect(() => {
    fetchPmsState(toxicSimulated);
  }, [toxicSimulated]);

  useEffect(() => {
    const wsProtocol = apiBase.startsWith("https") ? "wss" : "ws";
    const wsHost = apiBase.replace(/^https?:\/\//, "");
    let ws: WebSocket | null = null;

    try {
      ws = new WebSocket(`${wsProtocol}://${wsHost}/ws/pms/telemetry`);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "LIVE_TICK" && msg.symbol) {
            hfBufferRef.current.writeTick(
              msg.vpin ?? 0.18,
              msg.hawkes_intensity ?? 0.04,
              msg.price ?? 1000,
              msg.top3_lob_depth ?? 1500
            );
            setLivePrices((prev) => ({ ...prev, [msg.symbol]: msg.price }));
            setFlashClasses((prev) => ({
              ...prev,
              [msg.symbol]: msg.direction === "UP" ? "flash-up" : "flash-down",
            }));
            window.setTimeout(() => {
              setFlashClasses((prev) => ({ ...prev, [msg.symbol]: "" }));
            }, 600);
          }
        } catch {}
      };
    } catch {}

    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [apiBase]);

  const handleExecuteRebalance = async (profile: "VWAP" | "TWAP") => {
    setIsExecutingRebalance(true);
    try {
      if (window.fdc3) {
        await window.fdc3.raiseIntent("RebalanceAccount", {
          type: "fdc3.portfolio",
          name: vault.vault_name,
        });
      }

      const res = await fetch(`${apiBase}/api/v1/pms/rebalance/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          execution_profile: profile,
          simulate_toxic_regime: toxicSimulated,
        }),
      });
      if (res.ok) {
        await fetchPmsState(toxicSimulated);
      } else {
        const err = await res.json().catch(() => ({}));
        setGridFeedback(err.detail || "Cannot execute rebalance on an empty portfolio.");
      }
    } catch {
    } finally {
      setIsExecutingRebalance(false);
    }
  };

  const handleQuickAddStock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickSymbol.trim() || !quickQty || !quickPrice) return;
    setGridFeedback(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/add_position`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: quickSymbol.trim().toUpperCase(),
          quantity: parseInt(quickQty, 10),
          purchase_price: parseFloat(quickPrice),
          ltp: quickLtp ? parseFloat(quickLtp) : undefined,
          holding_days: quickHoldingDays ? parseInt(quickHoldingDays, 10) : 400,
          sub_account_id:
            quickAccount || vault.sub_account_summaries?.[0]?.account_id || "Personal",
          is_promoter_locked: false,
        }),
      });
      if (res.ok) {
        setGridFeedback(
          `✓ Added ${quickQty} shares of ${quickSymbol.toUpperCase()} @ NPR ${quickPrice} into portfolio!`
        );
        setQuickSymbol("");
        setQuickQty("");
        setQuickPrice("");
        setQuickLtp("");
        await fetchPmsState(toxicSimulated);
      }
    } catch {
      setGridFeedback("Error adding stock position.");
    }
  };

  // Batch Add Handlers
  const handleAddBatchRows = (count = 1) => {
    const defaultAcc = quickAccount || vault.sub_account_summaries?.[0]?.account_id || "Personal";
    setBatchAddRows((prev) => [...prev, ...createEmptyBatchRows(count, defaultAcc)]);
  };

  const handleUpdateBatchRow = (id: string, field: keyof BatchAddRowDraft, value: any) => {
    setBatchAddRows((prev) =>
      prev.map((r) => (r.id === id ? { ...r, [field]: value } : r))
    );
  };

  const handleRemoveBatchRow = (id: string) => {
    setBatchAddRows((prev) => (prev.length > 1 ? prev.filter((r) => r.id !== id) : prev));
  };

  const handleApplyAccountToAllBatchRows = (accountId: string) => {
    setBatchAddRows((prev) => prev.map((r) => ({ ...r, sub_account_id: accountId })));
  };

  const handleParsePasteIntoBatchRows = () => {
    if (!batchPasteText.trim()) return;
    const defaultAcc = quickAccount || vault.sub_account_summaries?.[0]?.account_id || "Personal";
    const lines = batchPasteText
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.length > 0 && !l.toLowerCase().startsWith("symbol"));

    const parsedRows: BatchAddRowDraft[] = [];
    for (let i = 0; i < lines.length; i++) {
      const parts = lines[i].split(/[\t,;]+|\s{2,}/).map((p) => p.trim()).filter(Boolean);
      const tokens = parts.length >= 3 ? parts : lines[i].split(/\s+/).map((p) => p.trim()).filter(Boolean);
      if (tokens.length >= 3) {
        const sym = tokens[0].toUpperCase();
        const qty = tokens[1].replace(/,/g, "");
        const price = tokens[2].replace(/,/g, "");
        const ltp = tokens[3] && !isNaN(Number(tokens[3].replace(/,/g, ""))) ? tokens[3].replace(/,/g, "") : "";
        const days = tokens[4] && !isNaN(Number(tokens[4])) ? tokens[4] : "400";
        const acc = tokens[5] || (tokens[3] && isNaN(Number(tokens[3])) ? tokens[3] : defaultAcc);
        parsedRows.push({
          id: `paste-${Date.now()}-${i}`,
          sub_account_id: acc,
          symbol: sym,
          quantity: qty,
          purchase_price: price,
          ltp,
          holding_days: days,
          is_promoter_locked: false,
        });
      }
    }
    if (parsedRows.length > 0) {
      setBatchAddRows(parsedRows);
      setBatchPasteText("");
      setGridFeedback(`✓ Parsed ${parsedRows.length} rows into the Batch Add table. Review and click "Commit Batch Add"!`);
    } else {
      setGridFeedback("Could not parse lines. Format each line as: SYMBOL, QUANTITY, BUY_PRICE [, LTP, HOLDING_DAYS, ACCOUNT]");
    }
  };

  const handleCommitBatchAdd = async () => {
    const validItems = batchAddRows
      .map((r) => ({
        sub_account_id: r.sub_account_id || "Personal",
        symbol: r.symbol.trim().toUpperCase(),
        quantity: parseInt(r.quantity, 10),
        purchase_price: parseFloat(r.purchase_price),
        ltp: r.ltp.trim() ? parseFloat(r.ltp) : undefined,
        holding_days: r.holding_days.trim() ? parseInt(r.holding_days, 10) : 400,
        is_promoter_locked: Boolean(r.is_promoter_locked),
      }))
      .filter((it) => it.symbol && it.quantity > 0 && it.purchase_price > 0);

    if (validItems.length === 0) {
      setGridFeedback("Please fill at least 1 row with a valid Stock Symbol, Quantity > 0, and Buy Price > 0.");
      return;
    }

    setIsSubmittingBatch(true);
    setGridFeedback(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/batch_add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: validItems }),
      });
      if (res.ok) {
        const data = await res.json();
        setGridFeedback(`✓ ${data.message || `Batch-added ${validItems.length} positions into portfolio!`}`);
        setBatchAddRows(createEmptyBatchRows(5, validItems[0].sub_account_id));
        await fetchPmsState(toxicSimulated);
      } else {
        const err = await res.json().catch(() => ({}));
        setGridFeedback(err.detail || "Failed to batch-add positions.");
      }
    } catch {
      setGridFeedback("Network error while batch-adding positions.");
    } finally {
      setIsSubmittingBatch(false);
    }
  };

  // Single & Batch Remove Handlers
  const handleDeleteLot = async (lotId: string) => {
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/lot/${lotId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSelectedLotIds((prev) => prev.filter((id) => id !== lotId));
        await fetchPmsState(toxicSimulated);
      }
    } catch {}
  };

  const toggleSelectLot = (lotId: string) => {
    setSelectedLotIds((prev) =>
      prev.includes(lotId) ? prev.filter((id) => id !== lotId) : [...prev, lotId]
    );
  };

  const handleBatchRemoveSelected = async () => {
    if (selectedLotIds.length === 0) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/batch_remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lot_ids: selectedLotIds }),
      });
      if (res.ok) {
        const data = await res.json();
        setGridFeedback(`✓ Removed ${data.removed_count ?? selectedLotIds.length} selected holding(s).`);
        setSelectedLotIds([]);
        await fetchPmsState(toxicSimulated);
      }
    } catch {
      setGridFeedback("Error batch-removing selected holdings.");
    }
  };

  const handleClearAccountLots = async (subAccountId: string, accountLabel: string) => {
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/batch_remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sub_account_id: subAccountId }),
      });
      if (res.ok) {
        const data = await res.json();
        setGridFeedback(`✓ Cleared ${data.removed_count ?? 0} holding(s) from ${accountLabel}.`);
        setSelectedLotIds([]);
        await fetchPmsState(toxicSimulated);
      }
    } catch {}
  };

  const handleWipeAllData = async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/clear_all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reset_cash: true }),
      });
      if (res.ok) {
        setSelectedLotIds([]);
        setGridFeedback("✓ All portfolio holdings, cash balances, and execution logs have been wiped to 0.");
        await fetchPmsState(toxicSimulated);
      }
    } catch {}
  };

  const handleSaveCashBalance = async (accountId: string) => {
    const val = parseFloat(editingCashValue);
    if (isNaN(val) || val < 0) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/pms/portfolio/update_cash`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sub_account_id: accountId, cash_balance: val }),
      });
      if (res.ok) {
        setEditingCashAccountId(null);
        await fetchPmsState(toxicSimulated);
      }
    } catch {}
  };

  const vault = pmsState?.vault || {
    vault_name: "Sovereign Himalaya Multi-Family & Institutional Vault",
    symbols: Object.keys(livePrices),
    x_gross: {},
    x_settlement_lock: {},
    x_promoter_lock: {},
    x_available: {},
    total_cash: 0,
    unsettled_cash_t2: 0,
    available_cash: 0,
    total_equity_market_value: 0,
    nav_total: 0,
    r_lock_ratio: 0.0,
    sub_account_summaries: [
      {
        account_id: "a1111111-0000-0000-0000-000000000001",
        account_type: "PERSONAL",
        account_label: "Personal Alpha Desk (TMS #58)",
        broker_code: "58",
        tms_client_code: "TMS58-NP-99401",
        boid_id: "1301010000482910",
        cash_balance: 0,
        unsettled_cash_locked: 0,
        available_cash: 0,
        available_equity: 0,
      },
      {
        account_id: "a2222222-0000-0000-0000-000000000002",
        account_type: "FAMILY",
        account_label: "Family Endowment Trust (TMS #45)",
        broker_code: "45",
        tms_client_code: "TMS45-FAM-21084",
        boid_id: "1301060001928374",
        cash_balance: 0,
        unsettled_cash_locked: 0,
        available_cash: 0,
        available_equity: 0,
      },
      {
        account_id: "a3333333-0000-0000-0000-000000000003",
        account_type: "CORPORATE",
        account_label: "Himalaya Quantitative Corp Treasury (TMS #34)",
        broker_code: "34",
        tms_client_code: "TMS34-CORP-77012",
        boid_id: "1301120004455667",
        cash_balance: 0,
        unsettled_cash_locked: 0,
        available_cash: 0,
        available_equity: 0,
      },
      {
        account_id: "a4444444-0000-0000-0000-000000000004",
        account_type: "CORPORATE",
        account_label: "Sovereign Co-Investment Feeder (TMS #49)",
        broker_code: "49",
        tms_client_code: "TMS49-INST-55190",
        boid_id: "1301170008877665",
        cash_balance: 0,
        unsettled_cash_locked: 0,
        available_cash: 0,
        available_equity: 0,
      },
    ] as SubAccountSummary[],
  };

  const health = pmsState?.health_gauge || {
    score: 100,
    status: "Optimal",
    cvar_1d_pct: 0.0,
    vpin: 0.18,
    hawkes_intensity: 0.04,
    cdsc_t2_lockup_pct: 0.0,
    var_99_pct: 0.0,
    var_max_pct: 3.5,
    s_locked_ratio: 0.0,
    microstructure_penalty_applied: false,
    penalty_points: 0,
    slicing_engine_paused: false,
  };

  const rebalanceCard = pmsState?.rebalance_card || {
    layman_cta_copy:
      "Your portfolio is currently empty (0 holdings). Use Batch Add or Quick Add to feed your holdings and generate your live Schur-RA-HRP rebalance plan.",
    estimated_tax_harvest_savings_npr: 0,
    projected_health_score_delta: 0,
    post_trade_health_score: 100,
    execution_plans: [] as ParentExecutionPlanItem[],
    rebalance_executed_count: 0,
  };

  const allocationRings = pmsState?.allocation_rings || {
    sectors: [] as SectorAllocationItem[],
    schur_hrp: {
      assets: [],
      ordered_assets: [],
      raw_weights: {},
      hrp_baseline_weights: {},
      post_hysteresis_weights: {},
      asset_ranks: {},
      raw_condition_number: 124.8,
      shrunk_condition_number: 1.98,
      shrinkage_intensity: 0.42,
      gamma_requested: 0.65,
      gamma_effective: 0.65,
      portfolio_variance_hrp: 0.00018,
      portfolio_variance_schur: 0.00015,
      quasi_diag_corr_matrix: [],
      dendrogram_splits: [],
    } as SchurHRPTelemetry,
    rolling_turnover_metrics: {
      annual_turnover_unbuffered: 0.486,
      annual_turnover_hysteresis: 0.079,
      fee_drag_unbuffered: -0.00316,
      fee_drag_hysteresis: -0.00051,
    },
    deadband_corridor_pct: 2.5,
  };

  const taxLots: TaxLotItem[] = Array.isArray(pmsState?.tax_lots)
    ? pmsState.tax_lots
    : [];
  const activityFeed: ActivityFeedItem[] = pmsState?.activity_feed || [];
  const alerts: TriHorizonAlertItem[] = pmsState?.tri_horizon_alerts || [];

  // Calculate aggregate cost vs market value across all taxLots for KPI strip & Grid
  const portfolioSummaryMetrics = useMemo(() => {
    let totalCost = 0;
    let totalMarketVal = 0;
    let totalShares = 0;

    for (const lot of taxLots) {
      const mktPrice = livePrices[lot.symbol] ?? lot.purchase_price;
      totalCost += lot.quantity * lot.purchase_price;
      totalMarketVal += lot.quantity * mktPrice;
      totalShares += lot.quantity;
    }

    const unrealizedPnl = totalMarketVal - totalCost;
    const returnPct = totalCost > 0 ? (unrealizedPnl / totalCost) * 100 : 0.0;
    return {
      totalCost,
      totalMarketVal,
      totalShares,
      unrealizedPnl,
      returnPct,
    };
  }, [taxLots, livePrices]);

  // Group tax lots by Sub-Account for the Triskell-style Portfolio Grid
  const groupedLotsByAccount = useMemo(() => {
    const groups: Record<
      string,
      {
        accountLabel: string;
        boid: string;
        brokerCode: string;
        lots: TaxLotItem[];
        totalCost: number;
        totalValue: number;
      }
    > = {};

    const subMap: Record<string, SubAccountSummary> = {};
    for (const s of vault.sub_account_summaries || []) {
      subMap[s.account_id] = s;
    }

    for (const lot of taxLots) {
      if (
        searchQuery.trim() &&
        !lot.symbol.toLowerCase().includes(searchQuery.trim().toLowerCase()) &&
        !lot.boid_id.includes(searchQuery.trim())
      ) {
        continue;
      }
      const key = lot.sub_account_id || "default";
      const subInfo = subMap[key];
      const label = subInfo
        ? `${subInfo.account_label} (${subInfo.account_type})`
        : `Account BOID ${lot.boid_id}`;

      if (!groups[key]) {
        groups[key] = {
          accountLabel: label,
          boid: lot.boid_id,
          brokerCode: lot.broker_code,
          lots: [],
          totalCost: 0,
          totalValue: 0,
        };
      }
      const mktPrice = livePrices[lot.symbol] ?? lot.purchase_price;
      groups[key].lots.push(lot);
      groups[key].totalCost += lot.quantity * lot.purchase_price;
      groups[key].totalValue += lot.quantity * mktPrice;
    }

    return Object.entries(groups);
  }, [taxLots, vault.sub_account_summaries, livePrices, searchQuery]);

  // Base Price adjustment calculation (Screen 1 "Base Price" tool)
  const adjustedBasePrice = useMemo(() => {
    const p = parseFloat(calcMarketPrice) || 0;
    const b = (parseFloat(calcBonusPct) || 0) / 100;
    const r = (parseFloat(calcRightPct) || 0) / 100;
    const paid = parseFloat(calcPaidUpPrice) || 100;
    return (p + r * paid) / (1 + b + r);
  }, [calcMarketPrice, calcBonusPct, calcRightPct, calcPaidUpPrice]);

  // Sidebar Menu Items
  const navItems: Array<{
    id: ActiveModuleId;
    label: string;
    badge?: string;
    icon: React.ReactNode;
  }> = [
    {
      id: "dashboard",
      label: "Executive Dashboard",
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      id: "grid",
      label: "Portfolio Grid & Edit",
      badge: `${taxLots.length}`,
      icon: <Table className="w-4 h-4" />,
    },
    {
      id: "rebalance",
      label: "1-Tap Smart Rebalance",
      badge: "Action",
      icon: <Sparkles className="w-4 h-4" />,
    },
    {
      id: "accounts",
      label: "PMS Client Accounts",
      badge: "4",
      icon: <Users className="w-4 h-4" />,
    },
    {
      id: "tracker",
      label: "Stock Tracker & Tools",
      icon: <Calculator className="w-4 h-4" />,
    },
    {
      id: "risk",
      label: "Risk & Lock Shield",
      badge: `${alerts.length}`,
      icon: <ShieldAlert className="w-4 h-4" />,
    },
    {
      id: "audit",
      label: "Tax & Merkle Receipts",
      icon: <FileCheck2 className="w-4 h-4" />,
    },
    {
      id: "scorecard",
      label: "Performance Scorecard",
      icon: <BarChart3 className="w-4 h-4" />,
    },
    {
      id: "quant",
      label: "Quant Pro Lab",
      icon: <Terminal className="w-4 h-4" />,
    },
  ];

  // Colorful Action Tiles (Inspired by Screenshot 1's PMS Launchpad)
  const colorfulLaunchTiles = [
    {
      title: "Portfolio Grid & Edit",
      subtitle: `${taxLots.length} Active Tax Lots · Add / Import`,
      bg: "from-sky-500 to-blue-600",
      icon: <FolderKanban className="w-10 h-10 opacity-30" />,
      actionText: "Open Portfolio Grid",
      onClick: () => setActiveModule("grid"),
    },
    {
      title: "1-Tap Smart Rebalance",
      subtitle: `Saves NPR ${rebalanceCard.estimated_tax_harvest_savings_npr.toLocaleString("en-IN")} in CGT`,
      bg: "from-emerald-500 to-teal-600",
      icon: <Sparkles className="w-10 h-10 opacity-30" />,
      actionText: "Execute 1-Tap Rebalance",
      onClick: () => setActiveModule("rebalance"),
    },
    {
      title: "Add / Import Stocks",
      subtitle: "Quick Add or CSV Bulk Upload",
      bg: "from-amber-500 to-orange-600",
      icon: <Upload className="w-10 h-10 opacity-30" />,
      actionText: "Open Import Wizard",
      onClick: () => setIsPortfolioManagerOpen(true),
    },
    {
      title: "PMS Client Accounts",
      subtitle: "4 Sub-Accounts · 16-Digit BOIDs",
      bg: "from-rose-500 to-red-600",
      icon: <Users className="w-10 h-10 opacity-30" />,
      actionText: "Manage Accounts & Cash",
      onClick: () => setActiveModule("accounts"),
    },
    {
      title: "Stock Tracker & Base Price",
      subtitle: "Live NEPSE Tape & Bonus/Right Calc",
      bg: "from-teal-500 to-cyan-600",
      icon: <Calculator className="w-10 h-10 opacity-30" />,
      actionText: "Open Price Tools",
      onClick: () => setActiveModule("tracker"),
    },
    {
      title: "Performance Scorecard",
      subtitle: "Actual vs Target · Cash Flow KRI",
      bg: "from-indigo-500 to-blue-700",
      icon: <BarChart3 className="w-10 h-10 opacity-30" />,
      actionText: "View Executive Charts",
      onClick: () => setActiveModule("scorecard"),
    },
  ];

  // Theme surface classes
  const canvasBg = executiveLightMode
    ? "bg-[#F1F5F9] text-slate-800"
    : "bg-[#080B11] text-slate-100";
  const cardBg = executiveLightMode
    ? "bg-white border-slate-200/90 text-slate-800 shadow-sm"
    : "bg-[#111622] border-slate-800/90 text-slate-100 shadow-xl";
  const subCardBg = executiveLightMode
    ? "bg-slate-50 border-slate-200 text-slate-700"
    : "bg-[#1E2638] border-slate-700/70 text-slate-200";
  const mutedText = executiveLightMode ? "text-slate-500" : "text-slate-400";

  return (
    <div className={`min-h-screen flex flex-col ${canvasBg} transition-colors duration-200`}>
      {/* =====================================================================
          1. TOP ROYAL BLUE ENTERPRISE HEADER BAR (Inspired by Corporater & PMS)
         ===================================================================== */}
      <header className="bg-[#005A9C] text-white shadow-md z-40 sticky top-0">
        <div className="px-4 py-2.5 flex items-center justify-between gap-4">
          {/* Left: Brand & Breadcrumb */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-white/15 border border-white/25 flex items-center justify-center font-black text-base tracking-tighter">
              AW
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold tracking-tight text-base">
                  APEX WEALTH
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-400/20 text-emerald-200 border border-emerald-300/30">
                  Institutional PMS v2.5
                </span>
              </div>
              <div className="text-[11px] text-sky-100/80 hidden sm:block">
                {vault.vault_name} · 4 Sub-Accounts Connected (TMS #58, #45, #34, #49)
              </div>
            </div>
          </div>

          {/* Center: Global Search Input */}
          <div className="hidden md:flex items-center bg-white/15 hover:bg-white/20 focus-within:bg-white focus-within:text-slate-900 rounded-lg px-3 py-1.5 w-80 transition-all border border-white/20">
            <Search className="w-4 h-4 opacity-75 mr-2 shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                if (activeModule !== "grid" && e.target.value.trim()) {
                  setActiveModule("grid");
                }
              }}
              placeholder="Search ticker (NABIL, CHDC) or BOID..."
              className="bg-transparent text-xs w-full focus:outline-none placeholder:text-sky-100/70 focus:placeholder:text-slate-400"
            />
          </div>

          {/* Right: Quick Action Buttons & Theme Switcher */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setActiveModule("grid");
                setGridOperationMode("batch_add");
              }}
              className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow-sm transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>Batch Add / Remove Stocks</span>
            </button>

            <button
              type="button"
              onClick={() => setIsPortfolioManagerOpen(true)}
              className="px-3 py-1.5 rounded-lg bg-white/15 hover:bg-white/25 text-white font-bold text-xs flex items-center gap-1.5 border border-white/20 transition-colors cursor-pointer"
            >
              <Upload className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">CSV / Cash Manager</span>
            </button>

            <button
              type="button"
              onClick={() => setExecutiveLightMode((prev) => !prev)}
              className="px-2.5 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-semibold flex items-center gap-1.5 border border-white/15 cursor-pointer"
              title="Switch between Executive Light Suite and Dark Cockpit Theme"
            >
              {executiveLightMode ? (
                <>
                  <Moon className="w-3.5 h-3.5" />
                  <span className="hidden lg:inline">Dark Cockpit</span>
                </>
              ) : (
                <>
                  <Sun className="w-3.5 h-3.5 text-amber-300" />
                  <span className="hidden lg:inline">Executive Light</span>
                </>
              )}
            </button>

            <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/10 text-[11px] font-mono-tabular border border-white/15">
              <Share2 className="w-3 h-3 text-sky-200" />
              <span>{fdc3LastEvent}</span>
            </div>
          </div>
        </div>

        {/* LIVE NEPSE MARKET TICKER RIBBON (Inspired by Screenshot 1's Top Stock Tape) */}
        <div className="bg-[#0F172A] text-slate-200 border-t border-slate-800 py-1.5 px-3 overflow-hidden flex items-center text-xs font-mono-tabular">
          <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px] uppercase tracking-wider mr-3 shrink-0 flex items-center gap-1 border border-emerald-500/30">
            <Radio className="w-3 h-3 animate-pulse" /> NEPSE LIVE TAPE
          </span>
          <div className="overflow-hidden flex-1">
            <div className="animate-marquee flex items-center gap-6">
              {[...Object.entries(livePrices), ...Object.entries(livePrices)].map(
                ([sym, price], idx) => {
                  const grossQty = vault.x_gross?.[sym] || 0;
                  const isUp = idx % 3 !== 0;
                  return (
                    <span
                      key={`${sym}-${idx}`}
                      onClick={() => {
                        setSearchQuery(sym);
                        setActiveModule("grid");
                      }}
                      className={`inline-flex items-center gap-1.5 cursor-pointer hover:underline ${
                        flashClasses[sym] || ""
                      }`}
                    >
                      <strong className="text-white">{sym}</strong>
                      <span>{Number(price).toFixed(2)}</span>
                      {grossQty > 0 && (
                        <span className="text-slate-400">({grossQty.toLocaleString()} sh)</span>
                      )}
                      <span className={isUp ? "text-emerald-400" : "text-rose-400"}>
                        {isUp ? "▲" : "▼"}
                      </span>
                    </span>
                  );
                }
              )}
            </div>
          </div>
        </div>
      </header>

      {/* =====================================================================
          2. MAIN WORKSTATION BODY: LEFT SIDEBAR + RIGHT MULTI-VIEW WORKSPACE
         ===================================================================== */}
      <div className="flex flex-1">
        {/* LEFT ENTERPRISE SIDEBAR (Inspired by Screenshot 1 & Triskell Screenshot 2) */}
        <aside className="w-60 bg-[#1B2531] text-slate-200 shrink-0 flex flex-col justify-between border-r border-slate-800 select-none">
          <div>
            {/* Market Status Banner (Like Screenshot 1's orange/emerald status block) */}
            <div
              className={`px-4 py-3 flex items-center justify-between text-xs font-bold uppercase tracking-wider ${
                health.slicing_engine_paused
                  ? "bg-rose-600 text-white"
                  : "bg-emerald-600 text-white"
              }`}
            >
              <span className="flex items-center gap-2">
                <Activity className="w-4 h-4" />
                {health.slicing_engine_paused ? "Toxicity Brake Active" : "PMS Engine Active"}
              </span>
              <span className="text-[10px] bg-black/25 px-1.5 py-0.5 rounded font-mono-tabular">
                {health.score}/100
              </span>
            </div>

            {/* Navigation Menu */}
            <div className="p-2.5 space-y-1">
              <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                PMS Workspaces
              </div>
              {navItems.map((item) => {
                const isActive = activeModule === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveModule(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                      isActive
                        ? "bg-[#0062A8] text-white shadow-sm"
                        : "text-slate-300 hover:bg-slate-800/80 hover:text-white"
                    }`}
                  >
                    <span className="flex items-center gap-2.5">
                      {item.icon}
                      <span>{item.label}</span>
                    </span>
                    {item.badge ? (
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-mono-tabular ${
                          isActive
                            ? "bg-white/20 text-white"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {item.badge}
                      </span>
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 opacity-50" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Favorites / Quick Sub-Accounts Shortcut List (Like Triskell Bottom-Left Favorites) */}
            <div className="p-2.5 mt-2 border-t border-slate-800/90">
              <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-400 flex items-center justify-between">
                <span>Connected Sub-Accounts</span>
                <span>4</span>
              </div>
              <div className="space-y-1 mt-1">
                {vault.sub_account_summaries?.map((sub: SubAccountSummary) => (
                  <button
                    key={sub.account_id}
                    type="button"
                    onClick={() => setActiveModule("accounts")}
                    className="w-full px-3 py-1.5 rounded-md text-left text-[11px] text-slate-300 hover:bg-slate-800/70 flex items-center justify-between"
                  >
                    <span className="truncate max-w-[130px]">
                      #{sub.broker_code} · {sub.account_type}
                    </span>
                    <span className="font-mono-tabular text-emerald-400 font-semibold">
                      {(sub.available_equity / 1_000_000).toFixed(1)}M
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar Footer */}
          <div className="p-3 border-t border-slate-800 text-[11px] text-slate-400 space-y-1 font-mono-tabular">
            <div className="flex justify-between">
              <span>Schur κ Bound:</span>
              <span className="text-emerald-400">
                {allocationRings.schur_hrp.shrunk_condition_number.toFixed(2)} ≤ 2.0
              </span>
            </div>
            <div className="flex justify-between">
              <span>T+2 Lock Ratio:</span>
              <span className="text-sky-400">{(vault.r_lock_ratio * 100).toFixed(1)}% ≤ 30%</span>
            </div>
          </div>
        </aside>

        {/* ===================================================================
            3. RIGHT WORKSPACE CONTENT AREA
           =================================================================== */}
        <main className="flex-1 p-5 sm:p-6 overflow-y-auto space-y-6">
          {/* Top Sub-Navigation Breadcrumb & Horizontal Tab Strip (Corporater / Triskell style) */}
          <div className={`p-4 rounded-xl border ${cardBg} flex flex-wrap items-center justify-between gap-4`}>
            <div>
              <div className={`text-[11px] font-medium ${mutedText}`}>
                Apex Wealth HQ &gt; Multi-Account Vault &gt;{" "}
                <span className="font-semibold text-blue-600 dark:text-blue-400">
                  {navItems.find((n) => n.id === activeModule)?.label}
                </span>
              </div>
              <div className="flex items-center gap-2.5 mt-1">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/15 text-emerald-600 border border-emerald-500/30">
                  ● {health.score}/100 Optimal
                </span>
                <h1 className="text-xl font-extrabold tracking-tight">
                  Investment Portfolio Management
                </h1>
              </div>
            </div>

            {/* Horizontal View Switcher Tabs */}
            <div className="flex flex-wrap items-center gap-1.5">
              {(
                [
                  { id: "dashboard", label: "Dashboard" },
                  { id: "grid", label: "Portfolio Grid (Edit)" },
                  { id: "rebalance", label: "1-Tap Rebalance" },
                  { id: "scorecard", label: "Scorecard & Charts" },
                  { id: "risk", label: "Risks & Locks" },
                  { id: "quant", label: "Quant Pro" },
                ] as Array<{ id: ActiveModuleId; label: string }>
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveModule(tab.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    activeModule === tab.id
                      ? "bg-[#0062A8] text-white shadow-sm"
                      : executiveLightMode
                      ? "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* =================================================================
              6-CARD EXECUTIVE KPI SUMMARY STRIP (Inspired by Screenshot 5)
             ================================================================= */}
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
            <div
              onClick={() => setActiveModule("accounts")}
              className={`p-4 rounded-xl border ${cardBg} cursor-pointer hover:border-blue-500/60 transition-all`}
            >
              <div className={`text-[10px] font-bold uppercase tracking-wider ${mutedText}`}>
                Total Portfolio Value
              </div>
              <div className="text-2xl font-extrabold text-[#0062A8] dark:text-sky-400 font-mono-tabular mt-1.5">
                NPR {(vault.nav_total / 1_000_000).toFixed(2)}M
              </div>
              <div className={`text-[11px] mt-1 ${mutedText}`}>
                Cash: NPR {(vault.available_cash / 1_000_000).toFixed(2)}M
              </div>
            </div>

            <div
              onClick={() => setActiveModule("grid")}
              className={`p-4 rounded-xl border ${cardBg} cursor-pointer hover:border-blue-500/60 transition-all`}
            >
              <div className={`text-[10px] font-bold uppercase tracking-wider ${mutedText}`}>
                Active Tax Lots (#)
              </div>
              <div className="text-2xl font-extrabold text-[#0062A8] dark:text-sky-400 font-mono-tabular mt-1.5">
                {taxLots.length} Lots
              </div>
              <div className={`text-[11px] mt-1 ${mutedText}`}>
                {portfolioSummaryMetrics.totalShares.toLocaleString()} Total Shares
              </div>
            </div>

            <div
              onClick={() => setActiveModule("scorecard")}
              className={`p-4 rounded-xl border ${cardBg} cursor-pointer hover:border-blue-500/60 transition-all`}
            >
              <div className={`text-[10px] font-bold uppercase tracking-wider ${mutedText}`}>
                Net Rate of Return
              </div>
              <div
                className={`text-2xl font-extrabold font-mono-tabular mt-1.5 flex items-center gap-1 ${
                  portfolioSummaryMetrics.returnPct >= 0
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-rose-600"
                }`}
              >
                {portfolioSummaryMetrics.returnPct >= 0 ? "+" : ""}
                {portfolioSummaryMetrics.returnPct.toFixed(2)}%
              </div>
              <div className={`text-[11px] mt-1 ${mutedText}`}>
                P&L: NPR {(portfolioSummaryMetrics.unrealizedPnl / 1_000_000).toFixed(2)}M
              </div>
            </div>

            <div
              onClick={() => setActiveModule("dashboard")}
              className={`p-4 rounded-xl border ${cardBg} cursor-pointer hover:border-blue-500/60 transition-all`}
            >
              <div className={`text-[10px] font-bold uppercase tracking-wider ${mutedText}`}>
                Portfolio Health Score
              </div>
              <div className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 font-mono-tabular mt-1.5">
                {health.score} / 100
              </div>
              <div className={`text-[11px] mt-1 ${mutedText}`}>
                Status: {health.status}
              </div>
            </div>

            <div
              onClick={() => setActiveModule("risk")}
              className={`p-4 rounded-xl border ${cardBg} cursor-pointer hover:border-blue-500/60 transition-all`}
            >
              <div className={`text-[10px] font-bold uppercase tracking-wider ${mutedText}`}>
                Risks & Locks Identified
              </div>
              <div className="text-2xl font-extrabold text-amber-500 font-mono-tabular mt-1.5">
                {alerts.length}
              </div>
              <div className={`text-[11px] mt-1 ${mutedText}`}>
                1 Promoter Lock (UPPER)
              </div>
            </div>

            <div
              onClick={() => setActiveModule("rebalance")}
              className={`p-4 rounded-xl border ${cardBg} cursor-pointer hover:border-blue-500/60 transition-all`}
            >
              <div className={`text-[10px] font-bold uppercase tracking-wider ${mutedText}`}>
                Tax Savings Ready
              </div>
              <div className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 font-mono-tabular mt-1.5">
                NPR {(rebalanceCard.estimated_tax_harvest_savings_npr / 1000).toFixed(1)}K
              </div>
              <div className={`text-[11px] mt-1 ${mutedText}`}>
                5.0% Long-Term CGT Tier
              </div>
            </div>
          </div>

          {/* =================================================================
              VIEW 1: EXECUTIVE DASHBOARD (Default Landing View)
             ================================================================= */}
          {activeModule === "dashboard" && (
            <div className="space-y-6">
              {taxLots.length === 0 && (
                <div className="p-5 rounded-xl border-2 border-emerald-500/50 bg-emerald-500/10 flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-extrabold text-emerald-600 dark:text-emerald-400">
                      <Sparkles className="w-4 h-4" />
                      <span>Clean Slate Active — 0 Preloaded Holdings in Vault</span>
                    </div>
                    <p className={`text-xs mt-1 ${mutedText}`}>
                      All demo data has been removed. Feed your own stocks using the Multi-Row Batch Add Spreadsheet, Fast Text Paste, or MeroShare CSV Import.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() => {
                        setActiveModule("grid");
                        setGridOperationMode("batch_add");
                      }}
                      className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-sm cursor-pointer"
                    >
                      <Plus className="w-4 h-4" />
                      <span>Open Batch Add Spreadsheet</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsPortfolioManagerOpen(true)}
                      className="px-4 py-2 rounded-lg bg-[#0062A8] hover:bg-blue-600 text-white font-bold text-xs flex items-center gap-1.5 shadow-sm cursor-pointer"
                    >
                      <Upload className="w-4 h-4" />
                      <span>Import CSV / Update Cash</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Vibrant Action Tiles Row (Inspired by Screenshot 1) */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Quick Action Launchpad — Click Any Module
                  </h2>
                  <span className={`text-xs ${mutedText}`}>
                    Layman Zero-Friction Controls · Institutional Engine Underneath
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {colorfulLaunchTiles.map((tile) => (
                    <div
                      key={tile.title}
                      onClick={tile.onClick}
                      className={`rounded-xl bg-gradient-to-r ${tile.bg} text-white shadow-md hover:shadow-lg hover:scale-[1.01] transition-all cursor-pointer overflow-hidden flex flex-col justify-between`}
                    >
                      <div className="p-4 flex items-center justify-between">
                        <div>
                          <div className="text-base font-extrabold tracking-tight">
                            {tile.title}
                          </div>
                          <div className="text-xs text-white/90 mt-1 font-medium">
                            {tile.subtitle}
                          </div>
                        </div>
                        {tile.icon}
                      </div>
                      <div className="bg-black/20 px-4 py-2 text-xs font-bold flex items-center justify-between">
                        <span>{tile.actionText}</span>
                        <ArrowUpRight className="w-4 h-4" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Corporater-Style 3-Column Executive Status & Trend Grid (Screenshot 5) */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {/* Panel 1: Focus Areas & Risk Shield Status Table */}
                <div className={`p-5 rounded-xl border ${cardBg} flex flex-col justify-between`}>
                  <div>
                    <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
                      <span className="text-xs font-extrabold uppercase tracking-wider">
                        Focus Areas & Safety Checks
                      </span>
                      <span className="text-[11px] font-bold text-emerald-600">
                        ● All Shields Active
                      </span>
                    </div>

                    <table className="w-full text-xs">
                      <thead>
                        <tr className={`border-b border-slate-200 dark:border-slate-800 ${mutedText} text-[10px] uppercase`}>
                          <th className="py-2 text-left">Safety Area</th>
                          <th className="py-2 text-center">Status</th>
                          <th className="py-2 text-right">Trend</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800/60">
                        <tr>
                          <td className="py-2.5 font-semibold">Downside Risk Cushion (CVaR)</td>
                          <td className="py-2.5 text-center">
                            <span className="inline-block w-3 h-3 rounded-full bg-emerald-500" />
                          </td>
                          <td className="py-2.5 text-right text-emerald-600 font-mono-tabular font-bold">
                            {health.cvar_1d_pct}% (Safe)
                          </td>
                        </tr>
                        <tr>
                          <td className="py-2.5 font-semibold">T+2 Cash Settlement Lock</td>
                          <td className="py-2.5 text-center">
                            <span className="inline-block w-3 h-3 rounded-full bg-emerald-500" />
                          </td>
                          <td className="py-2.5 text-right text-emerald-600 font-mono-tabular font-bold">
                            87.6% Unlocked
                          </td>
                        </tr>
                        <tr>
                          <td className="py-2.5 font-semibold">Order Flow Toxicity (VPIN)</td>
                          <td className="py-2.5 text-center">
                            <span
                              className={`inline-block w-3 h-3 rounded-full ${
                                health.vpin < 0.5 ? "bg-emerald-500" : "bg-rose-500"
                              }`}
                            />
                          </td>
                          <td className="py-2.5 text-right font-mono-tabular font-bold">
                            {health.vpin.toFixed(2)} (Normal)
                          </td>
                        </tr>
                        <tr>
                          <td className="py-2.5 font-semibold">3-Year Promoter Lock (UPPER)</td>
                          <td className="py-2.5 text-center">
                            <span className="inline-block w-3 h-3 rounded-full bg-amber-400" />
                          </td>
                          <td className="py-2.5 text-right text-amber-600 font-mono-tabular font-bold">
                            11d to Unlock
                          </td>
                        </tr>
                        <tr>
                          <td className="py-2.5 font-semibold">Annual Turnover Drag</td>
                          <td className="py-2.5 text-center">
                            <span className="inline-block w-3 h-3 rounded-full bg-emerald-500" />
                          </td>
                          <td className="py-2.5 text-right text-emerald-600 font-mono-tabular font-bold">
                            7.9% / yr
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveModule("risk")}
                    className="mt-4 w-full py-2 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-blue-600 hover:text-white text-xs font-bold transition-colors cursor-pointer"
                  >
                    Inspect Full Risk & Lock Shield →
                  </button>
                </div>

                {/* Panel 2: Multi-Account Performance Table (Screenshot 5 Center Panel) */}
                <div className={`p-5 rounded-xl border ${cardBg} flex flex-col justify-between`}>
                  <div>
                    <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
                      <span className="text-xs font-extrabold uppercase tracking-wider">
                        Sub-Account Performance
                      </span>
                      <button
                        type="button"
                        onClick={() => setIsPortfolioManagerOpen(true)}
                        className="text-[11px] font-bold text-[#0062A8] dark:text-sky-400 hover:underline cursor-pointer"
                      >
                        + Add / Edit Stocks
                      </button>
                    </div>

                    <table className="w-full text-xs">
                      <thead>
                        <tr className={`border-b border-slate-200 dark:border-slate-800 ${mutedText} text-[10px] uppercase`}>
                          <th className="py-2 text-left">Account Unit</th>
                          <th className="py-2 text-center">Status</th>
                          <th className="py-2 text-right">Equity (NPR)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800/60">
                        {vault.sub_account_summaries?.map((sub: SubAccountSummary) => (
                          <tr key={sub.account_id}>
                            <td className="py-2.5">
                              <div className="font-bold">{sub.account_label}</div>
                              <div className={`text-[10px] font-mono-tabular ${mutedText}`}>
                                BOID: {sub.boid_id}
                              </div>
                            </td>
                            <td className="py-2.5 text-center">
                              <span className="inline-block w-3 h-3 rounded-full bg-emerald-500" />
                            </td>
                            <td className="py-2.5 text-right font-mono-tabular font-bold">
                              {(sub.available_equity / 1_000_000).toFixed(2)}M
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveModule("accounts")}
                    className="mt-4 w-full py-2 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-blue-600 hover:text-white text-xs font-bold transition-colors cursor-pointer"
                  >
                    Manage Sub-Accounts & Cash Balances →
                  </button>
                </div>

                {/* Panel 3: 1-Tap Rebalance & Tax Optimization Action Box */}
                <div className={`p-5 rounded-xl border-2 border-blue-500/40 ${cardBg} flex flex-col justify-between`}>
                  <div>
                    <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
                      <span className="text-xs font-extrabold uppercase tracking-wider text-[#0062A8] dark:text-sky-400 flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4" />
                        1-Tap Smart Rebalancer
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-600">
                        +6 Pts Health Boost
                      </span>
                    </div>

                    <p className="text-xs leading-relaxed font-medium mb-4">
                      {rebalanceCard.layman_cta_copy}
                    </p>

                    <div className="grid grid-cols-2 gap-2.5 mb-4">
                      <div className={`p-3 rounded-lg border ${subCardBg}`}>
                        <div className={`text-[10px] uppercase font-bold ${mutedText}`}>
                          Est. Tax Savings
                        </div>
                        <div className="text-base font-extrabold text-emerald-600 dark:text-emerald-400 font-mono-tabular mt-0.5">
                          NPR {rebalanceCard.estimated_tax_harvest_savings_npr.toLocaleString("en-IN")}
                        </div>
                        <div className={`text-[10px] ${mutedText}`}>5.0% LTCGT Bracket</div>
                      </div>
                      <div className={`p-3 rounded-lg border ${subCardBg}`}>
                        <div className={`text-[10px] uppercase font-bold ${mutedText}`}>
                          Price Impact Cap
                        </div>
                        <div className="text-base font-extrabold text-[#0062A8] dark:text-sky-400 font-mono-tabular mt-0.5">
                          ≤ 7.2 bps
                        </div>
                        <div className={`text-[10px] ${mutedText}`}>15% LOB Depth Cap</div>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    disabled={isExecutingRebalance}
                    onClick={() => handleExecuteRebalance("VWAP")}
                    className="w-full py-3 px-4 rounded-xl bg-[#0062A8] hover:bg-blue-600 text-white font-bold text-xs shadow-md transition-all cursor-pointer flex items-center justify-center gap-2"
                  >
                    {isExecutingRebalance ? (
                      <span>Executing Pro-Rata Rebalance Across 4 Accounts...</span>
                    ) : (
                      <>
                        <span>Execute 1-Tap Smart Rebalance Now</span>
                        <ArrowUpRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Bottom Executive Row: Sector Allocation & Recent Audited Activity */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <AllocationRings
                  sectors={allocationRings.sectors}
                  schurHrp={allocationRings.schur_hrp}
                  rollingTurnoverMetrics={allocationRings.rolling_turnover_metrics}
                  deadbandCorridorPct={allocationRings.deadband_corridor_pct}
                />
                <TaxActivityFeed
                  items={activityFeed}
                  merkleRoot={pmsState?.merkle_root || "8afcb52b5b462ff4..."}
                  onInspectReceipt={(item) => setSelectedReceiptItem(item)}
                />
              </div>
            </div>
          )}

          {/* =================================================================
              VIEW 2: TRISKELL-STYLE GROUPED PORTFOLIO GRID & BATCH ADD / REMOVE
             ================================================================= */}
          {activeModule === "grid" && (
            <div className="space-y-5">
              {/* Mode Switcher Toolbar: Batch Add vs Single Add vs Batch Remove */}
              <div className={`p-3.5 rounded-xl border ${cardBg} flex flex-wrap items-center justify-between gap-3`}>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setGridOperationMode("batch_add")}
                    className={`px-3.5 py-2 rounded-lg text-xs font-extrabold flex items-center gap-1.5 transition-all cursor-pointer ${
                      gridOperationMode === "batch_add"
                        ? "bg-emerald-600 text-white shadow-sm"
                        : `${subCardBg} hover:border-emerald-500/50`
                    }`}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Batch Add Mode (Multi-Row Feed)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setGridOperationMode("single_add")}
                    className={`px-3.5 py-2 rounded-lg text-xs font-extrabold flex items-center gap-1.5 transition-all cursor-pointer ${
                      gridOperationMode === "single_add"
                        ? "bg-[#0062A8] text-white shadow-sm"
                        : `${subCardBg} hover:border-blue-500/50`
                    }`}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Quick Single Add</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setGridOperationMode("batch_remove")}
                    className={`px-3.5 py-2 rounded-lg text-xs font-extrabold flex items-center gap-1.5 transition-all cursor-pointer ${
                      gridOperationMode === "batch_remove"
                        ? "bg-rose-600 text-white shadow-sm"
                        : `${subCardBg} hover:border-rose-500/50`
                    }`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>
                      Batch Remove Mode{" "}
                      {selectedLotIds.length > 0 ? `(${selectedLotIds.length} Selected)` : ""}
                    </span>
                  </button>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsPortfolioManagerOpen(true)}
                    className="px-3.5 py-2 rounded-lg bg-[#0062A8] hover:bg-blue-600 text-white font-bold text-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>Bulk CSV / Cash Manager</span>
                  </button>

                  <button
                    type="button"
                    disabled={isWipingAll}
                    onClick={handleWipeAllData}
                    className="px-3.5 py-2 rounded-lg bg-rose-600/15 hover:bg-rose-600 hover:text-white text-rose-500 border border-rose-500/30 font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
                    title="Wipe all holdings, locks, and cash back to 0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>{isWipingAll ? "Wiping..." : "Wipe All Data (0 Slate)"}</span>
                  </button>
                </div>
              </div>

              {/* ===============================================================
                  MODE A: MULTI-ROW BATCH ADD SPREADSHEET + FAST TEXT PASTE
                 =============================================================== */}
              {gridOperationMode === "batch_add" && (
                <div className={`p-4 rounded-xl border-2 border-emerald-500/40 ${cardBg} space-y-4`}>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                    <div>
                      <div className="text-sm font-extrabold text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                        <Plus className="w-4 h-4" />
                        <span>Batch Add Stocks — Multi-Row Portfolio Feeder</span>
                      </div>
                      <p className={`text-xs ${mutedText} mt-0.5`}>
                        Enter multiple stock lots below or paste rows from Excel/MeroShare, then click{" "}
                        <strong>Commit Batch Add</strong> to feed them all at once.
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleAddBatchRows(1)}
                        className={`px-3 py-1.5 rounded-lg border text-xs font-bold cursor-pointer ${subCardBg} hover:border-emerald-500`}
                      >
                        + Add 1 Row
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAddBatchRows(5)}
                        className={`px-3 py-1.5 rounded-lg border text-xs font-bold cursor-pointer ${subCardBg} hover:border-emerald-500`}
                      >
                        + Add 5 Rows
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowBatchPasteBox((v) => !v)}
                        className="px-3 py-1.5 rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/30 text-xs font-bold cursor-pointer"
                      >
                        {showBatchPasteBox ? "Hide Fast Paste Box" : "⚡ Paste Multi-Line Text / CSV"}
                      </button>
                    </div>
                  </div>

                  {/* Optional Fast Paste Textarea */}
                  {showBatchPasteBox && (
                    <div className={`p-3.5 rounded-xl border ${subCardBg} space-y-2.5`}>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold">
                          Paste lines in format:{" "}
                          <code className="text-emerald-500">
                            SYMBOL, QUANTITY, BUY_PRICE [, LTP, HOLDING_DAYS, SUB_ACCOUNT_ID]
                          </code>
                        </span>
                        <span className={`text-[11px] ${mutedText}`}>
                          Supports comma, tab, or space separated lines
                        </span>
                      </div>
                      <textarea
                        rows={4}
                        value={batchPasteText}
                        onChange={(e) => setBatchPasteText(e.target.value)}
                        placeholder={`NABIL, 500, 485, 518, 400, sub-personal-01\nHDL, 300, 1290, 1345, 220, sub-family-02\nUPPER, 1000, 195, 198, 750, sub-corp-03`}
                        className={`w-full p-2.5 rounded-lg border text-xs font-mono-tabular ${cardBg} focus:outline-none focus:border-emerald-500`}
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={handleParsePasteIntoBatchRows}
                          className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold cursor-pointer"
                        >
                          Load Pasted Lines into Batch Spreadsheet ↓
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Multi-Row Batch Entry Spreadsheet */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className={`border-b border-slate-200 dark:border-slate-800 text-[10px] font-bold uppercase tracking-wider ${mutedText}`}>
                          <th className="py-2 px-2 text-left">#</th>
                          <th className="py-2 px-2 text-left">Target Sub-Account</th>
                          <th className="py-2 px-2 text-left">Ticker Symbol *</th>
                          <th className="py-2 px-2 text-left">Quantity (Shares) *</th>
                          <th className="py-2 px-2 text-left">Buy Price (NPR) *</th>
                          <th className="py-2 px-2 text-left">Live LTP (Optional)</th>
                          <th className="py-2 px-2 text-left">Holding Days</th>
                          <th className="py-2 px-2 text-center">Promoter Lock</th>
                          <th className="py-2 px-2 text-center">Row</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200/50 dark:divide-slate-800/50">
                        {batchAddRows.map((row, idx) => (
                          <tr key={row.rowId}>
                            <td className="py-2 px-2 font-mono-tabular font-bold text-slate-400">
                              {idx + 1}
                            </td>
                            <td className="py-2 px-2">
                              <select
                                value={row.subAccountId}
                                onChange={(e) =>
                                  handleUpdateBatchRow(row.rowId, "subAccountId", e.target.value)
                                }
                                className={`px-2.5 py-1.5 rounded-lg border text-xs w-full ${subCardBg}`}
                              >
                                {vault.sub_account_summaries?.map((acc: SubAccountSummary) => (
                                  <option key={acc.account_id} value={acc.account_id}>
                                    {acc.account_label}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-2 px-2">
                              <input
                                type="text"
                                value={row.symbol}
                                onChange={(e) =>
                                  handleUpdateBatchRow(
                                    row.rowId,
                                    "symbol",
                                    e.target.value.toUpperCase()
                                  )
                                }
                                placeholder="e.g. NABIL"
                                className={`px-2.5 py-1.5 rounded-lg border text-xs font-mono-tabular uppercase w-28 ${subCardBg}`}
                              />
                            </td>
                            <td className="py-2 px-2">
                              <input
                                type="number"
                                min="1"
                                value={row.quantity}
                                onChange={(e) =>
                                  handleUpdateBatchRow(row.rowId, "quantity", e.target.value)
                                }
                                placeholder="e.g. 500"
                                className={`px-2.5 py-1.5 rounded-lg border text-xs font-mono-tabular w-28 ${subCardBg}`}
                              />
                            </td>
                            <td className="py-2 px-2">
                              <input
                                type="number"
                                step="0.01"
                                min="0.01"
                                value={row.purchasePrice}
                                onChange={(e) =>
                                  handleUpdateBatchRow(row.rowId, "purchasePrice", e.target.value)
                                }
                                placeholder="e.g. 485"
                                className={`px-2.5 py-1.5 rounded-lg border text-xs font-mono-tabular w-28 ${subCardBg}`}
                              />
                            </td>
                            <td className="py-2 px-2">
                              <input
                                type="number"
                                step="0.01"
                                value={row.ltp}
                                onChange={(e) =>
                                  handleUpdateBatchRow(row.rowId, "ltp", e.target.value)
                                }
                                placeholder="Auto / Market"
                                className={`px-2.5 py-1.5 rounded-lg border text-xs font-mono-tabular w-28 ${subCardBg}`}
                              />
                            </td>
                            <td className="py-2 px-2">
                              <input
                                type="number"
                                min="0"
                                value={row.holdingDays}
                                onChange={(e) =>
                                  handleUpdateBatchRow(row.rowId, "holdingDays", e.target.value)
                                }
                                className={`px-2.5 py-1.5 rounded-lg border text-xs font-mono-tabular w-24 ${subCardBg}`}
                              />
                            </td>
                            <td className="py-2 px-2 text-center">
                              <input
                                type="checkbox"
                                checked={row.isPromoterLocked}
                                onChange={(e) =>
                                  handleUpdateBatchRow(
                                    row.rowId,
                                    "isPromoterLocked",
                                    e.target.checked
                                  )
                                }
                                className="w-4 h-4 accent-rose-600 cursor-pointer"
                                title="Check if 3-Year Mandatory Promoter Lock-in applies"
                              />
                            </td>
                            <td className="py-2 px-2 text-center">
                              <button
                                type="button"
                                onClick={() => handleRemoveBatchRow(row.rowId)}
                                className="p-1.5 rounded bg-rose-500/10 hover:bg-rose-500/25 text-rose-500 cursor-pointer"
                                title="Remove this input row"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-200 dark:border-slate-800">
                    <div className={`text-xs ${mutedText}`}>
                      Ready rows:{" "}
                      <strong className="text-emerald-500">
                        {
                          batchAddRows.filter(
                            (r) =>
                              r.symbol.trim() &&
                              Number(r.quantity) > 0 &&
                              Number(r.purchasePrice) > 0
                          ).length
                        }{" "}
                        valid stock lots
                      </strong>{" "}
                      (empty rows are automatically ignored)
                    </div>
                    <button
                      type="button"
                      disabled={isSubmittingBatchAdd}
                      onClick={handleCommitBatchAdd}
                      className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs flex items-center gap-2 shadow-md cursor-pointer"
                    >
                      <Plus className="w-4 h-4" />
                      <span>
                        {isSubmittingBatchAdd
                          ? "Feeding Batch into Institutional Engine..."
                          : "Commit Batch Add to Portfolio"}
                      </span>
                    </button>
                  </div>
                </div>
              )}

              {/* ===============================================================
                  MODE B: QUICK SINGLE ADD BAR
                 =============================================================== */}
              {gridOperationMode === "single_add" && (
                <form
                  onSubmit={handleQuickAddStock}
                  className={`p-4 rounded-xl border ${cardBg} flex flex-wrap items-end gap-3`}
                >
                  <div>
                    <label className={`block text-[10px] font-bold uppercase ${mutedText} mb-1`}>
                      Stock Ticker
                    </label>
                    <input
                      type="text"
                      required
                      value={quickSymbol}
                      onChange={(e) => setQuickSymbol(e.target.value)}
                      placeholder="e.g. NABIL"
                      className={`px-3 py-1.5 rounded-lg border text-xs font-mono-tabular w-28 ${subCardBg}`}
                    />
                  </div>
                  <div>
                    <label className={`block text-[10px] font-bold uppercase ${mutedText} mb-1`}>
                      Quantity (Shares)
                    </label>
                    <input
                      type="number"
                      required
                      value={quickQty}
                      onChange={(e) => setQuickQty(e.target.value)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-mono-tabular w-28 ${subCardBg}`}
                    />
                  </div>
                  <div>
                    <label className={`block text-[10px] font-bold uppercase ${mutedText} mb-1`}>
                      Purchase Price (NPR)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={quickPrice}
                      onChange={(e) => setQuickPrice(e.target.value)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-mono-tabular w-32 ${subCardBg}`}
                    />
                  </div>
                  <div>
                    <label className={`block text-[10px] font-bold uppercase ${mutedText} mb-1`}>
                      Target Sub-Account
                    </label>
                    <select
                      value={quickAccount}
                      onChange={(e) => setQuickAccount(e.target.value)}
                      className={`px-3 py-1.5 rounded-lg border text-xs ${subCardBg}`}
                    >
                      {vault.sub_account_summaries?.map((acc: SubAccountSummary) => (
                        <option key={acc.account_id} value={acc.account_id}>
                          {acc.account_label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="submit"
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 cursor-pointer shadow-sm"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>+ Add Single Position</span>
                  </button>
                </form>
              )}

              {/* ===============================================================
                  MODE C: BATCH REMOVE CONTROL DECK (Multi-Select, Account Clear, Wipe)
                 =============================================================== */}
              {(gridOperationMode === "batch_remove" || selectedLotIds.length > 0) && (
                <div className={`p-4 rounded-xl border-2 border-rose-500/40 ${cardBg} space-y-3`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-extrabold text-rose-500 flex items-center gap-2">
                        <Trash2 className="w-4 h-4" />
                        <span>
                          Batch Remove Mode — {selectedLotIds.length} of {filteredLots.length} Lots Selected
                        </span>
                      </div>
                      <p className={`text-xs ${mutedText} mt-0.5`}>
                        Tick checkboxes on individual stock rows or group headers below, or clear an entire sub-account in one click.
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={toggleSelectAllVisibleLots}
                        className={`px-3 py-1.5 rounded-lg border text-xs font-bold cursor-pointer ${subCardBg}`}
                      >
                        {selectedLotIds.length === filteredLots.length && filteredLots.length > 0
                          ? "Deselect All"
                          : `Select All Visible (${filteredLots.length})`}
                      </button>

                      <button
                        type="button"
                        disabled={selectedLotIds.length === 0 || isSubmittingBatchRemove}
                        onClick={handleBatchRemoveSelected}
                        className={`px-4 py-1.5 rounded-lg font-extrabold text-xs flex items-center gap-1.5 cursor-pointer ${
                          selectedLotIds.length > 0
                            ? "bg-rose-600 hover:bg-rose-500 text-white shadow-sm"
                            : "bg-slate-700/30 text-slate-500 cursor-not-allowed"
                        }`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>
                          {isSubmittingBatchRemove
                            ? "Removing..."
                            : `Batch Delete Selected (${selectedLotIds.length})`}
                        </span>
                      </button>
                    </div>
                  </div>

                  {/* Quick Per-Account Clear Strip */}
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                    <span className={`text-[11px] font-bold uppercase ${mutedText}`}>
                      1-Click Clear By Sub-Account:
                    </span>
                    {vault.sub_account_summaries?.map((acc: SubAccountSummary) => (
                      <button
                        key={acc.account_id}
                        type="button"
                        onClick={() => handleClearAccountLots(acc.account_id, acc.account_label)}
                        className="px-2.5 py-1 rounded-md bg-rose-500/10 hover:bg-rose-600 hover:text-white text-rose-500 border border-rose-500/25 text-[11px] font-bold transition-colors cursor-pointer"
                      >
                        Clear {acc.account_type} (#{acc.broker_code})
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {gridFeedback && (
                <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-600 dark:text-emerald-300 text-xs font-bold flex items-center justify-between">
                  <span>{gridFeedback}</span>
                  <button
                    type="button"
                    onClick={() => setGridFeedback(null)}
                    className="text-[11px] underline ml-4 cursor-pointer"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* Triskell-Style Grouped RAG Portfolio Table with Multi-Select Checkboxes */}
              <div className={`rounded-xl border ${cardBg} overflow-hidden`}>
                <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Table className="w-4 h-4 text-[#0062A8]" />
                    <span className="text-xs font-extrabold uppercase tracking-wider">
                      Master Multi-Account Portfolio Grid ({taxLots.length} Active Lots)
                    </span>
                  </div>
                  <div className="text-xs font-mono-tabular">
                    Total Equity Value:{" "}
                    <strong className="text-emerald-600 dark:text-emerald-400">
                      NPR {portfolioSummaryMetrics.totalMarketVal.toLocaleString("en-IN")}
                    </strong>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-100 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        <th className="py-2.5 px-3 text-center w-9">
                          <input
                            type="checkbox"
                            checked={
                              filteredLots.length > 0 &&
                              selectedLotIds.length === filteredLots.length
                            }
                            onChange={toggleSelectAllVisibleLots}
                            className="w-3.5 h-3.5 accent-rose-600 cursor-pointer"
                            title="Select / Deselect All Lots"
                          />
                        </th>
                        <th className="py-2.5 px-3 text-center">Health</th>
                        <th className="py-2.5 px-3 text-center">Tax Tier</th>
                        <th className="py-2.5 px-3 text-center">Lock</th>
                        <th className="py-2.5 px-3 text-left">Symbol</th>
                        <th className="py-2.5 px-3 text-left">Demat BOID / Broker</th>
                        <th className="py-2.5 px-3 text-center">Trend</th>
                        <th className="py-2.5 px-3 text-center">Schur Score</th>
                        <th className="py-2.5 px-3 text-center">Holding Status</th>
                        <th className="py-2.5 px-3 text-right">Shares</th>
                        <th className="py-2.5 px-3 text-right">Buy Price</th>
                        <th className="py-2.5 px-3 text-right">Live LTP</th>
                        <th className="py-2.5 px-3 text-right">Actual Cost</th>
                        <th className="py-2.5 px-3 text-right">Market Value</th>
                        <th className="py-2.5 px-3 text-right">Net P&L</th>
                        <th className="py-2.5 px-3 text-center">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200/70 dark:divide-slate-800/70 font-mono-tabular">
                      {groupedLotsByAccount.length === 0 ? (
                        <tr>
                          <td colSpan={16} className="py-12 px-4 text-center font-sans">
                            <div className="max-w-md mx-auto space-y-2">
                              <div className="text-sm font-extrabold">
                                Clean Slate — 0 Stock Holdings Currently in Vault
                              </div>
                              <p className={`text-xs ${mutedText}`}>
                                Use the <strong>Batch Add Spreadsheet</strong> above to feed multiple stocks at once, or click <strong>Bulk CSV / Cash Manager</strong> to import a CSV file.
                              </p>
                            </div>
                          </td>
                        </tr>
                      ) : (
                        groupedLotsByAccount.map(([groupKey, group]) => {
                          const isCollapsed = !!collapsedGroups[groupKey];
                          const groupPnl = group.totalValue - group.totalCost;
                          const groupLotIds = group.lots.map((l) => l.lot_id);
                          const allGroupSelected =
                            groupLotIds.length > 0 &&
                            groupLotIds.every((id) => selectedLotIds.includes(id));

                          return (
                            <React.Fragment key={groupKey}>
                              {/* Collapsible Group Header Row */}
                              <tr className="bg-slate-200/60 dark:bg-slate-800/70 font-sans font-extrabold text-xs hover:bg-slate-200 dark:hover:bg-slate-800">
                                <td className="py-2 px-3 text-center">
                                  <input
                                    type="checkbox"
                                    checked={allGroupSelected}
                                    onChange={() => toggleSelectGroupLots(groupLotIds)}
                                    className="w-3.5 h-3.5 accent-rose-600 cursor-pointer"
                                    title={`Select all lots in ${group.accountLabel}`}
                                  />
                                </td>
                                <td
                                  colSpan={11}
                                  onClick={() =>
                                    setCollapsedGroups((prev) => ({
                                      ...prev,
                                      [groupKey]: !prev[groupKey],
                                    }))
                                  }
                                  className="py-2 px-3 cursor-pointer"
                                >
                                  <div className="flex items-center gap-2">
                                    {isCollapsed ? (
                                      <ChevronRight className="w-4 h-4" />
                                    ) : (
                                      <ChevronDown className="w-4 h-4" />
                                    )}
                                    <span>
                                      {group.accountLabel.toUpperCase()} ({group.lots.length} ITEMS)
                                    </span>
                                    <span className="text-[11px] font-normal text-slate-500 font-mono-tabular ml-2">
                                      BOID: {group.boid} · TMS #{group.brokerCode}
                                    </span>
                                  </div>
                                </td>
                                <td className="py-2 px-3 text-right font-mono-tabular">
                                  {group.totalCost.toLocaleString("en-IN")}
                                </td>
                                <td className="py-2 px-3 text-right font-mono-tabular text-[#0062A8] dark:text-sky-400">
                                  {group.totalValue.toLocaleString("en-IN")}
                                </td>
                                <td
                                  className={`py-2 px-3 text-right font-mono-tabular ${
                                    groupPnl >= 0 ? "text-emerald-600" : "text-rose-600"
                                  }`}
                                >
                                  {groupPnl >= 0 ? "+" : ""}
                                  {groupPnl.toLocaleString("en-IN")}
                                </td>
                                <td />
                              </tr>

                              {/* Individual Lot Rows */}
                              {!isCollapsed &&
                                group.lots.map((lot) => {
                                  const ltp = livePrices[lot.symbol] ?? lot.purchase_price;
                                  const cost = lot.quantity * lot.purchase_price;
                                  const val = lot.quantity * ltp;
                                  const pnl = val - cost;
                                  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
                                  const isLongTerm = lot.holding_days > 365;
                                  const rank =
                                    allocationRings.schur_hrp.asset_ranks?.[lot.symbol] || 6;
                                  const scoreBadge = Math.max(
                                    5,
                                    Math.min(10, 11 - Math.ceil(rank / 2))
                                  );
                                  const isSelected = selectedLotIds.includes(lot.lot_id);

                                  return (
                                    <tr
                                      key={lot.lot_id}
                                      className={`transition-colors ${
                                        isSelected
                                          ? "bg-rose-500/10 hover:bg-rose-500/15"
                                          : "hover:bg-blue-500/5"
                                      }`}
                                    >
                                      <td className="py-2.5 px-3 text-center">
                                        <input
                                          type="checkbox"
                                          checked={isSelected}
                                          onChange={() => toggleSelectLot(lot.lot_id)}
                                          className="w-3.5 h-3.5 accent-rose-600 cursor-pointer"
                                        />
                                      </td>
                                      {/* RAG Traffic Light 1: Position Health */}
                                      <td className="py-2.5 px-3 text-center">
                                        <span
                                          className={`inline-block w-3 h-3 rounded-full ${
                                            pnl >= 0 ? "bg-emerald-500" : "bg-amber-500"
                                          }`}
                                          title={
                                            pnl >= 0 ? "In Profit" : "Tax-Loss Harvest Candidate"
                                          }
                                        />
                                      </td>
                                      {/* RAG Traffic Light 2: CGT Tax Bracket */}
                                      <td className="py-2.5 px-3 text-center">
                                        <span
                                          className={`inline-block w-3 h-3 rounded-full ${
                                            isLongTerm ? "bg-emerald-500" : "bg-sky-500"
                                          }`}
                                          title={lot.tax_bracket_label}
                                        />
                                      </td>
                                      {/* RAG Traffic Light 3: Lock Status */}
                                      <td className="py-2.5 px-3 text-center">
                                        <span
                                          className={`inline-block w-3 h-3 rounded-full ${
                                            lot.is_promoter_locked
                                              ? "bg-rose-500"
                                              : "bg-emerald-500"
                                          }`}
                                          title={
                                            lot.is_promoter_locked
                                              ? "3-Year Promoter Lock Active"
                                              : "Freely Tradable"
                                          }
                                        />
                                      </td>

                                      <td className="py-2.5 px-3 font-bold text-sm">
                                        {lot.symbol}
                                      </td>
                                      <td className="py-2.5 px-3 text-[11px] font-sans">
                                        TMS #{lot.broker_code} · {lot.tax_bracket_label}
                                      </td>
                                      <td className="py-2.5 px-3 text-center">
                                        {pnl >= 0 ? (
                                          <span className="inline-flex items-center gap-0.5 text-emerald-600 font-bold text-[11px]">
                                            <ArrowUpRight className="w-3.5 h-3.5" /> +
                                            {pnlPct.toFixed(1)}%
                                          </span>
                                        ) : (
                                          <span className="inline-flex items-center gap-0.5 text-amber-600 font-bold text-[11px]">
                                            <ArrowDownRight className="w-3.5 h-3.5" />{" "}
                                            {pnlPct.toFixed(1)}%
                                          </span>
                                        )}
                                      </td>

                                      {/* Triskell-style solid colored Score Cell */}
                                      <td
                                        className={`py-2.5 px-3 text-center font-bold text-white ${
                                          scoreBadge >= 8
                                            ? "bg-emerald-600"
                                            : scoreBadge >= 6
                                            ? "bg-amber-500"
                                            : "bg-rose-500"
                                        }`}
                                      >
                                        {scoreBadge}/10
                                      </td>

                                      {/* Triskell-style Delay/Duration Pill */}
                                      <td className="py-2.5 px-3 text-center">
                                        <span
                                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                            lot.is_promoter_locked
                                              ? "bg-rose-500/20 text-rose-600"
                                              : isLongTerm
                                              ? "bg-emerald-500/20 text-emerald-600"
                                              : "bg-sky-500/20 text-sky-600"
                                          }`}
                                        >
                                          {lot.holding_days}d held
                                        </span>
                                      </td>

                                      <td className="py-2.5 px-3 text-right font-bold">
                                        {lot.quantity.toLocaleString()}
                                      </td>
                                      <td className="py-2.5 px-3 text-right">
                                        {lot.purchase_price.toFixed(2)}
                                      </td>
                                      <td className="py-2.5 px-3 text-right font-bold text-[#0062A8] dark:text-sky-400">
                                        {ltp.toFixed(2)}
                                      </td>
                                      <td className="py-2.5 px-3 text-right">
                                        {cost.toLocaleString("en-IN")}
                                      </td>
                                      <td className="py-2.5 px-3 text-right font-bold">
                                        {val.toLocaleString("en-IN")}
                                      </td>
                                      <td
                                        className={`py-2.5 px-3 text-right font-bold ${
                                          pnl >= 0 ? "text-emerald-600" : "text-rose-600"
                                        }`}
                                      >
                                        {pnl >= 0 ? "+" : ""}
                                        {pnl.toLocaleString("en-IN")}
                                      </td>
                                      <td className="py-2.5 px-3 text-center">
                                        <button
                                          type="button"
                                          onClick={() => handleDeleteLot(lot.lot_id)}
                                          className="p-1.5 rounded bg-rose-500/10 hover:bg-rose-500/25 text-rose-500 cursor-pointer"
                                          title="Remove Lot"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                      </td>
                                    </tr>
                                  );
                                })}
                            </React.Fragment>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* =================================================================
              VIEW 3: 1-TAP SMART REBALANCER
             ================================================================= */}
          {activeModule === "rebalance" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-7">
                <RebalanceCard
                  laymanCtaCopy={rebalanceCard.layman_cta_copy}
                  estimatedTaxSavingsNpr={rebalanceCard.estimated_tax_harvest_savings_npr}
                  projectedHealthScoreDelta={rebalanceCard.projected_health_score_delta}
                  postTradeHealthScore={rebalanceCard.post_trade_health_score}
                  executionPlans={rebalanceCard.execution_plans}
                  rebalanceExecutedCount={rebalanceCard.rebalance_executed_count}
                  isExecuting={isExecutingRebalance}
                  onExecuteRebalance={handleExecuteRebalance}
                />
              </div>
              <div className="lg:col-span-5">
                <HealthGauge
                  score={health.score}
                  status={health.status}
                  cvar1dPct={health.cvar_1d_pct}
                  vpin={health.vpin}
                  hawkesIntensity={health.hawkes_intensity}
                  cdscT2LockupPct={health.cdsc_t2_lockup_pct}
                  var99Pct={health.var_99_pct}
                  varMaxPct={health.var_max_pct}
                  sLockedRatio={health.s_locked_ratio}
                  microstructurePenaltyApplied={health.microstructure_penalty_applied}
                  penaltyPoints={health.penalty_points}
                  slicingEnginePaused={health.slicing_engine_paused}
                  toxicSimulated={toxicSimulated}
                  onToggleToxicSimulation={() => setToxicSimulated((v) => !v)}
                />
              </div>
            </div>
          )}

          {/* =================================================================
              VIEW 4: PMS CLIENT ACCOUNTS & CASH EDITOR
             ================================================================= */}
          {activeModule === "accounts" && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-extrabold">
                    Connected PMS Sub-Accounts & CDSC Demat BOIDs
                  </h2>
                  <p className={`text-xs ${mutedText}`}>
                    Update cash balances or add new stock holdings into any legal entity account
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsPortfolioManagerOpen(true)}
                  className="px-4 py-2 rounded-xl bg-[#0062A8] text-white text-xs font-bold flex items-center gap-1.5 cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Stock Holding</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {vault.sub_account_summaries?.map((sub: SubAccountSummary) => (
                  <div
                    key={sub.account_id}
                    className={`p-5 rounded-xl border ${cardBg} space-y-4`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/15 text-blue-600 uppercase">
                          {sub.account_type} ENTITY
                        </span>
                        <h3 className="text-base font-extrabold mt-1">
                          {sub.account_label}
                        </h3>
                        <p className={`text-xs font-mono-tabular ${mutedText}`}>
                          16-Digit CDSC BOID: {sub.boid_id} · Broker TMS #{sub.broker_code} ({sub.tms_client_code})
                        </p>
                      </div>
                      <Building2 className="w-6 h-6 text-[#0062A8]" />
                    </div>

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

                    {/* Inline Cash Balance Update */}
                    <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
                      {editingCashAccountId === sub.account_id ? (
                        <div className="flex items-center gap-2 w-full">
                          <input
                            type="number"
                            value={editingCashValue}
                            onChange={(e) => setEditingCashValue(e.target.value)}
                            placeholder="New cash balance (NPR)"
                            className={`px-3 py-1.5 rounded-lg border text-xs font-mono-tabular flex-1 ${subCardBg}`}
                          />
                          <button
                            type="button"
                            onClick={() => handleSaveCashBalance(sub.account_id)}
                            className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-bold cursor-pointer"
                          >
                            Save Cash
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingCashAccountId(null)}
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
                              setEditingCashAccountId(sub.account_id);
                              setEditingCashValue(String(sub.cash_balance));
                            }}
                            className="px-3 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-blue-600 hover:text-white text-xs font-bold flex items-center gap-1 cursor-pointer transition-colors"
                          >
                            <Edit3 className="w-3 h-3" /> Edit Cash Balance
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* =================================================================
              VIEW 5: STOCK TRACKER & BASE PRICE CALCULATOR (Screenshot 1 Sidebar Tools)
             ================================================================= */}
          {activeModule === "tracker" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left 5 Cols: NEPSE Bonus / Right Share Base Price Adjustment Calculator */}
              <div className={`lg:col-span-5 p-5 rounded-xl border ${cardBg} space-y-4`}>
                <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
                  <Calculator className="w-5 h-5 text-[#0062A8]" />
                  <div>
                    <h2 className="text-sm font-extrabold uppercase">
                      NEPSE Bonus & Right Share Base Price Calculator
                    </h2>
                    <p className={`text-xs ${mutedText}`}>
                      Calculate adjusted price after corporate dividend / right announcements
                    </p>
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className={`block text-xs font-bold ${mutedText} mb-1`}>
                      Pre-Book Closure Market Price (NPR)
                    </label>
                    <input
                      type="number"
                      value={calcMarketPrice}
                      onChange={(e) => setCalcMarketPrice(e.target.value)}
                      className={`w-full px-3 py-2 rounded-lg border text-sm font-mono-tabular ${subCardBg}`}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={`block text-xs font-bold ${mutedText} mb-1`}>
                        Bonus Share (%)
                      </label>
                      <input
                        type="number"
                        value={calcBonusPct}
                        onChange={(e) => setCalcBonusPct(e.target.value)}
                        className={`w-full px-3 py-2 rounded-lg border text-sm font-mono-tabular ${subCardBg}`}
                      />
                    </div>
                    <div>
                      <label className={`block text-xs font-bold ${mutedText} mb-1`}>
                        Right Share (%)
                      </label>
                      <input
                        type="number"
                        value={calcRightPct}
                        onChange={(e) => setCalcRightPct(e.target.value)}
                        className={`w-full px-3 py-2 rounded-lg border text-sm font-mono-tabular ${subCardBg}`}
                      />
                    </div>
                  </div>
                  <div>
                    <label className={`block text-xs font-bold ${mutedText} mb-1`}>
                      Face / Paid-Up Value per Share (NPR)
                    </label>
                    <input
                      type="number"
                      value={calcPaidUpPrice}
                      onChange={(e) => setCalcPaidUpPrice(e.target.value)}
                      className={`w-full px-3 py-2 rounded-lg border text-sm font-mono-tabular ${subCardBg}`}
                    />
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-blue-600/10 border border-blue-500/30 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold uppercase text-[#0062A8] dark:text-sky-400">
                      Adjusted Base Price
                    </div>
                    <div className={`text-[11px] ${mutedText}`}>
                      P_adj = (P_mkt + R × 100) / (1 + B + R)
                    </div>
                  </div>
                  <div className="text-2xl font-black font-mono-tabular text-[#0062A8] dark:text-sky-400">
                    NPR {adjustedBasePrice.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Right 7 Cols: Live Universe Watchlist & Level-2 Depth Cap */}
              <div className={`lg:col-span-7 p-5 rounded-xl border ${cardBg}`}>
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
                  <span className="text-sm font-extrabold uppercase">
                    Live NEPSE Universe Stock Tracker (16 Institutional Symbols)
                  </span>
                  <span className="text-xs text-emerald-600 font-mono-tabular font-bold">
                    Sub-Second WebSocket Active
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono-tabular">
                    <thead>
                      <tr className={`border-b border-slate-200 dark:border-slate-800 ${mutedText} text-[10px] uppercase`}>
                        <th className="py-2 text-left">Ticker</th>
                        <th className="py-2 text-right">Live LTP (NPR)</th>
                        <th className="py-2 text-right">Vault Holding</th>
                        <th className="py-2 text-right">Target Weight</th>
                        <th className="py-2 text-center">Schur Rank</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800/60">
                      {Object.entries(livePrices).map(([sym, price]) => {
                        const qty = vault.x_gross?.[sym] || 0;
                        const tgtW =
                          (allocationRings.schur_hrp.post_hysteresis_weights?.[sym] || 0) *
                          100;
                        const rnk = allocationRings.schur_hrp.asset_ranks?.[sym] || "-";
                        return (
                          <tr key={sym} className={flashClasses[sym] || ""}>
                            <td className="py-2 font-bold">{sym}</td>
                            <td className="py-2 text-right font-bold text-[#0062A8] dark:text-sky-400">
                              {Number(price).toFixed(2)}
                            </td>
                            <td className="py-2 text-right">
                              {qty.toLocaleString()} sh
                            </td>
                            <td className="py-2 text-right text-emerald-600 font-bold">
                              {tgtW.toFixed(2)}%
                            </td>
                            <td className="py-2 text-center">#{rnk}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* =================================================================
              VIEW 6: TRI-HORIZON RISK & LOCK SHIELD
             ================================================================= */}
          {activeModule === "risk" && (
            <div className="space-y-5">
              <div className={`p-5 rounded-xl border ${cardBg} flex flex-wrap items-center justify-between gap-4`}>
                <div>
                  <h2 className="text-base font-extrabold">
                    Tri-Horizon Risk & Regulatory Lock Shield (Past · Present · Future)
                  </h2>
                  <p className={`text-xs ${mutedText}`}>
                    Automated monitoring for T+2 Cash Settlement Locks, VPIN Order Flow Toxicity, and 3-Year Promoter Cliffs
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setToxicSimulated((prev) => !prev)}
                  className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer transition-colors ${
                    toxicSimulated
                      ? "bg-rose-600 text-white"
                      : "bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/40"
                  }`}
                >
                  {toxicSimulated
                    ? "Reset Simulated VPIN Toxicity Spike"
                    : "Simulate Market Volatility Spike (VPIN ≥ 0.70)"}
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {(["PAST", "PRESENT", "FUTURE"] as const).map((horizon) => {
                  const horizonAlerts = alerts.filter((a) => a.horizon === horizon);
                  return (
                    <div key={horizon} className={`p-5 rounded-xl border ${cardBg} space-y-3`}>
                      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2.5">
                        <span className="text-xs font-extrabold uppercase tracking-wider">
                          {horizon} HORIZON
                        </span>
                        <span className={`text-[11px] font-mono-tabular ${mutedText}`}>
                          {horizon === "PAST"
                            ? "Merkle & CGT Audit"
                            : horizon === "PRESENT"
                            ? "VPIN · Hawkes · LOB"
                            : "VaR₉₉ · Rank · Cliff"}
                        </span>
                      </div>

                      {horizonAlerts.length === 0 ? (
                        <div className="py-6 text-center text-xs font-bold text-emerald-600">
                          ✓ All {horizon} Safeguards Verified Clean
                        </div>
                      ) : (
                        horizonAlerts.map((alert) => (
                          <div
                            key={alert.alert_id}
                            className={`p-3.5 rounded-xl border ${subCardBg} space-y-1.5`}
                          >
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-mono-tabular font-bold text-amber-600 dark:text-amber-400">
                                {alert.code}
                              </span>
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-600">
                                {alert.severity}
                              </span>
                            </div>
                            <div className="text-xs font-bold">{alert.title}</div>
                            <p className={`text-[11px] leading-relaxed ${mutedText}`}>
                              {alert.message}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* =================================================================
              VIEW 7: TAX & MERKLE AUDIT RECEIPTS
             ================================================================= */}
          {activeModule === "audit" && (
            <TaxActivityFeed
              items={activityFeed}
              merkleRoot={pmsState?.merkle_root || "8afcb52b5b462ff4..."}
              onInspectReceipt={(item) => setSelectedReceiptItem(item)}
            />
          )}

          {/* =================================================================
              VIEW 8: EXECUTIVE PERFORMANCE SCORECARD & KRI COMMENTARY
              (Modeled directly on Corporater Screenshots 4 & 5)
             ================================================================= */}
          {activeModule === "scorecard" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left 4 Cols: About This KRI + Executive Commentary Feed */}
              <div className="lg:col-span-4 space-y-5">
                <div className={`p-5 rounded-xl border ${cardBg} space-y-3`}>
                  <div className="text-xs font-extrabold uppercase tracking-wider border-b border-slate-200 dark:border-slate-800 pb-2.5">
                    About Portfolio KRI & Thresholds
                  </div>
                  <p className={`text-xs leading-relaxed ${mutedText}`}>
                    Measures risk-adjusted net asset value growth after NEPSE brokerage commissions,
                    SEBON fees, and 5.0%/7.5% capital gains taxes across all 4 sub-accounts.
                  </p>
                  <div className="space-y-1.5 pt-2 text-xs font-mono-tabular">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
                      <span>Optimal Score: 80.0 — 100.0</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-amber-400 inline-block" />
                      <span>Attention Corridor: 55.0 — 79.9</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
                      <span>Critical Brake: 0.0 — 54.9</span>
                    </div>
                  </div>
                </div>

                {/* KRI Commentary Card */}
                <div className={`p-5 rounded-xl border ${cardBg} space-y-3`}>
                  <div className="text-xs font-extrabold uppercase tracking-wider border-b border-slate-200 dark:border-slate-800 pb-2.5">
                    Executive KRI Commentary
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCommentText}
                      onChange={(e) => setNewCommentText(e.target.value)}
                      placeholder="Add an executive portfolio note..."
                      className={`flex-1 px-3 py-1.5 rounded-lg border text-xs ${subCardBg}`}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (!newCommentText.trim()) return;
                        setKriComments((prev) => [
                          {
                            id: `c-${Date.now()}`,
                            author: "Executive User",
                            role: "Vault Owner",
                            date: "Just now",
                            text: newCommentText.trim(),
                          },
                          ...prev,
                        ]);
                        setNewCommentText("");
                      }}
                      className="px-3 py-1.5 rounded-lg bg-[#0062A8] text-white text-xs font-bold cursor-pointer"
                    >
                      Post
                    </button>
                  </div>

                  <div className="space-y-3 pt-2">
                    {kriComments.map((c) => (
                      <div key={c.id} className={`p-3 rounded-lg border ${subCardBg} text-xs space-y-1`}>
                        <div className="flex items-center justify-between font-bold">
                          <span>{c.author}</span>
                          <span className={`text-[10px] ${mutedText}`}>{c.date}</span>
                        </div>
                        <p className={`text-[11px] leading-relaxed ${mutedText}`}>{c.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right 8 Cols: Actual vs Target KPI Strip + Development Over Time SVG Line Chart */}
              <div className="lg:col-span-8 space-y-5">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className={`p-4 rounded-xl border ${cardBg} text-center`}>
                    <div className={`text-[10px] font-bold uppercase ${mutedText}`}>
                      ACTUAL NAV (M)
                    </div>
                    <div className="text-2xl font-extrabold text-[#0062A8] dark:text-sky-400 font-mono-tabular mt-1">
                      94.99
                    </div>
                  </div>
                  <div className={`p-4 rounded-xl border ${cardBg} text-center`}>
                    <div className={`text-[10px] font-bold uppercase ${mutedText}`}>
                      TARGET NAV (M)
                    </div>
                    <div className="text-2xl font-extrabold text-[#0062A8] dark:text-sky-400 font-mono-tabular mt-1">
                      91.20
                    </div>
                  </div>
                  <div className={`p-4 rounded-xl border ${cardBg} text-center`}>
                    <div className={`text-[10px] font-bold uppercase ${mutedText}`}>
                      ACTUAL RETURN YTD
                    </div>
                    <div className="text-2xl font-extrabold text-emerald-600 font-mono-tabular mt-1">
                      +18.4%
                    </div>
                  </div>
                  <div className={`p-4 rounded-xl border ${cardBg} text-center`}>
                    <div className={`text-[10px] font-bold uppercase ${mutedText}`}>
                      BENCHMARK NEPSE YTD
                    </div>
                    <div className="text-2xl font-extrabold text-slate-500 font-mono-tabular mt-1">
                      +11.2%
                    </div>
                  </div>
                </div>

                {/* Development Over Time SVG Chart (Corporater Screenshot 4) */}
                <div className={`p-5 rounded-xl border ${cardBg}`}>
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-4">
                    <span className="text-xs font-extrabold uppercase tracking-wider">
                      Portfolio NAV Development Over Time (Actual Schur-HRP vs Benchmark Target)
                    </span>
                    <div className="flex items-center gap-4 text-xs font-semibold">
                      <span className="flex items-center gap-1.5 text-[#0062A8] dark:text-sky-400">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#0062A8]" /> Actual Portfolio
                      </span>
                      <span className="flex items-center gap-1.5 text-teal-500">
                        <span className="w-2.5 h-2.5 rounded-full bg-teal-500" /> Target Benchmark
                      </span>
                    </div>
                  </div>

                  <svg viewBox="0 0 700 220" className="w-full h-52 overflow-visible">
                    {/* Horizontal Grid Lines */}
                    {[30, 75, 120, 165].map((y) => (
                      <line
                        key={y}
                        x1="40"
                        y1={y}
                        x2="670"
                        y2={y}
                        stroke="currentColor"
                        strokeOpacity="0.1"
                      />
                    ))}
                    {/* Target Benchmark Line */}
                    <polyline
                      fill="none"
                      stroke="#14B8A6"
                      strokeWidth="2.5"
                      strokeDasharray="5 4"
                      points="50,165 110,152 170,138 230,144 290,125 350,118 410,105 470,112 530,94 590,82 650,70"
                    />
                    {/* Actual Portfolio Line */}
                    <polyline
                      fill="none"
                      stroke="#0062A8"
                      strokeWidth="3.5"
                      points="50,160 110,142 170,122 230,128 290,104 350,92 410,80 470,85 530,64 590,52 650,36"
                    />
                    {/* Data Nodes */}
                    {[
                      [50, 160, "78.2M"],
                      [170, 122, "82.4M"],
                      [290, 104, "85.1M"],
                      [410, 80, "88.9M"],
                      [530, 64, "91.8M"],
                      [650, 36, "95.0M"],
                    ].map(([x, y, label]) => (
                      <g key={String(x)}>
                        <circle cx={Number(x)} cy={Number(y)} r="4.5" fill="#0062A8" />
                        <text
                          x={Number(x)}
                          y={Number(y) - 10}
                          textAnchor="middle"
                          className="text-[10px] fill-current font-mono-tabular font-bold"
                        >
                          {label}
                        </text>
                      </g>
                    ))}
                  </svg>
                </div>
              </div>
            </div>
          )}

          {/* =================================================================
              VIEW 9: QUANT PRO LAB (Schur-RA-HRP + 64-Byte Shared Memory Matrix)
             ================================================================= */}
          {activeModule === "quant" && (
            <div className={`p-5 rounded-xl border ${cardBg} space-y-5`}>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-emerald-500" />
                  <div>
                    <h2 className="text-sm font-extrabold uppercase">
                      High-Density Quantitative Pro Telemetry & POSIX Shared Memory Matrix
                    </h2>
                    <p className={`text-xs font-mono-tabular ${mutedText}`}>
                      64-Byte Cache-Line Aligned Ring Buffer · Schur Complement Σ_A(γ) = Σ_A −
                      γΣ_AB Σ_B⁻¹ Σ_BA · FINOS FDC3 2.0
                    </p>
                  </div>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-mono-tabular bg-emerald-500/15 text-emerald-600 font-bold">
                  SharedArrayBuffer Ring Active (128 Slots)
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono-tabular text-xs border-collapse">
                  <thead>
                    <tr className={`border-b border-slate-200 dark:border-slate-800 ${mutedText} uppercase text-[10px]`}>
                      <th className="py-2.5 px-3">Symbol</th>
                      <th className="py-2.5 px-3">Live LTP (NPR)</th>
                      <th className="py-2.5 px-3">x_gross(t)</th>
                      <th className="py-2.5 px-3">x_settle_lock(t)</th>
                      <th className="py-2.5 px-3">x_promoter_lock(t)</th>
                      <th className="py-2.5 px-3">x_available(t)</th>
                      <th className="py-2.5 px-3">Schur Weight</th>
                      <th className="py-2.5 px-3">Hysteresis Weight</th>
                      <th className="py-2.5 px-3">Rank Rᵢ(t)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800/60">
                    {vault.symbols?.map((sym: string) => {
                      const rawW =
                        (allocationRings.schur_hrp.raw_weights?.[sym] || 0) * 100;
                      const hystW =
                        (allocationRings.schur_hrp.post_hysteresis_weights?.[sym] || 0) * 100;
                      const rank = allocationRings.schur_hrp.asset_ranks?.[sym] ?? "-";

                      return (
                        <tr key={sym} className="hover:bg-blue-500/5">
                          <td className="py-2 px-3 font-bold">{sym}</td>
                          <td className="py-2 px-3 text-[#0062A8] dark:text-sky-400 font-bold">
                            {(livePrices[sym] || 0).toFixed(2)}
                          </td>
                          <td className="py-2 px-3">
                            {(vault.x_gross?.[sym] || 0).toLocaleString()}
                          </td>
                          <td className="py-2 px-3 text-amber-600 font-semibold">
                            {(vault.x_settlement_lock?.[sym] || 0).toLocaleString()}
                          </td>
                          <td className="py-2 px-3 text-rose-600 font-semibold">
                            {(vault.x_promoter_lock?.[sym] || 0).toLocaleString()}
                          </td>
                          <td className="py-2 px-3 font-bold text-emerald-600">
                            {(vault.x_available?.[sym] || 0).toLocaleString()}
                          </td>
                          <td className="py-2 px-3">{rawW.toFixed(2)}%</td>
                          <td className="py-2 px-3 font-bold text-emerald-600">
                            {hystW.toFixed(2)}%
                          </td>
                          <td className="py-2 px-3">#{rank}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Merkle Receipt Proof Dialog */}
      <MerkleReceiptModal
        item={selectedReceiptItem}
        onClose={() => setSelectedReceiptItem(null)}
      />

      {/* Portfolio Manager Modal (View, Add, Edit, Delete, Bulk Import) */}
      <PortfolioManagerModal
        isOpen={isPortfolioManagerOpen}
        onClose={() => setIsPortfolioManagerOpen(false)}
        taxLots={taxLots}
        subAccounts={(vault.sub_account_summaries || []).map((s: SubAccountSummary) => ({
          account_id: s.account_id,
          account_label: s.account_label,
          broker_code: s.broker_code,
        }))}
        onRefresh={() => fetchPmsState(toxicSimulated)}
        apiBase={apiBase}
      />
    </div>
  );
};

export default App;
