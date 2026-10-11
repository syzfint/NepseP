"""
Master UI Rebuilder for State-Driven Multi-Screen Architecture (16:9 Aspect Ratio / 100vh).
Produces:
  1. pulse_terminal/index.html (Primary Terminal GUI)
  2. templates/terminal.html (FastAPI Template View)
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CLEAN_HTML_PATH = BASE_DIR / "pulse_terminal" / "index_clean.html"
TARGET_INDEX_PATH = BASE_DIR / "pulse_terminal" / "index.html"
TARGET_TEMPLATE_PATH = BASE_DIR / "templates" / "terminal.html"

with open(CLEAN_HTML_PATH, "r", encoding="utf-8") as f:
    clean_html = f.read()

head_close = clean_html.find("</head>")
assert head_close != -1, "Could not find </head>"

root_start = clean_html.find('<div id="terminal-root"')
assert root_start != -1, "Could not find <div id=\"terminal-root\""

script_marker = '<!-- 4. ZERO-DEPENDENCY VANILLA JAVASCRIPT DISPATCHER PIPELINE'
script_pos = clean_html.find(script_marker)
assert script_pos != -1, "Could not find script marker"

last_div = clean_html.rfind('</div>', 0, script_pos)
assert last_div != -1, "Could not find closing div of terminal-root"
root_end = last_div + len('</div>')

# ==============================================================================
# CSS FOR 16:9 RESPONSIVE BLOOMBERG/REFINITIV TERMINAL STYLING
# ==============================================================================
state_driven_css = """
  /* ========================================================================== */
  /* STATE-DRIVEN MULTI-SCREEN & 16:9 RESPONSIVE VIEWPORT ARCHITECTURE          */
  /* ========================================================================== */
  :root {
    --nav-height: 36px;
    --footer-height: 28px;
    --bg-deep: #0d1117;
    --bg-panel: #161b22;
    --bg-subpanel: #0d1117;
    --border-dim: #30363d;
    --border-bright: #58a6ff;
    --neon-cyan: #58a6ff;
    --neon-green: #3fb950;
    --neon-amber: #d29922;
    --neon-red: #f85149;
    --text-primary: #c9d1d9;
    --text-muted: #8b949e;
    --accent-blue: #1f6feb;
  }

  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  html, body {
    margin: 0;
    padding: 0;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    background: var(--bg-deep);
    color: var(--text-primary);
    font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
    font-size: 11px;
    user-select: none;
  }

  /* 3-ROW GRID SHELL: TOP NAV (36px), WORKSPACE VIEWPORT (1fr), FOOTER (28px) */
  #terminal-app-shell {
    display: grid;
    grid-template-rows: var(--nav-height) 1fr var(--footer-height);
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    position: relative;
    background: var(--bg-deep);
  }

  /* PERSISTENT WORKSPACE TOP NAVBAR (36px) */
  #workspace-navbar {
    grid-row: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--nav-height);
    background: #161b22;
    border-bottom: 1px solid var(--border-dim);
    padding: 0 12px;
    z-index: 9999;
    font-size: 11px;
    letter-spacing: 0.05em;
  }

  .nav-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 800;
    color: #f0f6fc;
    cursor: pointer;
  }

  .nav-brand .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--neon-cyan);
    box-shadow: 0 0 10px var(--neon-cyan);
    animation: blink-dot 2s infinite;
  }

  @keyframes blink-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.35; transform: scale(0.8); }
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
    gap: 6px;
  }

  .nav-btn .key-hint {
    background: #21262d;
    color: #58a6ff;
    border: 1px solid #30363d;
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 9px;
    font-weight: 700;
  }

  .nav-btn:hover {
    color: #f0f6fc;
    background: rgba(88, 166, 255, 0.1);
    border-color: rgba(88, 166, 255, 0.3);
  }

  .nav-btn.active {
    color: #58a6ff;
    background: rgba(88, 166, 255, 0.15);
    border-color: #58a6ff;
    box-shadow: 0 0 10px rgba(88, 166, 255, 0.2);
  }

  .nav-status {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 10px;
  }

  .nav-status-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    background: #0d1117;
    border: 1px solid var(--border-dim);
    padding: 2px 8px;
    border-radius: 3px;
    color: #58a6ff;
  }

  .nav-active-ticker {
    background: rgba(88, 166, 255, 0.15);
    border: 1px solid #58a6ff;
    color: #f0f6fc;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 3px;
    letter-spacing: 0.05em;
  }

  /* WORKSPACE MAIN VIEWPORT (1fr) */
  #workspace-container {
    grid-row: 2;
    width: 100%;
    height: 100%;
    overflow: hidden;
    position: relative;
    background: var(--bg-deep);
  }

  /* SCREEN CONTAINER ISOLATION */
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

  /* PERSISTENT GLOBAL TELEMETRY FOOTER (28px) */
  #global-terminal-footer {
    grid-row: 3;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--footer-height);
    background: #161b22;
    border-top: 1px solid var(--border-dim);
    padding: 0 12px;
    font-size: 10px;
    color: var(--text-muted);
    z-index: 9999;
  }

  .footer-left, .footer-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .footer-chip {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  /* SCREEN [1]: TRADING DESK */
  #screen-tradingdesk {
    display: none !important;
    width: 100%;
    height: 100%;
    position: absolute;
    top: 0;
    left: 0;
    overflow: hidden !important;
    flex-direction: column;
  }
  #screen-tradingdesk.active {
    display: flex !important;
  }
  #screen-tradingdesk #terminal-root {
    width: 100% !important;
    height: 100% !important;
    max-width: 100% !important;
    max-height: 100% !important;
    display: grid !important;
    grid-template-rows: 28px 28px 1fr !important; /* Avoid double telemetry bar */
    border: none !important;
    overflow: hidden !important;
    position: relative !important;
    top: auto !important;
    left: auto !important;
  }
  #screen-tradingdesk #telemetry-dock {
    display: none !important; /* Replaced by global-terminal-footer */
  }

  /* SCREEN [0]: LAUNCH PAD */
  #screen-launchpad {
    background: radial-gradient(circle at 50% 30%, #161b22 0%, #0d1117 80%);
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
    font-size: 20px;
    letter-spacing: 0.12em;
    color: #f0f6fc;
    font-weight: 800;
    margin: 0 0 6px 0;
  }
  .launchpad-header p {
    font-size: 11px;
    color: var(--text-muted);
    margin: 0;
  }

  .launchpad-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: repeat(2, 1fr);
    gap: 18px;
    flex: 1;
    min-height: 460px;
    max-width: 1300px;
    width: 100%;
    margin: 0 auto;
  }

  .launch-card {
    background: #161b22;
    border: 1px solid var(--border-dim);
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

  .launch-card:hover {
    border-color: #58a6ff;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(88, 166, 255, 0.15);
    background: #1c2128;
  }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .card-id-badge {
    background: #21262d;
    color: #58a6ff;
    border: 1px solid #30363d;
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 3px;
  }

  .card-title {
    font-size: 14px;
    font-weight: 700;
    color: #f0f6fc;
    margin: 8px 0 4px 0;
    letter-spacing: 0.04em;
  }

  .card-desc {
    font-size: 11px;
    color: #8b949e;
    line-height: 1.4;
    margin-bottom: 12px;
  }

  .card-metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    background: #0d1117;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 10px;
  }

  .card-metric-cell {
    display: flex;
    flex-direction: column;
  }

  .card-metric-label {
    font-size: 9px;
    color: #8b949e;
    text-transform: uppercase;
  }

  .card-metric-val {
    font-size: 12px;
    font-weight: 700;
    color: #58a6ff;
    margin-top: 2px;
  }

  /* SCREEN [2]: ALPHA DASHBOARD */
  #screen-alpha {
    flex-direction: column;
    background: var(--bg-deep);
    padding: 12px 16px;
    box-sizing: border-box;
    gap: 10px;
  }

  .screen-header-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #161b22;
    border: 1px solid var(--border-dim);
    padding: 10px 16px;
    border-radius: 4px;
  }

  .screen-title-group h2 {
    margin: 0;
    font-size: 14px;
    font-weight: 800;
    color: #f0f6fc;
    letter-spacing: 0.05em;
  }
  .screen-title-group p {
    margin: 3px 0 0 0;
    font-size: 10px;
    color: var(--text-muted);
  }

  .alpha-table-container {
    flex: 1;
    background: #161b22;
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
    background: #21262d;
    color: #58a6ff;
    padding: 8px 12px;
    font-weight: 700;
    border-bottom: 1px solid var(--border-dim);
    position: sticky;
    top: 0;
    z-index: 2;
    white-space: nowrap;
  }

  .quant-table td {
    padding: 7px 12px;
    border-bottom: 1px solid #21262d;
    white-space: nowrap;
    color: #c9d1d9;
  }

  .quant-table tr {
    cursor: pointer;
    transition: background-color 0.15s ease;
  }

  .quant-table tr:hover td {
    background: rgba(88, 166, 255, 0.08);
    color: #f0f6fc;
  }

  .quant-table tr.selected-row td {
    background: rgba(88, 166, 255, 0.18) !important;
    border-color: #58a6ff;
    color: #fff !important;
    font-weight: 700;
  }

  .badge-buy {
    color: #3fb950;
    background: rgba(63, 185, 80, 0.12);
    border: 1px solid rgba(63, 185, 80, 0.35);
    padding: 2px 6px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 9.5px;
  }

  .badge-sell {
    color: #f85149;
    background: rgba(248, 81, 73, 0.12);
    border: 1px solid rgba(248, 81, 73, 0.35);
    padding: 2px 6px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 9.5px;
  }

  .badge-neutral {
    color: #8b949e;
    background: rgba(139, 148, 158, 0.12);
    border: 1px solid rgba(139, 148, 158, 0.25);
    padding: 2px 6px;
    border-radius: 2px;
    font-size: 9.5px;
  }

  /* SCREEN [3]: RISK MONITOR */
  #screen-risk {
    flex-direction: column;
    background: var(--bg-deep);
    padding: 12px 16px;
    box-sizing: border-box;
    gap: 10px;
  }

  .risk-grid-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 130px 1fr;
    gap: 10px;
    flex: 1;
    min-height: 0;
  }

  .risk-kpi-row {
    grid-column: span 2;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  .risk-kpi-card {
    background: #161b22;
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
    color: #58a6ff;
    margin-top: 4px;
  }

  .risk-panel {
    background: #161b22;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  .risk-panel-header {
    font-size: 11.5px;
    font-weight: 700;
    color: #f0f6fc;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--border-dim);
    padding-bottom: 6px;
  }

  /* SCREEN [4]: FORECAST ENGINE */
  #screen-forecast {
    flex-direction: column;
    background: var(--bg-deep);
    padding: 12px 16px;
    box-sizing: border-box;
    gap: 10px;
  }

  .forecast-body {
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 10px;
    flex: 1;
    min-height: 0;
  }

  .forecast-sidebar {
    background: #161b22;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .forecast-chart-panel {
    background: #161b22;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    padding: 12px;
    min-height: 0;
  }
"""

# ==============================================================================
# HTML VIEWPORT STRUCTURE
# ==============================================================================
navbar_and_shell_start = """
<div id="terminal-app-shell">
  <!-- PERSISTENT QUANT WORKSPACE NAVBAR (36px) -->
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
      <div class="nav-active-ticker">
        <span>ACTIVE: </span><span id="nav-active-symbol-badge">NABIL</span>
      </div>
      <div class="nav-status-chip">
        <span>NPT</span>
        <span id="nav-clock" style="font-weight:700;">--:--:--</span>
      </div>
      <div class="nav-status-chip" style="color: #3fb950; border-color: rgba(63,185,80,0.3);">
        <span style="font-weight:700;">ENGINE: 60 FPS</span>
      </div>
    </div>
  </header>

  <!-- MULTI-WORKSPACE VIEWPORT CONTAINER (1fr) -->
  <main id="workspace-container">
"""

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
              <span style="color:#58a6ff; font-size:10px; font-weight:700;">600µs LATENCY</span>
            </div>
            <div class="card-title">TRADING DESK & LEVEL 2 BOOK</div>
            <div class="card-desc">Zero-DOM canvas graphics, real-time depth tape, Centaur human-in-the-loop staging blotter, and tick telemetry.</div>
          </div>
          <div class="card-metrics">
            <div class="card-metric-cell">
              <span class="card-metric-label">ACTIVE SYMBOL</span>
              <span class="card-metric-val" id="lp-active-sym-1">NABIL</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">L2 DEPTH</span>
              <span class="card-metric-val">50 LEVELS</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">SLIPPAGE GUARD</span>
              <span class="card-metric-val" style="color:#3fb950;">SHIELD ON</span>
            </div>
          </div>
        </div>

        <!-- CARD 2 -->
        <div class="launch-card" onclick="switchWorkspace(2)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[2] WORKSPACE</span>
              <span style="color:#3fb950; font-size:10px; font-weight:700;">353+ SECURITIES</span>
            </div>
            <div class="card-title">ALPHA & LIVE SIGNAL DASHBOARD</div>
            <div class="card-desc">Cross-asset directional signal engine, Gate G4 confidence ranking, Hawkes jump sweeps, and order-flow imbalance ratios.</div>
          </div>
          <div class="card-metrics">
            <div class="card-metric-cell">
              <span class="card-metric-label">GATE G4 TOP</span>
              <span class="card-metric-val">UPPER (87.4%)</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">HAWKES JUMP</span>
              <span class="card-metric-val" style="color:#d29922;">ACCUMULATION</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">COVERAGE</span>
              <span class="card-metric-val" style="color:#3fb950;">395 STOCKS</span>
            </div>
          </div>
        </div>

        <!-- CARD 3 -->
        <div class="launch-card" onclick="switchWorkspace(3)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[3] WORKSPACE</span>
              <span style="color:#d29922; font-size:10px; font-weight:700;">skfolio INTEGRATED</span>
            </div>
            <div class="card-title">RISK MONITOR & PORTFOLIO GOVERNANCE</div>
            <div class="card-desc">Schur Return-Adjusted Hierarchical Risk Parity (HRP), Broker HHI concentration monitor, and CDSC T+2 settlement shield.</div>
          </div>
          <div class="card-metrics">
            <div class="card-metric-cell">
              <span class="card-metric-label">PORTFOLIO VaR</span>
              <span class="card-metric-val" style="color:#f85149;">-1.85%</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">BROKER 58 HHI</span>
              <span class="card-metric-val">2,840 (HIGH)</span>
            </div>
            <div class="card-metric-cell">
              <span class="card-metric-label">HRP ASSETS</span>
              <span class="card-metric-val">100.0% SUM</span>
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
              <span class="card-metric-label">ACTIVE PROJECTION</span>
              <span class="card-metric-val" id="lp-forecast-sym" style="color:#3fb950;">NABIL (+3.9%)</span>
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

      <div class="launchpad-footer" style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:12px; margin-top:16px; font-size:10.5px; color:#8b949e;">
        <span>PRESS [1]-[4] TO LAUNCH DIRECTLY | PRESS [ESC] TO RETURN TO THIS MENU</span>
        <span>NEPSE QUANT PIPELINE v4.2.0 • DUCKDB ENGINE CONNECTED</span>
      </div>
    </section>
"""

screen_alpha_html = """
    <!-- SCREEN [2]: ALPHA & LIVE SIGNAL DASHBOARD -->
    <section id="screen-alpha" class="workspace-screen">
      <div class="screen-header-banner">
        <div class="screen-title-group">
          <h2>ALPHA SIGNALS & GATE G4 EXECUTION MONITOR (353+ SECURITIES)</h2>
          <p>CLICK ANY ROW TO SELECT STOCK ACROSS ALL TERMINAL SCREENS</p>
        </div>
        <div style="display:flex; gap:10px;">
          <input type="text" id="alpha-search-input" placeholder="FILTER TICKER..." oninput="filterAlphaGrid(this.value)" style="background:#0d1117; border:1px solid #30363d; color:#fff; padding:4px 10px; font-family:inherit; font-size:11px; border-radius:3px;">
          <button class="nav-btn active" onclick="refreshAlphaData()">REFRESH SIGNALS</button>
        </div>
      </div>

      <div class="alpha-table-container">
        <table class="quant-table" id="alpha-table">
          <thead>
            <tr>
              <th>SYMBOL</th>
              <th>LTP (NPR)</th>
              <th>EXP RETURN (5D)</th>
              <th>GATE G4 CONFIDENCE</th>
              <th>HAWKES SWEEP</th>
              <th>OFI RATIO</th>
              <th>STATUS</th>
              <th>UNLOCK OVERHANG</th>
              <th>DAYS TO UNLOCK</th>
            </tr>
          </thead>
          <tbody id="alpha-table-body">
            <!-- Dynamically populated via API/WebSocket -->
          </tbody>
        </table>
      </div>
    </section>
"""

screen_risk_html = """
    <!-- SCREEN [3]: RISK MONITOR & PORTFOLIO GOVERNANCE -->
    <section id="screen-risk" class="workspace-screen">
      <div class="screen-header-banner">
        <div class="screen-title-group">
          <h2>RISK MONITOR & SCHUR-RA-HRP PORTFOLIO GOVERNANCE</h2>
          <p>SELECTED ASSET RISK OVERLAY: <span id="risk-active-symbol-header" style="color:#58a6ff; font-weight:800;">NABIL</span></p>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="nav-btn active" onclick="refreshRiskData()">RECALCULATE HRP</button>
        </div>
      </div>

      <div class="risk-grid-container">
        <div class="risk-kpi-row">
          <div class="risk-kpi-card">
            <span class="kpi-label">PORTFOLIO VaR (95%)</span>
            <span class="kpi-value" id="risk-var-val" style="color:#f85149;">-1.85%</span>
          </div>
          <div class="risk-kpi-card">
            <span class="kpi-label">EXPECTED SHORTFALL (CVaR)</span>
            <span class="kpi-value" id="risk-cvar-val" style="color:#d29922;">-2.94%</span>
          </div>
          <div class="risk-kpi-card">
            <span class="kpi-label">TOP BROKER (58) HHI</span>
            <span class="kpi-value" id="risk-hhi-val">2,840</span>
          </div>
          <div class="risk-kpi-card">
            <span class="kpi-label">CDSC SETTLEMENT SHIELD</span>
            <span class="kpi-value" id="risk-cdsc-val" style="color:#3fb950;">ARMED (99.8%)</span>
          </div>
        </div>

        <div class="risk-panel">
          <div class="risk-panel-header">SCHUR-RA-HRP OPTIMAL WEIGHT ALLOCATION (100.0% TOTAL)</div>
          <div style="flex:1; overflow:auto;">
            <table class="quant-table">
              <thead>
                <tr>
                  <th>ASSET</th>
                  <th>CLUSTER</th>
                  <th>OPTIMAL WEIGHT</th>
                  <th>RISK CONTRIB</th>
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
                  <th>DOMINANCE</th>
                  <th>FLOW ACTION</th>
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

screen_forecast_html = """
    <!-- SCREEN [4]: 20-DAY FORECAST ENGINE -->
    <section id="screen-forecast" class="workspace-screen">
      <div class="screen-header-banner">
        <div class="screen-title-group">
          <h2>CHRONOS-BOLT 20-SESSION MULTI-QUANTILE TRAJECTORY ENGINE</h2>
          <p>ACTIVE ASSET TRAJECTORY: <span id="forecast-symbol-header" style="color:#58a6ff; font-weight:800;">NABIL</span></p>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="nav-btn active" onclick="refreshForecastData()">RERUN INFERENCE</button>
        </div>
      </div>

      <div class="forecast-body">
        <div class="forecast-sidebar">
          <div style="padding:8px 12px; background:#21262d; border-bottom:1px solid #30363d; font-size:11px; font-weight:700; color:#58a6ff;">
            20-DAY PROJECTED RETURNS RANK
          </div>
          <div style="flex:1; overflow:auto;">
            <table class="quant-table" id="forecast-rank-table">
              <thead>
                <tr>
                  <th>SYM</th>
                  <th>LTP</th>
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
            <div style="font-size:12px; font-weight:700; color:#f0f6fc;">
              CORRIDOR TRAJECTORY: <span id="forecast-chart-active-sym" style="color:#58a6ff;">NABIL</span>
            </div>
            <div style="font-size:10px; color:#8b949e; display:flex; gap:12px;">
              <span><span style="color:#f85149;">■</span> P10 DOWNSIDE</span>
              <span><span style="color:#58a6ff;">■</span> P50 MEDIAN</span>
              <span><span style="color:#3fb950;">■</span> P90 UPSIDE</span>
            </div>
          </div>
          <div id="forecast-chart-canvas-container" style="flex:1; width:100%; min-height:360px; background:#0d1117; border:1px solid #30363d; position:relative;">
            <canvas id="forecastCanvasElement" style="position:absolute; top:0; left:0; width:100%; height:100%;"></canvas>
          </div>
        </div>
      </div>
    </section>
"""

shell_footer_html = """
  </main>

  <!-- PERSISTENT GLOBAL TELEMETRY FOOTER (28px) -->
  <footer id="global-terminal-footer">
    <div class="footer-left">
      <div class="footer-chip">
        <span>GATE G4 ENGINE:</span>
        <span style="color:#3fb950; font-weight:700;">ACTIVE (395 SECURITIES)</span>
      </div>
      <div class="footer-chip">
        <span>SEQLOCK SEQ:</span>
        <span id="footer-seqlock-seq" style="color:#58a6ff;">154,208</span>
      </div>
      <div class="footer-chip">
        <span>LATENCY:</span>
        <span id="footer-pipeline-latency" style="color:#3fb950; font-weight:700;">142.5 µs</span>
      </div>
    </div>
    <div class="footer-right">
      <div class="footer-chip">
        <span>ACTIVE SCREEN:</span>
        <span id="footer-active-screen" style="color:#58a6ff; font-weight:700;">LAUNCH PAD [0]</span>
      </div>
      <div class="footer-chip">
        <span>FPS:</span>
        <span id="footer-fps-val" style="color:#3fb950; font-weight:700;">60.0 FPS</span>
      </div>
    </div>
  </footer>
</div>
"""

# ==============================================================================
# JAVASCRIPT GLOBAL STATE MANAGER & DYNAMIC STOCK SELECTION ENGINE
# ==============================================================================
state_manager_js = """
  // ==========================================================================
  // GLOBAL TERMINAL STATE MANAGER & DYNAMIC STOCK SELECTION PIPELINE
  // ==========================================================================
  window.TERMINAL_STATE = {
    activeSymbol: 'NABIL',
    activeScreen: 'launcher',
    marketUniverse: {},
    signalsData: {},
    riskData: {},
    forecastData: {}
  };

  let globalWs = null;
  let animFrameId = null;
  let fpsCounter = 0;
  let lastFpsCheck = performance.now();

  // FPS Profiler Loop (Asserts 60 FPS Canvas rendering)
  function runTerminalFpsLoop() {
    fpsCounter++;
    const now = performance.now();
    if (now - lastFpsCheck >= 1000) {
      const currentFps = (fpsCounter * 1000) / (now - lastFpsCheck);
      const el = document.getElementById('footer-fps-val');
      if (el) el.textContent = `${currentFps.toFixed(1)} FPS`;
      fpsCounter = 0;
      lastFpsCheck = now;
    }
    requestAnimationFrame(runTerminalFpsLoop);
  }
  requestAnimationFrame(runTerminalFpsLoop);

  // Modular View Re-render Routines
  function renderTradingDesk(symbol) {
    if (typeof window.renderTradingDesk === 'function' && window.renderTradingDesk !== renderTradingDesk) {
      window.renderTradingDesk(symbol);
      return;
    }
    const bookSym = document.getElementById('book-active-symbol');
    if (bookSym) bookSym.textContent = symbol;
    const chartMeta = document.getElementById('chart-active-meta');
    if (chartMeta) chartMeta.textContent = `${symbol} • LIVE DEPTH & CVD`;
    if (typeof loadAndRenderSeries === 'function' && typeof activeChartMode !== 'undefined') {
      loadAndRenderSeries(symbol, activeChartMode);
    } else if (typeof window.loadAndRenderSeries === 'function') {
      window.loadAndRenderSeries(symbol, 'CANDLE');
    }
  }

  function highlightAlphaRow(symbol) {
    document.querySelectorAll('.quant-table tr.selected-row').forEach(r => r.classList.remove('selected-row'));
    const alphaRow = document.getElementById('alpha-row-' + symbol);
    if (alphaRow) alphaRow.classList.add('selected-row');
    const fcRow = document.getElementById('fc-row-' + symbol);
    if (fcRow) fcRow.classList.add('selected-row');
  }

  function renderRiskMetrics(symbol) {
    const riskSym = document.getElementById('risk-active-symbol-header');
    if (riskSym) riskSym.textContent = symbol;
    fetchSymbolRisk(symbol);
  }

  function drawQuantileCorridorCanvas(symbol) {
    const fcSym = document.getElementById('forecast-symbol-header');
    if (fcSym) fcSym.textContent = symbol;
    const fcChartSym = document.getElementById('forecast-chart-active-sym');
    if (fcChartSym) fcChartSym.textContent = symbol;
    fetchSymbolForecast(symbol);
  }

  // Global Symbol Selection Dispatcher
  window.selectSymbol = function(symbol) {
    if (!symbol) return;
    symbol = symbol.toUpperCase().trim();
    window.TERMINAL_STATE.activeSymbol = symbol;

    // 1. Update Top Header Ticker Badges
    document.querySelectorAll('.active-symbol-badge').forEach(el => el.innerText = symbol);
    const badge = document.getElementById('nav-active-symbol-badge');
    if (badge) badge.innerText = symbol;
    const lpSym = document.getElementById('lp-active-sym-1');
    if (lpSym) lpSym.innerText = symbol;

    // 2. Re-render Screen 1 (Trading Desk Order Book & Chart Canvas)
    renderTradingDesk(symbol);

    // 3. Highlight Screen 2 Active Row
    highlightAlphaRow(symbol);

    // 4. Recalculate Screen 3 Stock Asset Risk Contribution & CDSC Shield
    renderRiskMetrics(symbol);

    // 5. Re-draw Screen 4 Chronos-Bolt P10/P50/P90 Quantile Forecast Canvas
    drawQuantileCorridorCanvas(symbol);

    // 6. Send WebSocket notification if connected
    const activeSocket = window.terminalSocket || globalWs;
    if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
      activeSocket.send(JSON.stringify({ command: 'SELECT_SYMBOL', symbol: symbol, action: 'SUBSCRIBE' }));
    }
  };

  // Switch Workspace Screen (0=Launcher, 1=Trading Desk, 2=Alpha, 3=Risk, 4=Forecast)
  window.switchWorkspace = function(id) {
    id = parseInt(id, 10);
    if (isNaN(id) || id < 0 || id > 4) id = 0;

    const screenMap = { 0: 'launcher', 1: 'trading_desk', 2: 'alpha', 3: 'risk', 4: 'forecast' };
    window.TERMINAL_STATE.activeScreen = screenMap[id] || 'launcher';

    // Navbar buttons
    for (let i = 0; i <= 4; i++) {
      const btn = document.getElementById('nav-btn-' + i);
      if (btn) {
        if (i === id) btn.classList.add('active');
        else btn.classList.remove('active');
      }
    }

    // Screens
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
        if (parseInt(key, 10) === id) s.classList.add('active');
        else s.classList.remove('active');
      }
    });

    const footerScreen = document.getElementById('footer-active-screen');
    const screenNames = ['LAUNCH PAD [0]', 'TRADING DESK [1]', 'ALPHA DASHBOARD [2]', 'RISK MONITOR [3]', '20D FORECAST [4]'];
    if (footerScreen) footerScreen.textContent = screenNames[id] || 'LAUNCH PAD [0]';

    // Trigger canvas & layout resizes
    if (id === 1) {
      setTimeout(() => {
        const tvContainer = document.getElementById('tv-chart-view');
        if (window.tvChart && tvContainer && tvContainer.clientWidth > 0) {
          window.tvChart.resize(tvContainer.clientWidth, tvContainer.clientHeight);
          window.tvChart.timeScale().fitContent();
        }
        renderTradingDesk(window.TERMINAL_STATE.activeSymbol || 'NABIL');
        window.dispatchEvent(new Event('resize'));
      }, 60);
    } else if (id === 2) {
      refreshAlphaData();
    } else if (id === 3) {
      refreshRiskData();
    } else if (id === 4) {
      fetchSymbolForecast(window.TERMINAL_STATE.activeSymbol);
    }
  };

  // Keyboard Navigation
  window.addEventListener('keydown', function(e) {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
    if (e.key === 'Escape' || e.key === '0') switchWorkspace(0);
    else if (e.key === '1') switchWorkspace(1);
    else if (e.key === '2') switchWorkspace(2);
    else if (e.key === '3') switchWorkspace(3);
    else if (e.key === '4') switchWorkspace(4);
  });

  // Top Clock (NPT UTC+5:45)
  function updateNavClock() {
    const el = document.getElementById('nav-clock');
    if (!el) return;
    const now = new Date();
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const npt = new Date(utc + (3600000 * 5.75));
    el.textContent = npt.toTimeString().split(' ')[0];
  }
  setInterval(updateNavClock, 1000);
  updateNavClock();

  // Screen [2]: Alpha Dashboard Fetch & Filter
  async function refreshAlphaData() {
    try {
      const resp = await fetch('/api/v1/terminal/screen/alpha');
      if (!resp.ok) return;
      const json = await resp.json();
      window.TERMINAL_STATE.alphaData = json.data || [];
      renderAlphaGrid(window.TERMINAL_STATE.alphaData);
    } catch (e) {
      console.warn('Alpha fetch error:', e);
    }
  }

  function renderAlphaGrid(items) {
    const tbody = document.getElementById('alpha-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    items.forEach(item => {
      const tr = document.createElement('tr');
      tr.id = 'alpha-row-' + item.symbol;
      if (item.symbol === window.TERMINAL_STATE.activeSymbol) tr.classList.add('selected-row');

      const isBuy = item.status === 'BUY';
      const isSell = item.status === 'SELL';
      const badgeCls = isBuy ? 'badge-buy' : (isSell ? 'badge-sell' : 'badge-neutral');
      const isAccum = item.hawkes_flag === 'ACCUMULATION_DETECTED';

      tr.innerHTML = `
        <td style="font-weight:700; color:#58a6ff;">${item.symbol}</td>
        <td>NPR ${item.ltp.toFixed(1)}</td>
        <td style="color:${item.exp_return_pct >= 0 ? '#3fb950' : '#f85149'}; font-weight:700;">${item.exp_return_pct >= 0 ? '+' : ''}${item.exp_return_pct.toFixed(2)}%</td>
        <td style="font-weight:700; color:${item.gate_g4_score >= 70 ? '#3fb950' : '#c9d1d9'};">${item.gate_g4_score.toFixed(1)}%</td>
        <td>${isAccum ? '<span style="color:#d29922; font-weight:700;">▲ ACCUMULATION</span>' : '<span style="color:#8b949e;">NORMAL</span>'}</td>
        <td>${item.ofi_ratio ? item.ofi_ratio.toFixed(2) : '1.00'}</td>
        <td><span class="${badgeCls}">${item.status}</span></td>
        <td style="color:${item.promoter_unlock_30d_pct > 15 ? '#f85149' : '#8b949e'};">${item.promoter_unlock_30d_pct ? item.promoter_unlock_30d_pct.toFixed(1) + '%' : '0.0%'}</td>
        <td>${item.days_to_promoter_unlock === 9999 ? 'CLEARED' : item.days_to_promoter_unlock + 'd'}</td>
      `;
      tr.onclick = () => window.selectSymbol(item.symbol);
      tbody.appendChild(tr);
    });
  }

  function filterAlphaGrid(query) {
    if (!window.TERMINAL_STATE.alphaData) return;
    query = (query || '').toUpperCase().trim();
    if (!query) {
      renderAlphaGrid(window.TERMINAL_STATE.alphaData);
      return;
    }
    const filtered = window.TERMINAL_STATE.alphaData.filter(i => i.symbol.includes(query));
    renderAlphaGrid(filtered);
  }

  // Screen [3]: Risk Monitor Fetch & Render
  async function refreshRiskData() {
    fetchSymbolRisk(window.TERMINAL_STATE.activeSymbol);
  }

  async function fetchSymbolRisk(symbol) {
    try {
      const resp = await fetch('/api/v1/terminal/screen/risk?symbol=' + encodeURIComponent(symbol));
      if (!resp.ok) return;
      const json = await resp.json();
      const data = json.data || {};
      window.TERMINAL_STATE.riskData = data;

      if (data.portfolio_var_95) {
        const el = document.getElementById('risk-var-val');
        if (el) el.textContent = (data.portfolio_var_95).toFixed(2) + '%';
      }
      if (data.portfolio_cvar_95) {
        const el = document.getElementById('risk-cvar-val');
        if (el) el.textContent = (data.portfolio_cvar_95).toFixed(2) + '%';
      }

      // Populate HRP Allocations
      const hrpBody = document.getElementById('risk-hrp-body');
      if (hrpBody && data.hrp_allocation) {
        hrpBody.innerHTML = '';
        data.hrp_allocation.forEach(row => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td style="font-weight:700; color:#58a6ff;">${row.symbol}</td>
            <td>${row.cluster || 'Cluster A'}</td>
            <td style="font-weight:700; color:#3fb950;">${row.weight.toFixed(1)}%</td>
            <td>${row.risk_contrib ? row.risk_contrib.toFixed(1) + '%' : '--'}</td>
            <td>${row.volatility_20d ? (row.volatility_20d * 100).toFixed(1) + '%' : '18.4%'}</td>
          `;
          tr.onclick = () => window.selectSymbol(row.symbol);
          hrpBody.appendChild(tr);
        });
      }

      // Populate Broker HHI Table
      const brokerBody = document.getElementById('risk-broker-body');
      if (brokerBody && data.broker_hhi) {
        brokerBody.innerHTML = '';
        data.broker_hhi.forEach(b => {
          const tr = document.createElement('tr');
          const isHigh = (b.hhi || 0) > 2500;
          tr.innerHTML = `
            <td style="font-weight:700; color:#c9d1d9;">#${b.broker_id}</td>
            <td>${b.name || 'Broker ' + b.broker_id}</td>
            <td style="font-weight:700; color:${isHigh ? '#f85149' : '#58a6ff'};">${b.hhi}</td>
            <td>${b.dominance_pct ? b.dominance_pct.toFixed(1) + '%' : '--'}</td>
            <td>${isHigh ? '<span class="badge-sell">CONCENTRATED</span>' : '<span class="badge-buy">ACCUMULATING</span>'}</td>
          `;
          brokerBody.appendChild(tr);
        });
      }
    } catch (e) {
      console.warn('Risk fetch error:', e);
    }
  }

  // Screen [4]: Forecast Data Fetch & Canvas Corridor Redraw
  async function refreshForecastData() {
    fetchSymbolForecast(window.TERMINAL_STATE.activeSymbol);
  }

  async function fetchSymbolForecast(symbol) {
    try {
      const resp = await fetch('/api/v1/terminal/screen/forecast?symbol=' + encodeURIComponent(symbol));
      if (!resp.ok) return;
      const json = await resp.json();
      const data = json.data || {};
      window.TERMINAL_STATE.forecastData = data;

      // Populate Sidebar Ranking
      const rankBody = document.getElementById('forecast-rank-body');
      if (rankBody && data.ranked_forecasts) {
        rankBody.innerHTML = '';
        data.ranked_forecasts.slice(0, 50).forEach(item => {
          const tr = document.createElement('tr');
          tr.id = 'fc-row-' + item.symbol;
          if (item.symbol === window.TERMINAL_STATE.activeSymbol) tr.classList.add('selected-row');

          const expSign = item.p50_exp >= 0 ? '+' : '';
          const expColor = item.p50_exp >= 0 ? '#3fb950' : '#f85149';
          tr.innerHTML = `
            <td style="font-weight:700; color:#58a6ff;">${item.symbol}</td>
            <td>${item.latest_close.toFixed(1)}</td>
            <td style="font-weight:700; color:${expColor};">${expSign}${item.p50_exp.toFixed(1)}%</td>
            <td style="color:#8b949e; font-size:10px;">${item.p10_exp.toFixed(1)}% ~ ${item.p90_exp.toFixed(1)}%</td>
          `;
          tr.onclick = () => window.selectSymbol(item.symbol);
          rankBody.appendChild(tr);
        });
      }

      renderForecastCanvas(data);
    } catch (e) {
      console.warn('Forecast fetch error:', e);
    }
  }

  // 60 FPS HTML5 Canvas Quantile Corridor Redraw Routine
  function renderForecastCanvas(data) {
    data = data || window.TERMINAL_STATE.forecastData;
    if (!data) return;

    const canvas = document.getElementById('forecastCanvasElement');
    if (!canvas) return;
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const p10 = data.p10_curve || [];
    const p50 = data.p50_curve || [];
    const p90 = data.p90_curve || [];
    const n = Math.max(p10.length, p50.length, p90.length);
    if (n === 0) return;

    let minY = Math.min(...p10, ...p50, ...p90);
    let maxY = Math.max(...p10, ...p50, ...p90);
    const pad = (maxY - minY) * 0.15 || 10;
    minY -= pad;
    maxY += pad;

    const padLeft = 65;
    const padRight = 35;
    const padTop = 35;
    const padBottom = 40;
    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    const getX = i => padLeft + (i / (n - 1)) * plotW;
    const getY = val => padTop + plotH - ((val - minY) / (maxY - minY)) * plotH;

    // Grid lines
    ctx.strokeStyle = '#21262d';
    ctx.lineWidth = 1;
    for (let g = 0; g <= 4; g++) {
      const yVal = minY + (g / 4) * (maxY - minY);
      const yPx = getY(yVal);
      ctx.beginPath();
      ctx.moveTo(padLeft, yPx);
      ctx.lineTo(w - padRight, yPx);
      ctx.stroke();

      ctx.fillStyle = '#8b949e';
      ctx.font = '10px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(yVal.toFixed(1), padLeft - 8, yPx + 3);
    }

    // Shaded Confidence Corridor
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
    ctx.fillStyle = 'rgba(88, 166, 255, 0.08)';
    ctx.fill();

    // P90 Line (Green Upside)
    ctx.beginPath();
    ctx.strokeStyle = '#3fb950';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p90[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // P10 Line (Red Downside)
    ctx.beginPath();
    ctx.strokeStyle = '#f85149';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p10[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // P50 Median Line (Solid Blue/Cyan)
    ctx.beginPath();
    ctx.strokeStyle = '#58a6ff';
    ctx.lineWidth = 2.5;
    ctx.setLineDash([]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p50[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Points on P50 Curve
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p50[i]);
      ctx.fillStyle = '#0d1117';
      ctx.strokeStyle = '#58a6ff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#8b949e';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('D+' + (i + 1), x, h - padBottom + 16);
    }
  }

  window.addEventListener('resize', () => {
    if (window.TERMINAL_STATE.activeScreen === 'forecast') {
      renderForecastCanvas();
    }
  });

  // Background WebSocket Message Dispatcher
  window.handleWorkspaceMessage = function(payload) {
    if (!payload) return;
    if (payload.type === 'TELEMETRY' && payload.data) {
      const seqEl = document.getElementById('footer-seqlock-seq');
      if (seqEl) seqEl.textContent = (payload.data.seqlock_seq || 0).toLocaleString();
      const latEl = document.getElementById('footer-pipeline-latency');
      if (latEl && payload.data.pipeline_latency_us) {
        latEl.textContent = payload.data.pipeline_latency_us.toFixed(1) + ' µs';
      }
    } else if (payload.type === 'ALPHA_DATA' && payload.data) {
      window.TERMINAL_STATE.alphaData = payload.data;
      if (window.TERMINAL_STATE.activeScreen === 'alpha') {
        renderAlphaGrid(payload.data);
      }
    } else if (payload.type === 'RISK_DATA' && payload.data) {
      window.TERMINAL_STATE.riskData = payload.data;
      if (window.TERMINAL_STATE.activeScreen === 'risk') {
        fetchSymbolRisk(window.TERMINAL_STATE.activeSymbol);
      }
    } else if (payload.type === 'FORECAST_DATA' && payload.data) {
      window.TERMINAL_STATE.forecastData = payload.data;
      if (window.TERMINAL_STATE.activeScreen === 'forecast') {
        renderForecastCanvas(payload.data);
      }
    } else if (payload.type === 'SYMBOL_CHANGED' && payload.data) {
      if (payload.data.forecast) {
        window.TERMINAL_STATE.forecastData = payload.data.forecast;
        renderForecastCanvas(payload.data.forecast);
      }
      if (payload.data.risk) {
        window.TERMINAL_STATE.riskData = payload.data.risk;
      }
    }
  };

  function initGlobalTerminalSocket() {
    if (window.terminalSocket && window.terminalSocket.readyState === WebSocket.OPEN) {
      globalWs = window.terminalSocket;
      return;
    }
    const loc = window.location;
    const wsUrl = (loc.protocol === 'https:' ? 'wss://' : 'ws://') + loc.host + '/ws/pulse';
    try {
      globalWs = new WebSocket(wsUrl);
      globalWs.onmessage = function(event) {
        try {
          const payload = JSON.parse(event.data);
          window.handleWorkspaceMessage(payload);
        } catch (err) {}
      };
      globalWs.onclose = function() {
        setTimeout(initGlobalTerminalSocket, 3000);
      };
    } catch (err) {}
  }
  initGlobalTerminalSocket();
"""

# ==============================================================================
# ASSEMBLE COMPLETE TERMINAL HTML FILE
# ==============================================================================

# Insert CSS into <head>
html_head = clean_html[:head_close] + "<style>\n" + state_driven_css + "\n</style>\n" + clean_html[head_close:root_start]

# Screen [1] wrap original_terminal_root
original_terminal_root = clean_html[root_start:root_end]
screen_tradingdesk_html = f"""
    <!-- SCREEN [1]: TRADING DESK & EXECUTION TAPE -->
    <section id="screen-tradingdesk" class="workspace-screen">
{original_terminal_root}
    </section>
"""

# Full viewport main block
viewport_block = (
    navbar_and_shell_start +
    screen_launchpad_html +
    screen_tradingdesk_html +
    screen_alpha_html +
    screen_risk_html +
    screen_forecast_html +
    shell_footer_html
)

html_post_root = clean_html[root_end:]
body_close = html_post_root.rfind('</body>')
assert body_close != -1, "Could not find </body>"

final_terminal_html = (
    html_head +
    viewport_block +
    html_post_root[:body_close] +
    "\n  <script>\n" + state_manager_js + "\n  </script>\n" +
    html_post_root[body_close:]
)

# Write to pulse_terminal/index.html
with open(TARGET_INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(final_terminal_html)

# Write to templates/terminal.html
with open(TARGET_TEMPLATE_PATH, "w", encoding="utf-8") as f:
    f.write(final_terminal_html)

print("Successfully generated:")
print(f"  - {TARGET_INDEX_PATH} ({len(final_terminal_html)} bytes)")
print(f"  - {TARGET_TEMPLATE_PATH} ({len(final_terminal_html)} bytes)")
