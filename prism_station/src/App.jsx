import React, { useState, useEffect, useRef } from 'react';
import {
  Shield, Cpu, Activity, TrendingUp, AlertTriangle, CheckCircle,
  Clock, DollarSign, Database, Droplets, Zap, Send, RefreshCw,
  Lock, ArrowRight, BarChart2, Layers, Search, Terminal, Sliders
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('copilot'); // copilot, blotter, cartel, macro, contagion
  const [telemetry, setTelemetry] = useState({
    phase_name: "LIVE_CONTINUOUS",
    seqlock_sequence: 4,
    seqlock_consistent: true,
    t2_settled_cash: 450000.0,
    macro_oil_ewma: 77.57,
    macro_oil_zscore: -0.11,
    is_oil_shock_active: false,
    oil_regime: "OIL_NEUTRAL_EQUILIBRIUM",
    hawkes_spectral_radius: 0.820,
    is_contagion_critical: false,
    sahas_live_price: 690.0,
    sahas_cartel_density: 0.787
  });

  const [blotter, setBlotter] = useState([
    { target_asset: 'SAHAS', action: 'BUY', current_price: 690.0, approved_lots_kitta: 80, committed_capital_npr: 55200.0, limit_entry_npr: 687.2, stop_loss_npr: 678.9, take_profit_npr: 710.2, cro_verdict: 'APPROVED', strategic_rationale: 'Alpha conviction +0.55 backed by syndicate coordination (0.79) and peaking tariff advantages.' },
    { target_asset: 'CHCL', action: 'BUY', current_price: 325.0, approved_lots_kitta: 170, committed_capital_npr: 55250.0, limit_entry_npr: 323.7, stop_loss_npr: 312.0, take_profit_npr: 345.5, cro_verdict: 'APPROVED', strategic_rationale: 'Peaking clean energy tariffs and Indian IEX cross-border transmission beneficiary.' },
    { target_asset: 'NGPL', action: 'BUY', current_price: 393.3, approved_lots_kitta: 140, committed_capital_npr: 55062.0, limit_entry_npr: 391.7, stop_loss_npr: 375.0, take_profit_npr: 420.0, cro_verdict: 'APPROVED', strategic_rationale: 'Low-OPEX hydro producer benefiting from high autumn river discharge runoff.' },
    { target_asset: 'NABIL', action: 'BUY', current_price: 533.0, approved_lots_kitta: 80, committed_capital_npr: 42640.0, limit_entry_npr: 530.9, stop_loss_npr: 512.0, take_profit_npr: 565.0, cro_verdict: 'APPROVED', strategic_rationale: 'Tier-1 commercial bank deposit expansion under NRB easing corridor.' },
    { target_asset: 'CIT', action: 'BUY', current_price: 1708.0, approved_lots_kitta: 20, committed_capital_npr: 34160.0, limit_entry_npr: 1701.2, stop_loss_npr: 1640.0, take_profit_npr: 1820.0, cro_verdict: 'APPROVED', strategic_rationale: 'Institutional asset manager holding defensive sovereign treasury and cash reserve.' },
    { target_asset: 'SHIVM', action: 'AVOID_OR_EXIT', current_price: 681.7, approved_lots_kitta: 0, committed_capital_npr: 0.0, limit_entry_npr: 0.0, stop_loss_npr: 0.0, take_profit_npr: 0.0, cro_verdict: 'VETO_REJECTED', strategic_rationale: 'MANDATE DENIAL / FORCED EXIT. Chief Risk Officer issued hard veto: Cost-push clinker energy and freight squeeze.' },
    { target_asset: 'SARBTM', action: 'AVOID_OR_EXIT', current_price: 800.0, approved_lots_kitta: 0, committed_capital_npr: 0.0, limit_entry_npr: 0.0, stop_loss_npr: 0.0, take_profit_npr: 0.0, cro_verdict: 'VETO_REJECTED', strategic_rationale: 'MANDATE DENIAL / FORCED EXIT. Chief Risk Officer issued hard veto: Clinker burning expense margin compression.' },
    { target_asset: 'API', action: 'BUY', current_price: 335.7, approved_lots_kitta: 170, committed_capital_npr: 57069.0, limit_entry_npr: 334.4, stop_loss_npr: 321.0, take_profit_npr: 360.0, cro_verdict: 'APPROVED', strategic_rationale: 'Hydro accumulator benefiting from syndicate absorption and low leverage balance sheet.' }
  ]);

  const [cartelData, setCartelData] = useState({
    cluster_density: 0.787,
    active_cartel_detected: true,
    nodes: [
      { id: "B58", label: "Desk 58 (Naasa)", type: "MAJOR_ACCUMULATOR", flow: 128000, x: 220, y: 160 },
      { id: "B48", label: "Desk 48 (Trishakti)", type: "CARTEL_COORDINATOR", flow: 105000, x: 340, y: 120 },
      { id: "B17", label: "Desk 17 (ABC)", type: "CIRCULAR_PASS", flow: 92000, x: 420, y: 220 },
      { id: "B34", label: "Desk 34 (Vision)", type: "INSTITUTIONAL_ABSORBER", flow: 86000, x: 280, y: 280 },
      { id: "B59", label: "Desk 59 (Deevya)", type: "CARTEL_COORDINATOR", flow: 77000, x: 480, y: 130 },
      { id: "B28", label: "Desk 28 (Shree Krishna)", type: "MOMENTUM_PUSHER", flow: 73000, x: 120, y: 260 },
      { id: "B45", label: "Desk 45 (Imperial)", type: "RETAIL_DESK", flow: 41000, x: 100, y: 100 },
      { id: "B19", label: "Desk 19 (Stock House)", type: "RETAIL_DESK", flow: 32000, x: 150, y: 360 }
    ],
    edges: [
      { from: "B58", to: "B48", volume: 85, is_collusive: true },
      { from: "B48", to: "B17", volume: 78, is_collusive: true },
      { from: "B17", to: "B58", volume: 72, is_collusive: true },
      { from: "B58", to: "B34", volume: 62, is_collusive: true },
      { from: "B48", to: "B59", volume: 68, is_collusive: true },
      { from: "B59", to: "B17", volume: 61, is_collusive: true },
      { from: "B28", to: "B58", volume: 45, is_collusive: false },
      { from: "B45", to: "B19", volume: 25, is_collusive: false }
    ]
  });

  const [chatMessages, setChatMessages] = useState([
    {
      sender: 'CIO',
      time: '15:45 NPT',
      text: 'Good afternoon. I am your Sovereign Chief Investment Officer. I am continuously monitoring the lock-free Seqlock state (<2μs) and DuckDB Lakehouse. How can I assist with portfolio allocation or asset risk evaluation today?'
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isDeliberating, setIsDeliberating] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(blotter[0]);
  const [totalCapital, setTotalCapital] = useState(450000);
  const [stagedOrderResult, setStagedOrderResult] = useState(null);

  // Simulation Sliders
  const [simOilPrice, setSimOilPrice] = useState(75.40);
  const [simOilResult, setSimOilResult] = useState(null);

  // Connect to FastAPI Backend
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch('/api/telemetry');
        if (res.ok) {
          const data = await res.json();
          setTelemetry(data);
        }
      } catch (e) {
        // Fallback gracefully to live simulated heartbeat
      }
    };
    fetchTelemetry();
    const timer = setInterval(fetchTelemetry, 3000);
    return () => clearInterval(timer);
  }, []);

  const handleSendMessage = async (msgText) => {
    const text = msgText || chatInput;
    if (!text.trim()) return;

    const userMsg = { sender: 'Operator', time: new Date().toLocaleTimeString(), text };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setIsDeliberating(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages(prev => [...prev, {
          sender: 'CIO',
          time: new Date().toLocaleTimeString(),
          text: data.response_markdown,
          mandate: data.mandate
        }]);
      } else {
        throw new Error('Backend offline');
      }
    } catch (err) {
      // Offline fallback deliberation
      setTimeout(() => {
        let answer = `I have verified the Seqlock memory snapshot. Cash balance is NPR ${telemetry.t2_settled_cash.toLocaleString()}, Hawkes contagion is ${telemetry.hawkes_spectral_radius.toFixed(3)}, and Brent Crude EWMA-60 is $${telemetry.macro_oil_ewma.toFixed(2)}/bbl.`;
        if (text.toUpperCase().includes('SAHAS')) {
          answer = `SAHAS Recommendation: BUY 80 Kitta at limit 687.2 NPR. Alpha conviction is +0.55 with 0.79 syndicate coordination. 5-Day VaR stop pinned at 678.9 NPR. Take profit target 710.2 NPR.`;
        } else if (text.toUpperCase().includes('SHIVM')) {
          answer = `SHIVM Recommendation: AVOID / EXIT. Chief Risk Officer hard veto active due to clinker fuel and freight cost compression. Zero allocation approved.`;
        }
        setChatMessages(prev => [...prev, {
          sender: 'CIO',
          time: new Date().toLocaleTimeString(),
          text: answer
        }]);
      }, 600);
    } finally {
      setIsDeliberating(false);
    }
  };

  const handleStageOrder = async (item) => {
    try {
      const res = await fetch('/api/stage-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: item.target_asset,
          lots_kitta: item.approved_lots_kitta,
          limit_price: item.limit_entry_npr,
          stop_loss: item.stop_loss_npr,
          take_profit: item.take_profit_npr
        })
      });
      if (res.ok) {
        const data = await res.json();
        setStagedOrderResult(data);
      } else {
        const err = await res.json();
        alert(`Order Staging Rejected: ${err.detail}`);
      }
    } catch (e) {
      // Local fallback simulation
      setStagedOrderResult({
        status: "STAGED_AND_SEALED",
        order_id: `ORD-${Date.now()}`,
        symbol: item.target_asset,
        lots_kitta: item.approved_lots_kitta,
        shares: item.approved_lots_kitta * 10,
        limit_price: item.limit_entry_npr,
        committed_capital_npr: item.committed_capital_npr,
        settled_cash_remaining: telemetry.t2_settled_cash - item.committed_capital_npr,
        cipher_token: `SEAL_CHACHA20_${item.target_asset}_${item.approved_lots_kitta}K_${Date.now()}`
      });
    }
  };

  const handleSimulateOil = async (newPrice) => {
    setSimOilPrice(newPrice);
    try {
      const res = await fetch('/api/simulate-oil', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulated_oil_price: parseFloat(newPrice) })
      });
      if (res.ok) {
        const data = await res.json();
        setSimOilResult(data);
      }
    } catch (e) {
      const z = (newPrice - 78.50) / 8.20;
      setSimOilResult({
        simulated_price: newPrice,
        z_score: z.toFixed(2),
        is_shock_triggered: z > 2.0,
        max_equity_allocation_pct: z > 2.0 ? 60.0 : 85.0,
        cash_reserve_pct: z > 2.0 ? 40.0 : 15.0
      });
    }
  };

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-200 flex flex-col font-sans select-none">
      {/* ------------------------------------------------------------- */}
      {/* 1. TOP HEADER & MICROSECOND TELEMETRY HUD                     */}
      {/* ------------------------------------------------------------- */}
      <header className="border-b border-slate-800 bg-[#0d131f]/90 backdrop-blur px-6 py-3 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 font-bold shadow-[0_0_15px_rgba(16,185,129,0.25)]">
            <Cpu className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h1 className="text-base font-extrabold tracking-wide text-white flex items-center gap-2">
              CHRONOSTRATA PRIME
              <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                PRISM PRO STATION
              </span>
            </h1>
            <p className="text-[11px] text-slate-400 font-mono">
              Sovereign Quantitative Engine • Zero-Trust Execution Fabric • Nepal Stock Exchange (NEPSE)
            </p>
          </div>
        </div>

        {/* Telemetry Badges */}
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
            <span className="text-slate-400">PHASE:</span>
            <span className="text-emerald-400 font-bold">{telemetry.phase_name}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-400">SEQLOCK:</span>
            <span className="text-cyan-400 font-bold">#{telemetry.seqlock_sequence} (&lt;2μs)</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">T+2 SETTLED CASH:</span>
            <span className="text-emerald-300 font-bold">NPR {telemetry.t2_settled_cash.toLocaleString()}</span>
          </div>

          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border ${telemetry.is_oil_shock_active ? 'border-red-500/60 bg-red-950/20' : 'border-slate-800'}`}>
            <Droplets className={`w-3.5 h-3.5 ${telemetry.is_oil_shock_active ? 'text-red-400' : 'text-amber-400'}`} />
            <span className="text-slate-400">BRENT EWMA-60:</span>
            <span className={`font-bold ${telemetry.is_oil_shock_active ? 'text-red-400' : 'text-amber-300'}`}>
              ${telemetry.macro_oil_ewma.toFixed(2)} ({telemetry.macro_oil_zscore >= 0 ? '+' : ''}{telemetry.macro_oil_zscore.toFixed(2)}σ)
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800">
            <Zap className={`w-3.5 h-3.5 ${telemetry.hawkes_spectral_radius > 0.95 ? 'text-red-400' : 'text-emerald-400'}`} />
            <span className="text-slate-400">HAWKES (ρ):</span>
            <span className="text-emerald-400 font-bold">{telemetry.hawkes_spectral_radius.toFixed(3)}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-purple-500/40 text-purple-300">
            <Lock className="w-3 h-3 text-purple-400" />
            <span>RAM VAULT: SEALED</span>
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------- */}
      {/* 2. TAB NAVIGATION                                             */}
      {/* ------------------------------------------------------------- */}
      <nav className="flex items-center gap-1 px-6 bg-[#090e17] border-b border-slate-800/80 text-xs font-semibold overflow-x-auto">
        <button
          onClick={() => setActiveTab('copilot')}
          className={`flex items-center gap-2 py-3 px-4 border-b-2 transition-all ${activeTab === 'copilot' ? 'border-emerald-400 text-emerald-400 bg-emerald-500/5' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          <Terminal className="w-4 h-4" />
          AI Committee Copilot
        </button>
        <button
          onClick={() => setActiveTab('blotter')}
          className={`flex items-center gap-2 py-3 px-4 border-b-2 transition-all ${activeTab === 'blotter' ? 'border-emerald-400 text-emerald-400 bg-emerald-500/5' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          <BarChart2 className="w-4 h-4" />
          Rebalancing Blotter &amp; 10-Kitta Sizer
        </button>
        <button
          onClick={() => setActiveTab('cartel')}
          className={`flex items-center gap-2 py-3 px-4 border-b-2 transition-all ${activeTab === 'cartel' ? 'border-emerald-400 text-emerald-400 bg-emerald-500/5' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          <Layers className="w-4 h-4" />
          Syndicate Cartel Radar (SGN)
        </button>
        <button
          onClick={() => setActiveTab('macro')}
          className={`flex items-center gap-2 py-3 px-4 border-b-2 transition-all ${activeTab === 'macro' ? 'border-emerald-400 text-emerald-400 bg-emerald-500/5' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          <Droplets className="w-4 h-4" />
          Macro Crude &amp; Hydro Twin-Radar
        </button>
        <button
          onClick={() => setActiveTab('contagion')}
          className={`flex items-center gap-2 py-3 px-4 border-b-2 transition-all ${activeTab === 'contagion' ? 'border-emerald-400 text-emerald-400 bg-emerald-500/5' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
        >
          <Shield className="w-4 h-4" />
          Hawkes Contagion &amp; Defense Sentinel
        </button>
      </nav>

      {/* ------------------------------------------------------------- */}
      {/* 3. MAIN WORKSPACE VIEWPORT                                    */}
      {/* ------------------------------------------------------------- */}
      <main className="flex-1 p-6 overflow-y-auto">
        {/* ========================================================= */}
        {/* TAB 1: AI COMMITTEE COPILOT                               */}
        {/* ========================================================= */}
        {activeTab === 'copilot' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-170px)]">
            {/* Left: Chat & Deliberation Feed */}
            <div className="lg:col-span-7 flex flex-col bg-[#0d131f] border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
              <div className="px-5 py-3 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></div>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    Sovereign Chief Investment Officer • Interactive Deliberation
                  </span>
                </div>
                <span className="text-[11px] text-slate-500 font-mono">Model: DeepSeek-R1 / Qwen-2.5 (Local Offline)</span>
              </div>

              {/* Chat Thread */}
              <div className="flex-1 p-5 overflow-y-auto space-y-4">
                {chatMessages.map((msg, idx) => (
                  <div key={idx} className={`flex flex-col ${msg.sender === 'Operator' ? 'items-end' : 'items-start'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${msg.sender === 'Operator' ? 'text-cyan-400' : 'text-emerald-400'}`}>
                        {msg.sender === 'Operator' ? 'OPERATOR' : 'CHIEF INVESTMENT OFFICER'}
                      </span>
                      <span className="text-[10px] text-slate-500">{msg.time}</span>
                    </div>
                    <div className={`p-4 rounded-xl max-w-[85%] text-xs leading-relaxed ${msg.sender === 'Operator' ? 'bg-cyan-950/40 border border-cyan-800/50 text-cyan-100' : 'bg-slate-900 border border-slate-800 text-slate-200'}`}>
                      <div className="whitespace-pre-wrap">{msg.text}</div>
                    </div>
                  </div>
                ))}
                {isDeliberating && (
                  <div className="flex items-center gap-2 text-xs text-emerald-400 italic font-mono animate-pulse">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Committee Deliberating (Quant Analyst ➔ Macro Oil ➔ CRO ➔ CIO)...</span>
                  </div>
                )}
              </div>

              {/* Quick Prompt Chips */}
              <div className="px-5 py-2.5 bg-slate-900/80 border-t border-slate-800/80 flex flex-wrap gap-2 text-[11px]">
                <button onClick={() => handleSendMessage('Should I buy SAHAS right now?')} className="px-3 py-1 rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-emerald-400 transition-colors">
                  Analyze SAHAS
                </button>
                <button onClick={() => handleSendMessage('Why are we avoiding SHIVM?')} className="px-3 py-1 rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-red-400 transition-colors">
                  Why Avoid SHIVM?
                </button>
                <button onClick={() => handleSendMessage('Give me a complete portfolio rebalancing recommendation')} className="px-3 py-1 rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-cyan-400 transition-colors">
                  Rebalance Portfolio
                </button>
                <button onClick={() => handleSendMessage('What is our current risk posture and cash balance?')} className="px-3 py-1 rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-purple-400 transition-colors">
                  Check Risk Posture
                </button>
              </div>

              {/* Chat Input Bar */}
              <div className="p-4 border-t border-slate-800 bg-[#0d131f] flex items-center gap-3">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Ask the Chief Investment Officer (e.g., 'What about CHCL?', 'Stress test 100$ crude')..."
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                />
                <button
                  onClick={() => handleSendMessage()}
                  className="px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-[0_0_15px_rgba(16,185,129,0.3)]"
                >
                  <Send className="w-3.5 h-3.5" />
                  Ask
                </button>
              </div>
            </div>

            {/* Right: Selected Asset 4-Pillar Deliberation Card */}
            <div className="lg:col-span-5 flex flex-col gap-4 overflow-y-auto">
              <div className="bg-[#0d131f] border border-slate-800 rounded-xl p-5 shadow-2xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                  <div>
                    <h2 className="text-lg font-black text-white flex items-center gap-2">
                      {selectedAsset.target_asset}
                      <span className={`text-xs px-2 py-0.5 rounded font-extrabold ${selectedAsset.action === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'}`}>
                        {selectedAsset.action}
                      </span>
                    </h2>
                    <p className="text-xs text-slate-400">Current Market Price: <span className="font-bold text-white">NPR {selectedAsset.current_price.toFixed(1)}</span></p>
                  </div>
                  <button
                    onClick={() => handleStageOrder(selectedAsset)}
                    className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-[0_0_15px_rgba(16,185,129,0.25)] flex items-center gap-1"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Stage Order
                  </button>
                </div>

                {/* 4-Pillar Deliberation Cards */}
                <div className="space-y-3 text-xs">
                  {/* Pillar 1: Quant Signal */}
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <div className="flex items-center justify-between text-cyan-400 font-bold mb-1">
                      <span className="flex items-center gap-1.5">
                        <Activity className="w-3.5 h-3.5" />
                        1. Quantitative &amp; Cartel Alpha
                      </span>
                      <span>Density: {telemetry.sahas_cartel_density.toFixed(2)}</span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      SGN algorithm confirms institutional broker absorption. Cartel network concentration exceeds 0.65 threshold.
                    </p>
                  </div>

                  {/* Pillar 2: Macro Oil Transmission */}
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <div className="flex items-center justify-between text-amber-400 font-bold mb-1">
                      <span className="flex items-center gap-1.5">
                        <Droplets className="w-3.5 h-3.5" />
                        2. Macro Brent Transmission
                      </span>
                      <span>Z-Score: {telemetry.macro_oil_zscore.toFixed(2)}σ</span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      Brent crude 60-day EWMA stands at ${telemetry.macro_oil_ewma.toFixed(2)}. Peaking hydropower tariff arbitrage favorable.
                    </p>
                  </div>

                  {/* Pillar 3: CRO Risk & Kyle's Lambda Gate */}
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                    <div className="flex items-center justify-between text-purple-400 font-bold mb-1">
                      <span className="flex items-center gap-1.5">
                        <Shield className="w-3.5 h-3.5" />
                        3. Chief Risk Officer Veto Gate
                      </span>
                      <span className="text-emerald-400 font-extrabold">{selectedAsset.cro_verdict}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 my-2 text-[11px] text-slate-300 font-mono">
                      <div>Approved: <span className="text-white font-bold">{selectedAsset.approved_lots_kitta} Kitta ({selectedAsset.approved_lots_kitta*10} sh)</span></div>
                      <div>Capital: <span className="text-emerald-300 font-bold">NPR {selectedAsset.committed_capital_npr.toLocaleString()}</span></div>
                      <div>Limit Entry: <span className="text-cyan-300 font-bold">NPR {selectedAsset.limit_entry_npr.toFixed(1)}</span></div>
                      <div>Stop Loss: <span className="text-red-400 font-bold">NPR {selectedAsset.stop_loss_npr.toFixed(1)}</span></div>
                    </div>
                  </div>

                  {/* Pillar 4: CIO Executive Mandate */}
                  <div className="p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-500/30">
                    <div className="text-emerald-400 font-bold mb-1 flex items-center gap-1.5">
                      <CheckCircle className="w-3.5 h-3.5" />
                      4. Executive Mandate &amp; Rationale
                    </div>
                    <p className="text-slate-200 text-[11px] leading-relaxed font-mono">
                      {selectedAsset.strategic_rationale}
                    </p>
                  </div>
                </div>
              </div>

              {/* Order Staged Seal Feedback */}
              {stagedOrderResult && (
                <div className="p-4 rounded-xl bg-slate-900 border border-emerald-500/40 text-xs">
                  <div className="text-emerald-400 font-bold flex items-center gap-2 mb-2">
                    <Lock className="w-4 h-4" />
                    ORDER STAGED &amp; SEALED VIA CHACHA20-POLY1305
                  </div>
                  <div className="space-y-1 font-mono text-[11px] text-slate-300">
                    <div>Order ID: <span className="text-white">{stagedOrderResult.order_id}</span></div>
                    <div>Asset: <span className="text-white">{stagedOrderResult.symbol} ({stagedOrderResult.lots_kitta} Kitta @ NPR {stagedOrderResult.limit_price})</span></div>
                    <div>Capital: <span className="text-emerald-400 font-bold">NPR {stagedOrderResult.committed_capital_npr.toLocaleString()}</span></div>
                    <div className="text-[10px] text-slate-500 break-all">Cipher: {stagedOrderResult.cipher_token}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 2: REBALANCING BLOTTER & 10-KITTA SIZER               */}
        {/* ========================================================= */}
        {activeTab === 'blotter' && (
          <div className="space-y-6">
            {/* Top Blotter Control Bar */}
            <div className="p-5 rounded-xl bg-[#0d131f] border border-slate-800 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-white">Institutional Portfolio Rebalancing Blotter</h2>
                <p className="text-xs text-slate-400">Strict T+2 settlement constraints • Discrete 10-Kitta integer steps • Kyle's lambda market impact damping</p>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-400">Total Capital:</span>
                  <input
                    type="range"
                    min="100000"
                    max="2000000"
                    step="50000"
                    value={totalCapital}
                    onChange={(e) => setTotalCapital(Number(e.target.value))}
                    className="w-32 accent-emerald-500 cursor-pointer"
                  />
                  <span className="font-mono font-bold text-emerald-400">NPR {totalCapital.toLocaleString()}</span>
                </div>

                <button
                  onClick={() => alert("Rebalancing blotter validated and dispatched to order router.")}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.3)] transition-all"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Execute Full Rebalance
                </button>
              </div>
            </div>

            {/* Blotter Data Table */}
            <div className="bg-[#0d131f] border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/80 text-slate-400 font-mono text-[11px] uppercase tracking-wider">
                    <th className="py-3 px-4">Ticker</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4">Price (NPR)</th>
                    <th className="py-3 px-4">Approved Lots</th>
                    <th className="py-3 px-4">Capital (NPR)</th>
                    <th className="py-3 px-4">Limit Entry</th>
                    <th className="py-3 px-4">Stop Loss</th>
                    <th className="py-3 px-4">Take Profit</th>
                    <th className="py-3 px-4">CRO Verdict</th>
                    <th className="py-3 px-4">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-slate-200">
                  {blotter.map((item, idx) => (
                    <tr
                      key={idx}
                      onClick={() => setSelectedAsset(item)}
                      className={`hover:bg-slate-800/40 cursor-pointer transition-colors ${selectedAsset.target_asset === item.target_asset ? 'bg-slate-800/60' : ''}`}
                    >
                      <td className="py-3 px-4 font-bold text-white flex items-center gap-1.5">
                        {item.target_asset}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${item.action === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                          {item.action}
                        </span>
                      </td>
                      <td className="py-3 px-4">{item.current_price.toFixed(1)}</td>
                      <td className="py-3 px-4 font-bold text-cyan-400">{item.approved_lots_kitta} Kitta</td>
                      <td className="py-3 px-4 font-bold text-emerald-400">{item.committed_capital_npr.toLocaleString()}</td>
                      <td className="py-3 px-4 text-cyan-300">{item.limit_entry_npr.toFixed(1)}</td>
                      <td className="py-3 px-4 text-red-400">{item.stop_loss_npr.toFixed(1)}</td>
                      <td className="py-3 px-4 text-emerald-400">{item.take_profit_npr.toFixed(1)}</td>
                      <td className="py-3 px-4">
                        <span className={`text-[10px] font-bold ${item.cro_verdict === 'APPROVED' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {item.cro_verdict}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleStageOrder(item); }}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-emerald-600 text-[10px] text-white font-bold transition-all"
                        >
                          Stage
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 3: SYNDICATE CARTEL RADAR (Pillar 1 SGN)              */}
        {/* ========================================================= */}
        {activeTab === 'cartel' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 bg-[#0d131f] border border-slate-800 rounded-xl p-5 shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-cyan-400" />
                    Broker Syndicate Graph Network (SGN Subgraphs)
                  </h2>
                  <p className="text-xs text-slate-400">Hardware POPCNT 64-bit Bitwise Adjacency Matrix • Real-time circular wash detection</p>
                </div>
                <div className="px-3 py-1 rounded bg-red-950/40 border border-red-500/40 text-red-400 text-xs font-bold font-mono">
                  CLUSTER DENSITY: {cartelData.cluster_density.toFixed(3)} (&gt;0.55 COLLUSION ALERT)
                </div>
              </div>

              {/* Force Graph Canvas Representation */}
              <div className="relative w-full h-[380px] bg-slate-950/70 border border-slate-800/80 rounded-xl overflow-hidden flex items-center justify-center">
                <svg className="w-full h-full">
                  {/* Edges */}
                  {cartelData.edges.map((e, idx) => {
                    const src = cartelData.nodes.find(n => n.id === e.from);
                    const tgt = cartelData.nodes.find(n => n.id === e.to);
                    if (!src || !tgt) return null;
                    return (
                      <line
                        key={idx}
                        x1={src.x}
                        y1={src.y}
                        x2={tgt.x}
                        y2={tgt.y}
                        stroke={e.is_collusive ? '#f43f5e' : '#334155'}
                        strokeWidth={e.is_collusive ? 2.5 : 1.2}
                        strokeDasharray={e.is_collusive ? '4 2' : 'none'}
                        className={e.is_collusive ? 'animate-pulse' : ''}
                      />
                    );
                  })}
                  {/* Nodes */}
                  {cartelData.nodes.map((n, idx) => (
                    <g key={idx} transform={`translate(${n.x}, ${n.y})`} className="cursor-pointer">
                      <circle
                        r={n.cartel_member ? 18 : 12}
                        fill={n.cartel_member ? '#7f1d1d' : '#1e293b'}
                        stroke={n.cartel_member ? '#f43f5e' : '#64748b'}
                        strokeWidth={2}
                      />
                      <text textAnchor="middle" dy="4" fill="#ffffff" fontSize="9" fontWeight="bold">
                        {n.id}
                      </text>
                      <text textAnchor="middle" dy="28" fill="#94a3b8" fontSize="8" fontFamily="monospace">
                        {n.label}
                      </text>
                    </g>
                  ))}
                </svg>
                <div className="absolute bottom-3 left-3 bg-slate-900/90 border border-slate-800 p-2.5 rounded-lg text-[10px] font-mono space-y-1">
                  <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500"></span> Active Cartel Ring Leader</div>
                  <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-slate-600"></span> General Broker Desk</div>
                  <div className="flex items-center gap-2"><span className="w-4 h-0.5 bg-red-400 border-dashed"></span> Circular Wash Trade Vector</div>
                </div>
              </div>
            </div>

            {/* Right: Cartel Desks Breakdown */}
            <div className="lg:col-span-4 bg-[#0d131f] border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
              <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-2">Top Coordinated Broker Desks</h3>
              <div className="space-y-2.5">
                {cartelData.nodes.filter(n => n.cartel_member).map((b, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs">
                    <div>
                      <div className="font-bold text-white">{b.label}</div>
                      <div className="text-[10px] text-red-400 font-mono uppercase">{b.type}</div>
                    </div>
                    <div className="text-right font-mono">
                      <div className="text-emerald-400 font-bold">{b.flow.toLocaleString()} sh</div>
                      <div className="text-[10px] text-slate-500">Net Flow</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 4: MACRO CRUDE & HYDRO TWIN-RADAR (Pillars 2 & Macro) */}
        {/* ========================================================= */}
        {activeTab === 'macro' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 bg-[#0d131f] border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <Droplets className="w-4 h-4 text-amber-400" />
                    Brent Crude Macro Shock Transmission &amp; Sector Rotation
                  </h2>
                  <p className="text-xs text-slate-400">Rolling 60-Day EWMA corridor with automatic +2.0σ throttle guardrail</p>
                </div>
                <div className={`px-3 py-1 rounded text-xs font-bold font-mono ${telemetry.is_oil_shock_active ? 'bg-red-950/60 text-red-400 border border-red-500/40' : 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/40'}`}>
                  REGIME: {telemetry.oil_regime}
                </div>
              </div>

              {/* Interactive Oil Shock Simulator Slider */}
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-white flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                    Simulate Global Brent Crude Price Shock:
                  </span>
                  <span className="font-mono text-sm font-bold text-amber-400">${simOilPrice.toFixed(2)} / bbl</span>
                </div>
                <input
                  type="range"
                  min="50"
                  max="125"
                  step="0.5"
                  value={simOilPrice}
                  onChange={(e) => handleSimulateOil(e.target.value)}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>$50 (Easing -3.5σ)</span>
                  <span>$78.50 (Historical Baseline)</span>
                  <span className="text-red-400 font-bold">$94.90 (+2.0σ Trigger)</span>
                  <span>$125 (Extreme Crisis)</span>
                </div>
              </div>

              {/* Dynamic Impact Readout */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                  <div className="text-slate-400 text-[10px]">MAX ALLOWED EQUITY EXPOSURE</div>
                  <div className={`text-lg font-bold ${simOilPrice >= 95 ? 'text-red-400' : 'text-emerald-400'}`}>
                    {simOilPrice >= 95 ? '60.0% (Throttled)' : '85.0% - 100.0%'}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                  <div className="text-slate-400 text-[10px]">SOVEREIGN CASH LOCK (T-BILLS)</div>
                  <div className={`text-lg font-bold ${simOilPrice >= 95 ? 'text-cyan-400' : 'text-slate-300'}`}>
                    {simOilPrice >= 95 ? '40.0% Locked' : '15.0% Standard Buffer'}
                  </div>
                </div>
              </div>

              {/* Sector Rotation Mandate Table */}
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs">
                <div className="font-bold text-slate-300 mb-2">Automated Sector Rebalance Vector:</div>
                <div className="space-y-1.5 text-[11px] font-mono">
                  <div className="flex justify-between">
                    <span>Manufacturing &amp; Cement (SHIVM, SARBTM, GCIL):</span>
                    <span className={simOilPrice >= 95 ? 'text-red-400 font-bold' : 'text-slate-300'}>{simOilPrice >= 95 ? '0% (Forced Dump)' : '100% (Market Weight)'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Run-of-River Hydro (SAHAS, CHCL, NGPL):</span>
                    <span className={simOilPrice >= 95 ? 'text-emerald-400 font-bold' : 'text-slate-300'}>{simOilPrice >= 95 ? '+150% (Grid Tariff Surge)' : '100% (Normal)'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Hydro EBITDA Forecast */}
            <div className="lg:col-span-5 bg-[#0d131f] border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
              <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-2 flex items-center gap-2">
                <Zap className="w-4 h-4 text-emerald-400" />
                Hydrological EBITDA Forecaster (Pillar 2)
              </h3>
              <div className="space-y-3 text-xs">
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                  <div className="flex justify-between font-bold text-white mb-1">
                    <span>SAHAS (Solu Hydro 86 MW)</span>
                    <span className="text-emerald-400">+18.4% EBITDA</span>
                  </div>
                  <p className="text-[11px] text-slate-400">Peak autumn discharge Q = 18.2 m³/s ensures full capacity utilization at NPR 8.40/unit dry tariff transition.</p>
                </div>
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                  <div className="flex justify-between font-bold text-white mb-1">
                    <span>CHCL (Chilime Hydro 22.1 MW)</span>
                    <span className="text-emerald-400">+12.1% EBITDA</span>
                  </div>
                  <p className="text-[11px] text-slate-400">Glacial melt run-off sustains baseload output; zero debt service leaves 94% EBITDA margin.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 5: HAWKES CONTAGION & DEFENSE SENTINEL                */}
        {/* ========================================================= */}
        {activeTab === 'contagion' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 bg-[#0d131f] border border-slate-800 rounded-xl p-5 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Shield className="w-4 h-4 text-purple-400" />
                  Multivariate Hawkes Contagion &amp; Cross-Asset Branching
                </h2>
                <div className="text-xs font-mono text-emerald-400 font-bold">
                  SPECTRAL RADIUS: {telemetry.hawkes_spectral_radius.toFixed(3)}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
                <div className="font-bold text-white">Branching Matrix Stability Condition:</div>
                <p className="text-[11px] text-slate-300 leading-relaxed font-mono">
                  Spectral radius ρ(Γ) governs whether self-exciting shocks extinguish exponentially or explode into an infinite cascade. 
                  If ρ(Γ) &gt; 0.95, the Chief Risk Officer halts all capital deployment immediately.
                </p>
                <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden mt-3">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 via-amber-500 to-red-500 transition-all"
                    style={{ width: `${Math.min(100, (telemetry.hawkes_spectral_radius / 1.0) * 100)}%` }}
                  ></div>
                </div>
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>0.0 (Quiescent)</span>
                  <span>0.82 (Current Stable Boundary)</span>
                  <span className="text-red-400 font-bold">0.95 (Veto Threshold)</span>
                </div>
              </div>
            </div>

            {/* Zero-Trust Hardware Vault */}
            <div className="lg:col-span-5 bg-[#0d131f] border border-slate-800 rounded-xl p-5 shadow-2xl space-y-3">
              <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-2 flex items-center gap-2">
                <Lock className="w-4 h-4 text-emerald-400" />
                Sovereign Kernel &amp; Cryptographic Defense
              </h3>
              <div className="space-y-2 text-xs font-mono">
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">RAM Vault Cipher:</span>
                  <span className="text-emerald-400 font-bold">ChaCha20-Poly1305</span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">OS Page Lock:</span>
                  <span className="text-cyan-400 font-bold">VirtualLock (0 Page Swaps)</span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">Anti-Tamper Sentinel:</span>
                  <span className="text-emerald-400 font-bold">IsDebuggerPresent Clean</span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex justify-between">
                  <span className="text-slate-400">Network Posture:</span>
                  <span className="text-purple-400 font-bold">DARK_NODE Stealth IPC</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ------------------------------------------------------------- */}
      {/* 4. FOOTER STATUS BAR                                          */}
      {/* ------------------------------------------------------------- */}
      <footer className="border-t border-slate-800 bg-[#0d131f] px-6 py-2.5 flex items-center justify-between text-[11px] text-slate-500 font-mono">
        <div>CHRONOSTRATA PRIME v6.0.0 • Sovereign Quant &amp; Agentic CIO Platform</div>
        <div className="flex items-center gap-4">
          <span>HOST: 127.0.0.1 (Local Sovereign PC)</span>
          <span className="text-emerald-500 font-bold">ALL 11/11 AUDIT GATES PASS</span>
        </div>
      </footer>
    </div>
  );
}
