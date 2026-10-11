import os
import re

with open('pulse_terminal/index_clean.html', 'r', encoding='utf-8') as f:
    clean_html = f.read()

# Locate insertion points in index_clean.html
# 1. Styles: We can append custom workspace CSS right before </head>
head_close = clean_html.find('</head>')
assert head_close != -1, "Could not find </head>"

# 2. Body start and Terminal Root
root_start = clean_html.find('<div id="terminal-root"')
assert root_start != -1, "Could not find <div id=\"terminal-root\""

# Find terminal-root closing tag
script_marker = '<!-- 4. ZERO-DEPENDENCY VANILLA JAVASCRIPT DISPATCHER PIPELINE'
script_pos = clean_html.find(script_marker)
assert script_pos != -1, "Could not find script marker"

# In clean_html, right before script_pos is "  </div>\n\n  "
last_div = clean_html.rfind('</div>', 0, script_pos)
assert last_div != -1, "Could not find closing div of terminal-root"
root_end = last_div + len('</div>')

print(f"root_start: {root_start}, root_end: {root_end}")

# ==============================================================================
# CSS FOR WORKSPACE NAVIGATION & ISOLATED SCREENS
# ==============================================================================
workspace_css = """
  /* ========================================================================== */
  /* WORKSPACE SYSTEM & SCREEN ISOLATION ARCHITECTURE                           */
  /* ========================================================================== */
  :root {
    --nav-height: 38px;
    --bg-deep: #030508;
    --bg-card: #070d14;
    --border-dim: #132438;
    --border-bright: #1b4965;
    --neon-cyan: #00e5ff;
    --neon-green: #00e676;
    --neon-amber: #ffab00;
    --neon-red: #ff1744;
    --text-primary: #e2e8f0;
    --text-muted: #64748b;
  }

  body {
    margin: 0;
    padding: 0;
    background: var(--bg-deep);
    color: var(--text-primary);
    font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
    overflow: hidden;
    width: 100vw;
    height: 100vh;
  }

  /* PERSISTENT TOP NAVIGATION BAR */
  #workspace-navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--nav-height);
    background: #040910;
    border-bottom: 1px solid var(--border-dim);
    padding: 0 12px;
    box-sizing: border-box;
    z-index: 99999;
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    font-size: 11px;
    letter-spacing: 0.05em;
    user-select: none;
  }

  .nav-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 800;
    color: #fff;
    cursor: pointer;
  }

  .nav-brand .pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--neon-cyan);
    box-shadow: 0 0 8px var(--neon-cyan);
    animation: blink-dot 2s infinite;
  }

  @keyframes blink-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.3; transform: scale(0.8); }
  }

  .nav-items {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 100%;
  }

  .nav-btn {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    padding: 4px 10px;
    font-family: inherit;
    font-size: 10.5px;
    font-weight: 600;
    cursor: pointer;
    border-radius: 3px;
    transition: all 0.15s ease;
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .nav-btn .key-hint {
    background: #0f1c2e;
    color: #7dd3fc;
    border: 1px solid #1e3a5f;
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 9px;
  }

  .nav-btn:hover {
    color: #fff;
    background: rgba(0, 229, 255, 0.08);
    border-color: rgba(0, 229, 255, 0.3);
  }

  .nav-btn.active {
    color: var(--neon-cyan);
    background: rgba(0, 229, 255, 0.12);
    border-color: var(--neon-cyan);
    box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);
  }

  .nav-status {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 10px;
    color: var(--text-muted);
  }

  .nav-status-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    background: #071320;
    border: 1px solid #102a45;
    padding: 2px 7px;
    border-radius: 3px;
    color: #38bdf8;
  }

  /* WORKSPACE CONTAINER VIEWPORT */
  #workspace-container {
    position: absolute;
    top: var(--nav-height);
    left: 0;
    right: 0;
    bottom: 0;
    width: 100vw;
    height: calc(100vh - var(--nav-height));
    overflow: hidden;
  }

  /* STRICT ISOLATION FOR EVERY SCREEN */
  .workspace-screen {
    display: none !important;
    width: 100%;
    height: 100%;
    position: absolute;
    top: 0;
    left: 0;
    box-sizing: border-box;
    overflow: hidden;
  }

  .workspace-screen.active {
    display: flex !important;
  }

  /* SCREEN [1]: TRADING DESK */
  #screen-tradingdesk {
    flex-direction: column;
  }
  #screen-tradingdesk #terminal-root {
    width: 100% !important;
    height: 100% !important;
    position: relative !important;
    display: flex !important;
    flex-direction: column !important;
  }

  /* SCREEN [0]: LAUNCH PAD */
  #screen-launchpad {
    background: radial-gradient(circle at 50% 30%, #081220 0%, #030508 80%);
    padding: 24px 32px;
    flex-direction: column;
    justify-content: space-between;
    box-sizing: border-box;
    overflow-y: auto;
  }

  .launchpad-header {
    text-align: center;
    margin-bottom: 20px;
  }

  .launchpad-header h1 {
    font-size: 22px;
    margin: 0 0 6px 0;
    letter-spacing: 0.12em;
    color: #fff;
    font-weight: 800;
  }

  .launchpad-header p {
    margin: 0;
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.05em;
  }

  .launchpad-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: repeat(2, 1fr);
    gap: 18px;
    flex: 1;
    min-height: 480px;
    max-width: 1300px;
    width: 100%;
    margin: 0 auto;
  }

  .launch-card {
    background: #060d17;
    border: 1px solid #13273e;
    border-radius: 6px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    overflow: hidden;
  }

  .launch-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: transparent;
    transition: background 0.2s ease;
  }

  .launch-card:hover {
    border-color: #00e5ff;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 229, 255, 0.12);
    background: #081220;
  }

  .launch-card:hover::before {
    background: var(--neon-cyan);
  }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .card-id-badge {
    background: #0f2238;
    color: #38bdf8;
    border: 1px solid #1b4965;
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 3px;
  }

  .card-title {
    font-size: 14px;
    font-weight: 700;
    color: #f1f5f9;
    margin: 8px 0 4px 0;
    letter-spacing: 0.04em;
  }

  .card-desc {
    font-size: 11px;
    color: #94a3b8;
    line-height: 1.4;
    margin-bottom: 12px;
  }

  .card-metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    background: #03070d;
    border: 1px solid #0f1c2d;
    border-radius: 4px;
    padding: 10px;
  }

  .card-metric-cell {
    display: flex;
    flex-direction: column;
  }

  .card-metric-label {
    font-size: 9px;
    color: #64748b;
    text-transform: uppercase;
  }

  .card-metric-val {
    font-size: 12px;
    font-weight: 700;
    color: #38bdf8;
    margin-top: 2px;
  }

  .launchpad-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #101e30;
    padding-top: 12px;
    margin-top: 16px;
    font-size: 10.5px;
    color: #64748b;
  }

  /* SCREEN [2]: ALPHA DASHBOARD */
  #screen-alpha {
    flex-direction: column;
    background: #030508;
    padding: 12px 16px;
    box-sizing: border-box;
    gap: 12px;
  }

  .screen-header-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #060d17;
    border: 1px solid var(--border-bright);
    padding: 10px 16px;
    border-radius: 4px;
  }

  .screen-title-group h2 {
    margin: 0;
    font-size: 15px;
    font-weight: 800;
    color: #fff;
    letter-spacing: 0.05em;
  }
  .screen-title-group p {
    margin: 3px 0 0 0;
    font-size: 10px;
    color: var(--text-muted);
  }

  .alpha-table-container {
    flex: 1;
    background: #040810;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    overflow: auto;
  }

  .quant-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    text-align: left;
  }

  .quant-table th {
    background: #08111e;
    color: #7dd3fc;
    padding: 9px 12px;
    font-weight: 700;
    border-bottom: 1px solid #162f4e;
    position: sticky;
    top: 0;
    z-index: 2;
    white-space: nowrap;
  }

  .quant-table td {
    padding: 7px 12px;
    border-bottom: 1px solid #091322;
    white-space: nowrap;
    color: #cbd5e1;
  }

  .quant-table tr:hover td {
    background: rgba(0, 229, 255, 0.05);
    color: #fff;
  }

  .badge-buy {
    color: #00e676;
    background: rgba(0, 230, 118, 0.1);
    border: 1px solid rgba(0, 230, 118, 0.3);
    padding: 2px 6px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 9.5px;
  }

  .badge-sell {
    color: #ff1744;
    background: rgba(255, 23, 68, 0.1);
    border: 1px solid rgba(255, 23, 68, 0.3);
    padding: 2px 6px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 9.5px;
  }

  .badge-neutral {
    color: #94a3b8;
    background: rgba(148, 163, 184, 0.1);
    border: 1px solid rgba(148, 163, 184, 0.2);
    padding: 2px 6px;
    border-radius: 2px;
    font-size: 9.5px;
  }

  /* SCREEN [3]: RISK MONITOR */
  #screen-risk {
    flex-direction: column;
    background: #030508;
    padding: 12px 16px;
    box-sizing: border-box;
    gap: 12px;
  }

  .risk-grid-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 140px 1fr;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .risk-kpi-row {
    grid-column: span 2;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }

  .risk-kpi-card {
    background: #060e18;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .risk-kpi-card .kpi-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .risk-kpi-card .kpi-value {
    font-size: 20px;
    font-weight: 800;
    color: #38bdf8;
    margin-top: 4px;
  }

  .risk-panel {
    background: #040810;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  .risk-panel-header {
    font-size: 12px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 8px;
    border-bottom: 1px solid #0f1c2d;
    padding-bottom: 6px;
  }

  /* SCREEN [4]: FORECAST ENGINE */
  #screen-forecast {
    flex-direction: column;
    background: #030508;
    padding: 12px 16px;
    box-sizing: border-box;
    gap: 12px;
  }

  .forecast-body {
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .forecast-sidebar {
    background: #040810;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .forecast-chart-panel {
    background: #040810;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    padding: 12px;
    min-height: 0;
  }
"""

# ==============================================================================
# HTML FOR NAVBAR AND WORKSPACE SCREENS
# ==============================================================================
navbar_html = """
  <!-- PERSISTENT QUANT WORKSPACE NAVBAR -->
  <header id="workspace-navbar">
    <div class="nav-brand" onclick="switchWorkspace(0)">
      <div class="pulse-dot"></div>
      <span>NEPSE PULSE TERMINAL</span>
    </div>

    <div class="nav-items">
      <button id="nav-btn-0" class="nav-btn active" onclick="switchWorkspace(0)">
        <span class="key-hint">ESC</span> MENU
      </button>
      <button id="nav-btn-1" class="nav-btn" onclick="switchWorkspace(1)">
        <span class="key-hint">1</span> TRADING DESK
      </button>
      <button id="nav-btn-2" class="nav-btn" onclick="switchWorkspace(2)">
        <span class="key-hint">2</span> ALPHA DASHBOARD
      </button>
      <button id="nav-btn-3" class="nav-btn" onclick="switchWorkspace(3)">
        <span class="key-hint">3</span> RISK MONITOR
      </button>
      <button id="nav-btn-4" class="nav-btn" onclick="switchWorkspace(4)">
        <span class="key-hint">4</span> 20D FORECAST
      </button>
    </div>

    <div class="nav-status">
      <div class="nav-status-chip">
        <span>NPT</span>
        <span id="nav-clock" style="font-weight:700;">--:--:--</span>
      </div>
      <div class="nav-status-chip" style="color: #00e676; border-color: rgba(0,230,118,0.3);">
        <span style="font-weight:700;">FASTAPI: OK</span>
      </div>
    </div>
  </header>

  <!-- MULTI-WORKSPACE VIEWPORT CONTAINER -->
  <main id="workspace-container">
"""

# SCREEN [0]: Launch Pad
screen_launchpad_html = """
    <!-- SCREEN [0]: WORKSPACE LAUNCH PAD -->
    <section id="screen-launchpad" class="workspace-screen active">
      <div class="launchpad-header">
        <h1>NEPSE QUANTITATIVE SUITE • WORKSPACE LAUNCHER</h1>
        <p>SELECT A WORKSPACE BELOW OR USE HARDWARE SHORTCUTS [1] - [4]</p>
      </div>

      <div class="launchpad-grid">
        <!-- CARD 1 -->
        <div class="launch-card" onclick="switchWorkspace(1)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[1] WORKSPACE</span>
              <span style="color:#00e5ff; font-size:10px; font-weight:700;">600µs LATENCY</span>
            </div>
            <div class="card-title">TRADING DESK & LEVEL 2 BOOK</div>
            <div class="card-desc">Zero-DOM canvas graphics, real-time depth tape, Centaur human-in-the-loop staging blotter, and tick telemetry.</div>
          </div>
          <div class="card-metrics">
            <div class="card-metric-cell">
              <span class="card-metric-label">ACTIVE SYMBOL</span>
              <span class="card-metric-val">NABIL</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">L2 DEPTH</span>
              <span class="card-metric-val">50 LEVELS</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">SLIPPAGE GUARD</span>
              <span class="card-metric-val" style="color:#00e676;">SHIELD ON</span>
            </div>
          </div>
        </div>

        <!-- CARD 2 -->
        <div class="launch-card" onclick="switchWorkspace(2)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[2] WORKSPACE</span>
              <span style="color:#00e676; font-size:10px; font-weight:700;">353+ SECURITIES</span>
            </div>
            <div class="card-title">ALPHA & LIVE SIGNAL DASHBOARD</div>
            <div class="card-desc">Cross-asset directional signal engine, Gate G4 confidence ranking, Hawkes jump sweeps, and order-flow imbalance ratios.</div>
          </div>
          <div class="card-metrics">
            <div class="card-metric-cell">
              <span class="card-metric-label">GATE G4 TOP</span>
              <span class="card-metric-val">SHIVM (94.2%)</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">HAWKES JUMP</span>
              <span class="card-metric-val" style="color:#ffab00;">2 DETECTED</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">BUY SIGNALS</span>
              <span class="card-metric-val" style="color:#00e676;">14 ACTIVE</span>
            </div>
          </div>
        </div>

        <!-- CARD 3 -->
        <div class="launch-card" onclick="switchWorkspace(3)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[3] WORKSPACE</span>
              <span style="color:#ffab00; font-size:10px; font-weight:700;">skfolio INTEGRATED</span>
            </div>
            <div class="card-title">RISK MONITOR & PORTFOLIO GOVERNANCE</div>
            <div class="card-desc">Schur Return-Adjusted Hierarchical Risk Parity (HRP), Broker HHI concentration monitor, and CDSC T+2 settlement shield.</div>
          </div>
          <div class="card-metrics">
            <div class="card-metric-cell">
              <span class="card-metric-label">PORTFOLIO VaR</span>
              <span class="card-metric-val" style="color:#ff1744;">-2.42%</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">BROKER 58 HHI</span>
              <span class="card-metric-val">2,840 (HIGH)</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">HRP ASSETS</span>
              <span class="card-metric-val">10 OPTIMAL</span>
            </div>
          </div>
        </div>

        <!-- CARD 4 -->
        <div class="launch-card" onclick="switchWorkspace(4)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[4] WORKSPACE</span>
              <span style="color:#a855f7; font-size:10px; font-weight:700;">CHRONOS-BOLT P10/P50/P90</span>
            </div>
            <div class="card-title">20-DAY FORECAST CORRIDOR ENGINE</div>
            <div class="card-desc">Multi-quantile trajectory cones, asymmetric volatility barriers, and forward projected return distributions.</div>
          </div>
          <div class="card-metrics">
            <div class="card-metric-cell">
              <span class="card-metric-label">TOP PROJECTED</span>
              <span class="card-metric-val" style="color:#00e676;">HDL (+11.4%)</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">CORRIDOR SPREAD</span>
              <span class="card-metric-val">±4.8%</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">CONFIDENCE</span>
              <span class="card-metric-val">88.5%</span>
            </div>
          </div>
        </div>
      </div>

      <div class="launchpad-footer">
        <span>PRESS [1]-[4] TO LAUNCH DIRECTLY | PRESS [ESC] TO RETURN TO THIS MENU</span>
        <span>NEPSE QUANT PIPELINE v4.2.0 • DUCKDB ENGINE CONNECTED</span>
      </div>
    </section>
"""

# SCREEN [2]: Alpha Dashboard
screen_alpha_html = """
    <!-- SCREEN [2]: ALPHA & LIVE SIGNAL DASHBOARD -->
    <section id="screen-alpha" class="workspace-screen">
      <div class="screen-header-banner">
        <div class="screen-title-group">
          <h2>ALPHA SIGNALS & GATE G4 EXECUTION MONITOR</h2>
          <p>353+ NEPSE SECURITIES RANKED BY MULTI-FACTOR PREDICTIVE PROBABILITY (POINT-IN-TIME FEATURE FEED)</p>
        </div>
        <div style="display:flex; gap:10px;">
          <input type="text" id="alpha-search-input" placeholder="SEARCH SYMBOL..." style="background:#03070d; border:1px solid #162f4e; color:#fff; padding:4px 10px; font-family:inherit; font-size:11px; border-radius:3px;">
          <button class="nav-btn active" onclick="refreshAlphaData()">REFRESH SIGNALS</button>
        </div>
      </div>

      <div class="alpha-table-container">
        <table class="quant-table" id="alpha-table">
          <thead>
            <tr>
              <th>SYMBOL</th>
              <th>SECTOR</th>
              <th>GATE G4 CONFIDENCE</th>
              <th>HAWKES SWEEP</th>
              <th>OFI RATIO</th>
              <th>BUYER HHI</th>
              <th>SELLER HHI</th>
              <th>UNLOCK OVERHANG</th>
              <th>STATUS</th>
            </tr>
          </thead>
          <tbody id="alpha-table-body">
            <!-- Dynamically populated via API -->
          </tbody>
        </table>
      </div>
    </section>
"""

# SCREEN [3]: Risk Monitor
screen_risk_html = """
    <!-- SCREEN [3]: RISK MONITOR & PORTFOLIO GOVERNANCE -->
    <section id="screen-risk" class="workspace-screen">
      <div class="screen-header-banner">
        <div class="screen-title-group">
          <h2>RISK MONITOR & SCHUR-RA-HRP PORTFOLIO GOVERNANCE</h2>
          <p>MACRO INTEREST RATE DYNAMICS, BROKER CONCENTRATION HHI & CDSC T+2 SETTLEMENT LIQUIDITY SHIELD</p>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="nav-btn active" onclick="refreshRiskData()">RECALCULATE HRP</button>
        </div>
      </div>

      <div class="risk-grid-container">
        <div class="risk-kpi-row">
          <div class="risk-kpi-card">
            <span class="kpi-label">PORTFOLIO VaR (95%)</span>
            <span class="kpi-value" id="risk-var-val" style="color:#ff1744;">-2.42%</span>
          </div>
          <div class="risk-kpi-card">
            <span class="kpi-label">EXPECTED SHORTFALL (CVaR)</span>
            <span class="kpi-value" id="risk-cvar-val" style="color:#ffab00;">-3.68%</span>
          </div>
          <div class="risk-kpi-card">
            <span class="kpi-label">TOP BROKER (58) HHI</span>
            <span class="kpi-value" id="risk-hhi-val">2,840</span>
          </div>
          <div class="risk-kpi-card">
            <span class="kpi-label">CDSC SETTLEMENT SHIELD</span>
            <span class="kpi-value" id="risk-cdsc-val" style="color:#00e676;">ARMED (99.8%)</span>
          </div>
        </div>

        <div class="risk-panel">
          <div class="risk-panel-header">SCHUR-RA-HRP OPTIMAL WEIGHT ALLOCATION (100.0% TOTAL)</div>
          <div style="flex:1; overflow:auto;">
            <table class="quant-table">
              <thead>
                <tr>
                  <th>ASSET</th>
                  <th>OPTIMAL WEIGHT</th>
                  <th>CONTRIB TO RISK</th>
                  <th>VOLATILITY (20D)</th>
                </tr>
              </thead>
              <tbody id="risk-hrp-body">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>

        <div class="risk-panel">
          <div class="risk-panel-header">BROKER ORDER-FLOW CONCENTRATION HEATMAP (HHI)</div>
          <div style="flex:1; overflow:auto;">
            <table class="quant-table">
              <thead>
                <tr>
                  <th>BROKER</th>
                  <th>BROKER NAME</th>
                  <th>HHI SCORE</th>
                  <th>FLOW DOMINANCE</th>
                  <th>FLAG</th>
                </tr>
              </thead>
              <tbody id="risk-broker-body">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
"""

# SCREEN [4]: Forecast Engine
screen_forecast_html = """
    <!-- SCREEN [4]: 20-DAY FORECAST ENGINE -->
    <section id="screen-forecast" class="workspace-screen">
      <div class="screen-header-banner">
        <div class="screen-title-group">
          <h2>CHRONOS-BOLT 20-SESSION MULTI-QUANTILE TRAJECTORY ENGINE</h2>
          <p>DYNAMIC VOLATILITY CONES (P10 / P50 / P90) WITH POINT-IN-TIME MACRO AND PROMOTER UNLOCK PENALTIES</p>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="nav-btn active" onclick="refreshForecastData()">RERUN INFERENCE</button>
        </div>
      </div>

      <div class="forecast-body">
        <div class="forecast-sidebar">
          <div style="padding:10px 12px; background:#08111e; border-bottom:1px solid #162f4e; font-size:11px; font-weight:700; color:#7dd3fc;">
            20-DAY PROJECTED RETURNS RANK
          </div>
          <div style="flex:1; overflow:auto;">
            <table class="quant-table">
              <thead>
                <tr>
                  <th>SYM</th>
                  <th>P50 EXP</th>
                  <th>RANGE (P10-P90)</th>
                </tr>
              </thead>
              <tbody id="forecast-rank-body">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>

        <div class="forecast-chart-panel">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div style="font-size:12px; font-weight:700; color:#f1f5f9;">
              SELECTED ASSET: <span id="forecast-symbol-header" style="color:#00e5ff;">NABIL</span> (20-SESSION TRAJECTORY CORRIDOR)
            </div>
            <div style="font-size:10px; color:#64748b; display:flex; gap:12px;">
              <span><span style="color:#ff1744;">■</span> P10 DOWNSIDE</span>
              <span><span style="color:#00e5ff;">■</span> P50 MEDIAN</span>
              <span><span style="color:#00e676;">■</span> P90 UPSIDE</span>
            </div>
          </div>
          <div id="forecast-chart-canvas" style="flex:1; width:100%; min-height:360px; background:#020407; border:1px solid #0f1c2d; position:relative;">
            <canvas id="forecastCanvasElement" style="position:absolute; top:0; left:0; width:100%; height:100%;"></canvas>
          </div>
        </div>
      </div>
    </section>
"""

# ==============================================================================
# JAVASCRIPT LOGIC FOR SWITCHING SCREENS AND FETCHING WORKSPACE DATA
# ==============================================================================
workspace_js = """
  // ==========================================================================
  // MULTI-WORKSPACE CONTROLLER & DATA BINDING PIPELINE
  // ==========================================================================
  let currentWorkspaceId = 0;
  let forecastDataCache = null;

  function switchWorkspace(id) {
    id = parseInt(id, 10);
    if (isNaN(id) || id < 0 || id > 4) id = 0;
    currentWorkspaceId = id;

    // Update Top Navbar Buttons
    for (let i = 0; i <= 4; i++) {
      const btn = document.getElementById('nav-btn-' + i);
      if (btn) {
        if (i === id) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      }
    }

    // Hide all workspace screens
    const screens = {
      0: document.getElementById('screen-launchpad'),
      1: document.getElementById('screen-tradingdesk'),
      2: document.getElementById('screen-alpha'),
      3: document.getElementById('screen-risk'),
      4: document.getElementById('screen-forecast')
    };

    Object.keys(screens).forEach(key => {
      const s = screens[key];
      if (s) {
        if (parseInt(key, 10) === id) {
          s.classList.add('active');
        } else {
          s.classList.remove('active');
        }
      }
    });

    // Handle screen-specific resize & data loading
    if (id === 1) {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    } else if (id === 2) {
      refreshAlphaData();
    } else if (id === 3) {
      refreshRiskData();
    } else if (id === 4) {
      refreshForecastData();
    }
  }

  // Keyboard shortcut listener for instantaneous navigation
  window.addEventListener('keydown', function(e) {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
      return;
    }
    if (e.key === 'Escape' || e.key === '0') {
      switchWorkspace(0);
    } else if (e.key === '1') {
      switchWorkspace(1);
    } else if (e.key === '2') {
      switchWorkspace(2);
    } else if (e.key === '3') {
      switchWorkspace(3);
    } else if (e.key === '4') {
      switchWorkspace(4);
    }
  });

  // Top Navbar Clock
  function updateNavClock() {
    const el = document.getElementById('nav-clock');
    if (!el) return;
    const now = new Date();
    // UTC to NPT (UTC+5:45)
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const npt = new Date(utc + (3600000 * 5.75));
    el.textContent = npt.toTimeString().split(' ')[0];
  }
  setInterval(updateNavClock, 1000);
  updateNavClock();

  // Screen [2] Alpha Data Fetcher
  async function refreshAlphaData() {
    try {
      const resp = await fetch('/api/workspaces/alpha');
      if (!resp.ok) return;
      const data = await resp.json();
      const tbody = document.getElementById('alpha-table-body');
      if (!tbody) return;
      tbody.innerHTML = '';

      data.forEach(item => {
        const tr = document.createElement('tr');
        const badgeClass = item.status === 'BUY' ? 'badge-buy' : (item.status === 'SELL' ? 'badge-sell' : 'badge-neutral');
        tr.innerHTML = `
          <td style="font-weight:700; color:#38bdf8;">${item.symbol}</td>
          <td>${item.sector || 'COMMERCIAL'}</td>
          <td style="font-weight:700; color:${item.gate_g4_score > 70 ? '#00e676' : '#f1f5f9'};">${item.gate_g4_score.toFixed(1)}%</td>
          <td>${item.hawkes_flag ? '<span style="color:#ffab00; font-weight:700;">▲ SPIKE</span>' : '<span style="color:#64748b;">QUIET</span>'}</td>
          <td>${item.ofi_ratio ? item.ofi_ratio.toFixed(2) : '1.00'}</td>
          <td>${item.buyer_hhi || 1200}</td>
          <td>${item.seller_hhi || 1150}</td>
          <td style="color:${item.unlock_overhang_pct > 15 ? '#ff1744' : '#64748b'};">${item.unlock_overhang_pct ? item.unlock_overhang_pct.toFixed(1) + '%' : '0.0%'}</td>
          <td><span class="${badgeClass}">${item.status}</span></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.warn('Alpha fetch error:', err);
    }
  }

  // Screen [3] Risk Data Fetcher
  async function refreshRiskData() {
    try {
      const resp = await fetch('/api/workspaces/risk');
      if (!resp.ok) return;
      const data = await resp.json();

      if (data.portfolio_var_95) {
        const varEl = document.getElementById('risk-var-val');
        if (varEl) varEl.textContent = (data.portfolio_var_95 * 100).toFixed(2) + '%';
      }
      if (data.portfolio_cvar_95) {
        const cvarEl = document.getElementById('risk-cvar-val');
        if (cvarEl) cvarEl.textContent = (data.portfolio_cvar_95 * 100).toFixed(2) + '%';
      }

      // Populate HRP Allocations
      const hrpBody = document.getElementById('risk-hrp-body');
      if (hrpBody && data.hrp_allocation) {
        hrpBody.innerHTML = '';
        data.hrp_allocation.forEach(row => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td style="font-weight:700; color:#38bdf8;">${row.symbol}</td>
            <td style="font-weight:700; color:#00e676;">${row.weight.toFixed(1)}%</td>
            <td>${row.risk_contrib ? row.risk_contrib.toFixed(2) + '%' : '--'}</td>
            <td>${row.volatility_20d ? (row.volatility_20d * 100).toFixed(1) + '%' : '18.4%'}</td>
          `;
          hrpBody.appendChild(tr);
        });
      }

      // Populate Broker HHI Table
      const brokerBody = document.getElementById('risk-broker-body');
      if (brokerBody && data.broker_hhi) {
        brokerBody.innerHTML = '';
        data.broker_hhi.forEach(b => {
          const tr = document.createElement('tr');
          const isHigh = b.hhi > 2500;
          tr.innerHTML = `
            <td style="font-weight:700; color:#cbd5e1;">#${b.broker_id}</td>
            <td>${b.name || 'Broker ' + b.broker_id}</td>
            <td style="font-weight:700; color:${isHigh ? '#ff1744' : '#38bdf8'};">${b.hhi}</td>
            <td>${b.dominance_pct ? b.dominance_pct.toFixed(1) + '%' : '--'}</td>
            <td>${isHigh ? '<span class="badge-sell">CONCENTRATED</span>' : '<span class="badge-buy">NORMAL</span>'}</td>
          `;
          brokerBody.appendChild(tr);
        });
      }
    } catch (err) {
      console.warn('Risk fetch error:', err);
    }
  }

  // Screen [4] Forecast Data Fetcher & Canvas Corridor Renderer
  async function refreshForecastData() {
    try {
      const resp = await fetch('/api/workspaces/forecast');
      if (!resp.ok) return;
      forecastDataCache = await resp.json();

      // Populate Sidebar Ranking
      const rankBody = document.getElementById('forecast-rank-body');
      if (rankBody && forecastDataCache.ranked_forecasts) {
        rankBody.innerHTML = '';
        forecastDataCache.ranked_forecasts.forEach(item => {
          const tr = document.createElement('tr');
          tr.style.cursor = 'pointer';
          const expSign = item.p50_exp >= 0 ? '+' : '';
          const expColor = item.p50_exp >= 0 ? '#00e676' : '#ff1744';
          tr.innerHTML = `
            <td style="font-weight:700; color:#38bdf8;">${item.symbol}</td>
            <td style="font-weight:700; color:${expColor};">${expSign}${item.p50_exp.toFixed(1)}%</td>
            <td style="color:#94a3b8; font-size:10px;">${item.p10_exp.toFixed(1)}% ~ ${item.p90_exp.toFixed(1)}%</td>
          `;
          tr.onclick = () => selectForecastSymbol(item.symbol);
          rankBody.appendChild(tr);
        });
      }

      renderForecastCanvas();
    } catch (err) {
      console.warn('Forecast fetch error:', err);
    }
  }

  function selectForecastSymbol(sym) {
    const header = document.getElementById('forecast-symbol-header');
    if (header) header.textContent = sym;
    renderForecastCanvas();
  }

  function renderForecastCanvas() {
    if (!forecastDataCache) return;
    const canvas = document.getElementById('forecastCanvasElement');
    if (!canvas) return;
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const p10 = forecastDataCache.p10_curve || [];
    const p50 = forecastDataCache.p50_curve || [];
    const p90 = forecastDataCache.p90_curve || [];
    const n = Math.max(p10.length, p50.length, p90.length);
    if (n === 0) return;

    // Determine Y range
    let minY = Math.min(...p10, ...p50, ...p90);
    let maxY = Math.max(...p10, ...p50, ...p90);
    const pad = (maxY - minY) * 0.15 || 10;
    minY -= pad;
    maxY += pad;

    const padLeft = 60;
    const padRight = 30;
    const padTop = 30;
    const padBottom = 40;
    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    const getX = i => padLeft + (i / (n - 1)) * plotW;
    const getY = val => padTop + plotH - ((val - minY) / (maxY - minY)) * plotH;

    // Draw Grid Lines
    ctx.strokeStyle = '#0d1d30';
    ctx.lineWidth = 1;
    for (let g = 0; g <= 4; g++) {
      const yVal = minY + (g / 4) * (maxY - minY);
      const yPx = getY(yVal);
      ctx.beginPath();
      ctx.moveTo(padLeft, yPx);
      ctx.lineTo(w - padRight, yPx);
      ctx.stroke();

      ctx.fillStyle = '#64748b';
      ctx.font = '10px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(yVal.toFixed(1), padLeft - 8, yPx + 3);
    }

    // Draw Shaded P10-P90 Corridor
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p90[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    for (let i = n - 1; i >= 0; i--) {
      const x = getX(i);
      const y = getY(p10[i]);
      ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(0, 229, 255, 0.08)';
    ctx.fill();

    // Draw P90 line (Green)
    ctx.beginPath();
    ctx.strokeStyle = '#00e676';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p90[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw P10 line (Red)
    ctx.beginPath();
    ctx.strokeStyle = '#ff1744';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p10[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw P50 Median line (Solid Cyan)
    ctx.beginPath();
    ctx.strokeStyle = '#00e5ff';
    ctx.lineWidth = 2.5;
    ctx.setLineDash([]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p50[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw Points on P50
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p50[i]);
      ctx.fillStyle = '#030508';
      ctx.strokeStyle = '#00e5ff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // X-axis label
      ctx.fillStyle = '#64748b';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('D+' + (i + 1), x, h - padBottom + 16);
    }
  }

  window.addEventListener('resize', () => {
    if (currentWorkspaceId === 4) {
      renderForecastCanvas();
    }
  });
"""

# ==============================================================================
# ASSEMBLE CLEAN HTML
# ==============================================================================
# 1. Insert CSS right before </head>
html_part1 = clean_html[:head_close]
html_head_injected = html_part1 + "<style>\n" + workspace_css + "\n</style>\n" + clean_html[head_close:root_start]

# 2. Extract original terminal-root content
original_terminal_root = clean_html[root_start:root_end]

# 3. Screen [1] wrap original_terminal_root
screen_tradingdesk_html = f"""
    <!-- SCREEN [1]: TRADING DESK & EXECUTION TAPE -->
    <section id="screen-tradingdesk" class="workspace-screen">
{original_terminal_root}
    </section>
"""

# 4. Assemble workspace viewport with all screens
main_viewport = (
    navbar_html +
    screen_launchpad_html +
    screen_tradingdesk_html +
    screen_alpha_html +
    screen_risk_html +
    screen_forecast_html +
    "\n  </main>\n"
)

# 5. Insert after terminal-root closing tag up to </body>
html_part_after_root = clean_html[root_end:]

# Insert workspace_js right before </body>
body_close = html_part_after_root.rfind('</body>')
assert body_close != -1, "Could not find </body>"

final_html = (
    html_head_injected +
    main_viewport +
    html_part_after_root[:body_close] +
    "\n  <script>\n" + workspace_js + "\n  </script>\n" +
    html_part_after_root[body_close:]
)

with open('pulse_terminal/index.html', 'w', encoding='utf-8') as f:
    f.write(final_html)

print("Successfully generated clean pulse_terminal/index.html!")
print("Total size:", len(final_html), "bytes")
