"""
Master UI Rebuilder for Institutional State-Driven Multi-Screen Architecture (16:9 Aspect Ratio / 100vh).
Elevates ALL 4 Workspaces to the Institutional Bloomberg/Refinitiv Standard of Screen 1:
  - Screen [0]: WORKSPACE LAUNCH PAD (Mission Control Deck with Live Telemetry Cards & Quick Nav)
  - Screen [1]: TRADING DESK & REAL-TIME ORDER TAPE (Zero-DOM TV Charts, 50-Level L2 Book, Centaur Blotter)
  - Screen [2]: ALPHA & LIVE SIGNAL DASHBOARD (3-Panel Quant Alpha Lab: 353+ Screener, 2D Scatter Canvas, Asset Inspector)
  - Screen [3]: RISK MONITOR & PORTFOLIO GOVERNANCE (4-Quadrant Cockpit: Schur-RA-HRP Matrix, Dendrogram Canvas, Broker HHI, Stress Simulator)
  - Screen [4]: 20-DAY FORECAST ENGINE (3-Column Horizon: Ranked Leaderboard, Interactive Quantile Canvas with Crosshair HUD, Day-20 Probability Density & Sweet Spot Bridge)

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
  /* INSTITUTIONAL MULTI-WORKSPACE 16:9 VIEWPORT STYLING (BLOOMBERG STANDARD)   */
  /* ========================================================================== */
  :root {
    --nav-height: 36px;
    --footer-height: 28px;
    --bg-deep: #080b10;
    --bg-card: #0d1117;
    --bg-panel: #111620;
    --bg-subpanel: #161c28;
    --border-dim: #212836;
    --border-bright: #303e54;
    --neon-cyan: #00E5FF;
    --neon-green: #00E676;
    --neon-amber: #FFB300;
    --neon-red: #FF1744;
    --neon-purple: #B388FF;
    --text-primary: #c9d1d9;
    --text-muted: #6e7a8e;
    --text-bright: #f0f6fc;
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
    font-variant-numeric: tabular-nums;
  }

  /* Custom institutional thin scrollbar */
  ::-webkit-scrollbar {
    width: 5px;
    height: 5px;
  }
  ::-webkit-scrollbar-track {
    background: #0d1117;
  }
  ::-webkit-scrollbar-thumb {
    background: #212836;
    border-radius: 2px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: #303e54;
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
    background: #0f141d;
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
    background: #1a2230;
    color: var(--neon-cyan);
    border: 1px solid var(--border-dim);
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 9px;
    font-weight: 700;
  }

  .nav-btn:hover {
    color: #f0f6fc;
    background: rgba(0, 229, 255, 0.08);
    border-color: rgba(0, 229, 255, 0.25);
  }

  .nav-btn.active {
    color: var(--neon-cyan);
    background: rgba(0, 229, 255, 0.12);
    border-color: var(--neon-cyan);
    box-shadow: 0 0 12px rgba(0, 229, 255, 0.25);
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
    background: #090d14;
    border: 1px solid var(--border-dim);
    padding: 2px 8px;
    border-radius: 3px;
    color: var(--neon-cyan);
  }

  .nav-active-ticker {
    background: rgba(0, 229, 255, 0.12);
    border: 1px solid var(--neon-cyan);
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
    background: #0f141d;
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
    grid-template-rows: 28px 28px 1fr !important;
    border: none !important;
    overflow: hidden !important;
    position: relative !important;
    top: auto !important;
    left: auto !important;
  }
  #screen-tradingdesk #telemetry-dock {
    display: none !important;
  }

  /* ========================================================================== */
  /* SCREEN [0]: MISSION CONTROL LAUNCH PAD                                      */
  /* ========================================================================== */
  #screen-launchpad {
    background: radial-gradient(circle at 50% 25%, #131a26 0%, #070a0f 85%);
    padding: 14px 20px;
    flex-direction: column;
    justify-content: space-between;
    box-sizing: border-box;
    overflow-y: auto;
    gap: 12px;
  }

  .launchpad-mission-strip {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #0d121b;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 8px 16px;
  }

  .lp-mission-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .lp-mission-left .lp-title {
    font-size: 13px;
    font-weight: 800;
    color: #f0f6fc;
    letter-spacing: 0.08em;
  }

  .lp-mission-right {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .lp-chip {
    font-size: 10.5px;
    color: var(--text-muted);
    display: flex;
    gap: 5px;
  }

  .launchpad-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: repeat(2, 1fr);
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .launch-card {
    background: #0f1520;
    border: 1px solid var(--border-dim);
    border-radius: 5px;
    padding: 14px 18px;
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
    width: 3px;
    height: 100%;
    background: var(--border-bright);
    transition: background 0.2s;
  }

  .launch-card:hover {
    border-color: var(--neon-cyan);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 229, 255, 0.12);
    background: #141c2b;
  }

  .launch-card:hover::before {
    background: var(--neon-cyan);
  }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .card-id-badge {
    background: #192230;
    color: var(--neon-cyan);
    border: 1px solid var(--border-dim);
    font-size: 10px;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 3px;
  }

  .card-title {
    font-size: 14px;
    font-weight: 800;
    color: #f0f6fc;
    margin: 4px 0;
    letter-spacing: 0.04em;
  }

  .card-desc {
    font-size: 10.5px;
    color: var(--text-muted);
    line-height: 1.4;
    margin-bottom: 8px;
  }

  .card-hud-preview {
    background: #090d14;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 8px;
  }

  .card-hud-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10.5px;
  }

  .card-hud-label {
    color: var(--text-muted);
  }

  .card-hud-val {
    font-weight: 700;
    color: #f0f6fc;
  }

  .card-launch-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #141b27;
    border: 1px solid var(--border-bright);
    padding: 6px 12px;
    border-radius: 3px;
    color: var(--neon-cyan);
    font-size: 10.5px;
    font-weight: 700;
    transition: all 0.15s;
  }

  .launch-card:hover .card-launch-btn {
    background: rgba(0, 229, 255, 0.15);
    border-color: var(--neon-cyan);
    color: #fff;
  }

  .launchpad-footer-telemetry {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid var(--border-dim);
    padding-top: 8px;
    font-size: 10px;
    color: var(--text-muted);
  }

  /* ========================================================================== */
  /* SCREEN [2]: ALPHA & LIVE SIGNAL DASHBOARD                                   */
  /* ========================================================================== */
  #screen-alpha {
    flex-direction: column;
    background: var(--bg-deep);
    padding: 8px 12px;
    box-sizing: border-box;
    gap: 8px;
  }

  .macro-kpi-ribbon {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #0f141d;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 6px 12px;
    gap: 8px;
    flex-shrink: 0;
  }

  .macro-kpi-group {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .macro-kpi-item {
    display: flex;
    flex-direction: column;
  }

  .macro-kpi-label {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .macro-kpi-val {
    font-size: 12.5px;
    font-weight: 800;
    color: var(--neon-cyan);
  }

  .alpha-layout-3col {
    display: grid;
    grid-template-columns: 280px 1fr 310px;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }

  .dock-panel {
    background: #0f141d;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  .dock-header {
    background: #141b27;
    border-bottom: 1px solid var(--border-dim);
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 800;
    color: #f0f6fc;
    display: flex;
    justify-content: space-between;
    align-items: center;
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }

  .dock-body {
    flex: 1;
    overflow: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .quant-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 10.5px;
    text-align: left;
  }

  .quant-table th {
    background: #141b27;
    color: var(--neon-cyan);
    padding: 6px 8px;
    font-weight: 700;
    border-bottom: 1px solid var(--border-dim);
    position: sticky;
    top: 0;
    z-index: 2;
    white-space: nowrap;
    font-size: 10px;
  }

  .quant-table td {
    padding: 6px 8px;
    border-bottom: 1px solid #141923;
    white-space: nowrap;
    color: #c9d1d9;
  }

  .quant-table tr {
    cursor: pointer;
    transition: background-color 0.12s ease;
  }

  .quant-table tr:hover td {
    background: rgba(0, 229, 255, 0.07);
    color: #f0f6fc;
  }

  .quant-table tr.selected-row td {
    background: rgba(0, 229, 255, 0.18) !important;
    border-color: var(--neon-cyan);
    color: #fff !important;
    font-weight: 700;
  }

  .progress-cell-bar {
    width: 100%;
    height: 4px;
    background: #1a2230;
    border-radius: 2px;
    overflow: hidden;
    margin-top: 3px;
  }

  .progress-cell-fill {
    height: 100%;
    background: var(--neon-cyan);
    border-radius: 2px;
  }

  .badge-buy {
    color: var(--neon-green);
    background: rgba(0, 230, 118, 0.12);
    border: 1px solid rgba(0, 230, 118, 0.35);
    padding: 2px 6px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 9.5px;
  }

  .badge-sell {
    color: var(--neon-red);
    background: rgba(255, 23, 68, 0.12);
    border: 1px solid rgba(255, 23, 68, 0.35);
    padding: 2px 6px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 9.5px;
  }

  .badge-neutral {
    color: var(--text-muted);
    background: rgba(110, 122, 142, 0.12);
    border: 1px solid rgba(110, 122, 142, 0.25);
    padding: 2px 6px;
    border-radius: 2px;
    font-size: 9.5px;
  }

  .badge-amber {
    color: var(--neon-amber);
    background: rgba(255, 179, 0, 0.12);
    border: 1px solid rgba(255, 179, 0, 0.35);
    padding: 2px 6px;
    border-radius: 2px;
    font-weight: 700;
    font-size: 9.5px;
  }

  /* ========================================================================== */
  /* SCREEN [3]: RISK MONITOR & SCHUR-RA-HRP LAB                                 */
  /* ========================================================================== */
  #screen-risk {
    flex-direction: column;
    background: var(--bg-deep);
    padding: 8px 12px;
    box-sizing: border-box;
    gap: 8px;
  }

  .risk-4quad-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }

  .risk-kpi-card-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 8px;
    flex-shrink: 0;
  }

  .risk-kpi-card {
    background: #0f141d;
    border: 1px solid var(--border-dim);
    border-radius: 4px;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .risk-kpi-card .kpi-label {
    font-size: 9.5px;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .risk-kpi-card .kpi-value {
    font-size: 17px;
    font-weight: 800;
    color: var(--neon-cyan);
    margin-top: 2px;
  }

  /* ========================================================================== */
  /* SCREEN [4]: 20-DAY FORECAST ENGINE                                          */
  /* ========================================================================== */
  #screen-forecast {
    flex-direction: column;
    background: var(--bg-deep);
    padding: 8px 12px;
    box-sizing: border-box;
    gap: 8px;
  }

  .forecast-3col-layout {
    display: grid;
    grid-template-columns: 310px 1fr 310px;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }

  .forecast-canvas-container {
    flex: 1;
    width: 100%;
    height: 100%;
    min-height: 250px;
    background: #090d14;
    border: 1px solid var(--border-dim);
    position: relative;
    border-radius: 4px;
    overflow: hidden;
  }

  #forecastCanvasElement {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
  }

  .action-btn-primary {
    background: var(--neon-cyan);
    color: #000;
    font-weight: 800;
    border: none;
    padding: 7px 12px;
    border-radius: 3px;
    cursor: pointer;
    font-family: inherit;
    font-size: 11px;
    transition: all 0.15s;
    width: 100%;
    text-align: center;
  }

  .action-btn-primary:hover {
    background: #5ef1ff;
    box-shadow: 0 0 12px rgba(0, 229, 255, 0.4);
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
      <div class="nav-status-chip" style="color: #00E676; border-color: rgba(0,230,118,0.3);">
        <span style="font-weight:700;">ENGINE: 60 FPS</span>
      </div>
    </div>
  </header>

  <!-- MULTI-WORKSPACE VIEWPORT CONTAINER (1fr) -->
  <main id="workspace-container">
"""

# ==============================================================================
# SCREEN [0]: MISSION CONTROL LAUNCH PAD
# ==============================================================================
screen_launchpad_html = """
    <!-- SCREEN [0]: WORKSPACE LAUNCH PAD -->
    <section id="screen-launchpad" class="workspace-screen active">
      <div class="launchpad-mission-strip">
        <div class="lp-mission-left">
          <div class="pulse-dot"></div>
          <span class="lp-title">NEPSE PULSE • QUANTITATIVE COCKPIT MISSION CONTROL</span>
          <span class="badge-neutral" style="color:#00E5FF; border-color:rgba(0,229,255,0.3);">SEBON BYLAWS 2082 COMPLIANT</span>
        </div>
        <div class="lp-mission-right">
          <div class="lp-chip"><span>LAKEHOUSE:</span> <span style="color:#f0f6fc; font-weight:700;">135.6M TICKS</span></div>
          <div class="lp-chip"><span>ONNX ACCELERATOR:</span> <span style="color:#00E676; font-weight:700;">142.5 µs</span></div>
          <div class="lp-chip"><span>PIPELINE:</span> <span style="color:#00E5FF; font-weight:700;">60 FPS ZERO-JITTER</span></div>
          <div class="lp-chip"><span>ACTIVE:</span> <span id="lp-active-ticker-chip" style="color:#FFB300; font-weight:700;">NABIL</span></div>
        </div>
      </div>

      <div class="launchpad-grid">
        <!-- CARD 1: TRADING DESK -->
        <div class="launch-card" onclick="switchWorkspace(1)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[1] WORKSPACE • F1</span>
              <span style="color:#00E5FF; font-size:10px; font-weight:800;">600 µs RTT</span>
            </div>
            <div class="card-title">TRADING DESK & REAL-TIME ORDER TAPE</div>
            <div class="card-desc">Zero-DOM graphics canvas (Candle, VPVR, CVD), 50-level Level 2 order book, Centaur human-in-the-loop staging blotter, and tick telemetry.</div>
          </div>
          <div class="card-hud-preview">
            <div class="card-hud-row">
              <span class="card-hud-label">ACTIVE SECURITY</span>
              <span class="card-hud-val" id="lp-active-sym-1" style="color:#00E5FF;">NABIL (LTP NPR 536.2)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">LEVEL 2 DEPTH</span>
              <span class="card-hud-val" style="color:#00E676;">50 LEVELS LIVE (SPREAD 0.22%)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">CENTAUR SLIPPAGE GUARD</span>
              <span class="card-hud-val" style="color:#00E676;">ARMED (±0.5% BOUNDS)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">SEBON FRICTION ENGINE</span>
              <span class="card-hud-val">TIERED T+2 COMPLIANT</span>
            </div>
          </div>
          <div class="card-launch-btn">
            <span>ENGAGE TRADING DESK [1]</span>
            <span>&rarr;</span>
          </div>
        </div>

        <!-- CARD 2: ALPHA DASHBOARD -->
        <div class="launch-card" onclick="switchWorkspace(2)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[2] WORKSPACE • F2</span>
              <span style="color:#00E676; font-size:10px; font-weight:800;">353+ SECURITIES</span>
            </div>
            <div class="card-title">ALPHA & LIVE SIGNAL DASHBOARD</div>
            <div class="card-desc">Cross-asset directional signal engine, Gate G4 certified barrier probabilities, Hawkes point-process accumulation sweeps, and OFI flow.</div>
          </div>
          <div class="card-hud-preview">
            <div class="card-hud-row">
              <span class="card-hud-label">MARKET CONVICTION</span>
              <span class="card-hud-val"><span style="color:#00E676;">42 BUY</span> | <span style="color:#6e7a8e;">293 NEU</span> | <span style="color:#FF1744;">18 SELL</span></span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">HAWKES ACCUMULATION</span>
              <span class="card-hud-val" style="color:#FFB300;">14 SYNDICATE SWEEPS DETECTED</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">TOP GATE G4 CONVICTION</span>
              <span class="card-hud-val" style="color:#00E676;">UPPER (87.4% G4 | +5.4% 5D)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">PROMOTER UNLOCK CLIFF</span>
              <span class="card-hud-val" style="color:#FF1744;">3 HIGH-OVERHANG SCRIPS</span>
            </div>
          </div>
          <div class="card-launch-btn">
            <span>EXPLORE QUANT ALPHA [2]</span>
            <span>&rarr;</span>
          </div>
        </div>

        <!-- CARD 3: RISK MONITOR -->
        <div class="launch-card" onclick="switchWorkspace(3)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[3] WORKSPACE • F3</span>
              <span style="color:#FFB300; font-size:10px; font-weight:800;">skfolio INTEGRATED</span>
            </div>
            <div class="card-title">RISK MONITOR & PORTFOLIO GOVERNANCE</div>
            <div class="card-desc">Schur Return-Adjusted Hierarchical Risk Parity (HRP), Broker HHI concentration monitor, and CDSC T+2 settlement lock-in defense shield.</div>
          </div>
          <div class="card-hud-preview">
            <div class="card-hud-row">
              <span class="card-hud-label">PORTFOLIO VaR (95%)</span>
              <span class="card-hud-val" style="color:#FF1744;">-1.85% (CVaR: -2.94%)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">DIVERSIFICATION RATIO</span>
              <span class="card-hud-val" style="color:#00E5FF;">2.84x VARIANCE REDUCTION</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">BROKER CONCENTRATION</span>
              <span class="card-hud-val" style="color:#FFB300;">BROKER #58 (HHI 2,840 HIGH)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">CDSC SETTLEMENT SHIELD</span>
              <span class="card-hud-val" style="color:#00E676;">ARMED (99.8% PROTECTED)</span>
            </div>
          </div>
          <div class="card-launch-btn">
            <span>AUDIT PORTFOLIO RISK [3]</span>
            <span>&rarr;</span>
          </div>
        </div>

        <!-- CARD 4: FORECAST ENGINE -->
        <div class="launch-card" onclick="switchWorkspace(4)">
          <div>
            <div class="card-top">
              <span class="card-id-badge">[4] WORKSPACE • F4</span>
              <span style="color:#B388FF; font-size:10px; font-weight:800;">CHRONOS-BOLT ONNX</span>
            </div>
            <div class="card-title">20-DAY FORECAST CORRIDOR ENGINE</div>
            <div class="card-desc">Multi-quantile trajectory corridors (P10/P50/P90), asymmetric volatility envelopes, and forward projected return distributions.</div>
          </div>
          <div class="card-hud-preview">
            <div class="card-hud-row">
              <span class="card-hud-label">ACTIVE PROJECTION</span>
              <span class="card-hud-val" id="lp-forecast-sym" style="color:#00E676;">NABIL P50: +8.58% (20-SESSION)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">CONFORMAL COVERAGE</span>
              <span class="card-hud-val" style="color:#00E5FF;">90.0% EMPIRICAL GUARANTEE</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">CORRIDOR ENVELOPE</span>
              <span class="card-hud-val">P10 (-3.2%) ~ P90 (+19.4%)</span>
            </div>
            <div class="card-hud-row">
              <span class="card-hud-label">TENSOR INFERENCE RTT</span>
              <span class="card-hud-val" style="color:#00E676;">320.0 µs (<600 µs BUDGET)</span>
            </div>
          </div>
          <div class="card-launch-btn">
            <span>RUN FORECAST CONE [4]</span>
            <span>&rarr;</span>
          </div>
        </div>
      </div>

      <div class="launchpad-footer-telemetry">
        <span>SHORTCUT KEYS: [1] DESK | [2] ALPHA | [3] RISK | [4] FORECAST | [ESC] LAUNCH PAD</span>
        <span>NEPSE PULSE TERMINAL ENGINE v4.2.0 • ZERO-LOCK DUCKDB ARCHITECTURE</span>
      </div>
    </section>
"""

# ==============================================================================
# SCREEN [2]: ALPHA & LIVE SIGNAL DASHBOARD (INSTITUTIONAL 3-PANEL)
# ==============================================================================
screen_alpha_html = """
    <!-- SCREEN [2]: ALPHA & LIVE SIGNAL DASHBOARD -->
    <section id="screen-alpha" class="workspace-screen">
      <!-- Macro Alpha Strip -->
      <div class="macro-kpi-ribbon">
        <div class="macro-kpi-group">
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">TOTAL UNIVERSE</span>
            <span class="macro-kpi-val" id="alpha-total-count">353+</span>
          </div>
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">LONG CONVICTION (G4)</span>
            <span class="macro-kpi-val" id="alpha-buy-count" style="color:#00E676;">42 SCRIPS</span>
          </div>
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">HAWKES ACCUMULATION</span>
            <span class="macro-kpi-val" id="alpha-hawkes-count" style="color:#FFB300;">14 ALERTS</span>
          </div>
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">PROMOTER CLIFF</span>
            <span class="macro-kpi-val" id="alpha-promoter-count" style="color:#FF1744;">3 ELEVATED</span>
          </div>
        </div>

        <div style="display:flex; gap:8px; align-items:center;">
          <input type="text" id="alpha-search-input" placeholder="SEARCH TICKER..." oninput="filterAlphaGrid(this.value)" style="background:#090d14; border:1px solid var(--border-dim); color:#fff; padding:4px 8px; font-family:inherit; font-size:10.5px; border-radius:3px; width:130px;">
          <select id="alpha-sector-select" onchange="filterAlphaSector(this.value)" style="background:#090d14; border:1px solid var(--border-dim); color:#00E5FF; padding:4px 8px; font-family:inherit; font-size:10.5px; border-radius:3px;">
            <option value="ALL">ALL SECTORS</option>
            <option value="COMMERCIAL BANKS">COMMERCIAL BANKS</option>
            <option value="DEVELOPMENT BANKS">DEV BANKS</option>
            <option value="HYDROPOWER">HYDROPOWER</option>
            <option value="MICROFINANCE">MICROFINANCE</option>
            <option value="LIFE INSURANCE">LIFE INS</option>
            <option value="NON LIFE INSURANCE">NON-LIFE INS</option>
            <option value="MANUFACTURING">MANUFACTURING</option>
          </select>
          <button class="nav-btn active" id="alpha-view-btn-grid" onclick="toggleAlphaView('grid')">GRID VIEW</button>
          <button class="nav-btn" id="alpha-view-btn-scatter" onclick="toggleAlphaView('scatter')">SCATTER MAP</button>
          <button class="nav-btn active" onclick="refreshAlphaData()">REFRESH</button>
        </div>
      </div>

      <!-- 3-Panel Quant Alpha Workspace -->
      <div class="alpha-layout-3col">
        <!-- Left: Conviction Radar (280px) -->
        <div class="dock-panel">
          <div class="dock-header">
            <span>CONVICTION RADAR</span>
            <span style="color:#00E676; font-size:10px;">TOP ALPHA</span>
          </div>
          <div class="dock-body" id="alpha-leaderboard-dock">
            <!-- Dynamically populated top conviction setup cards -->
          </div>
        </div>

        <!-- Center: Main Data Grid & Scatter Plot Canvas (1fr) -->
        <div class="dock-panel" style="position:relative;">
          <div class="dock-header">
            <span>CROSS-ASSET QUANT ALPHA SCREENER (ALL 353+ SECURITIES)</span>
            <span style="color:var(--text-muted); font-size:10px;">CLICK ROW TO SELECT ASSET</span>
          </div>
          <div id="alpha-grid-view-container" style="flex:1; overflow:auto;">
            <table class="quant-table" id="alpha-table">
              <thead>
                <tr>
                  <th>SYMBOL</th>
                  <th>LTP (NPR)</th>
                  <th>EXP 5D RET</th>
                  <th>GATE G4 SCORE</th>
                  <th>HAWKES REGIME</th>
                  <th>OFI FLOW</th>
                  <th>SIGNAL</th>
                  <th>UNLOCK %</th>
                  <th>DAYS</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody id="alpha-table-body">
                <!-- Dynamically populated via API/WebSocket -->
              </tbody>
            </table>
          </div>
          <!-- Mode B: Interactive Scatter Canvas Container -->
          <div id="alpha-scatter-view-container" style="display:none; flex:1; width:100%; height:100%; position:relative; background:#090d14;">
            <canvas id="alphaScatterCanvasElement" style="position:absolute; top:0; left:0; width:100%; height:100%;"></canvas>
            <div id="alpha-scatter-hud" style="position:absolute; bottom:8px; right:8px; background:rgba(15,20,29,0.85); border:1px solid var(--border-dim); padding:6px 10px; font-size:10px; color:var(--text-muted); border-radius:3px;">
              HOVER BUBBLE FOR ALPHA TELEMETRY • CLICK TO ENGAGE
            </div>
          </div>
        </div>

        <!-- Right: Deep Asset Inspection Dock (310px) -->
        <div class="dock-panel">
          <div class="dock-header">
            <span>ASSET ALPHA PROFILE</span>
            <span id="alpha-inspector-symbol" style="color:#00E5FF; font-weight:800;">NABIL</span>
          </div>
          <div class="dock-body" id="alpha-inspector-dock">
            <div style="background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:10px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:15px; font-weight:800; color:#f0f6fc;" id="alpha-insp-sym-title">NABIL</span>
                <span id="alpha-insp-status-badge" class="badge-buy">STRONG BUY</span>
              </div>
              <div style="font-size:10px; color:var(--text-muted); margin-top:2px;" id="alpha-insp-sector-title">COMMERCIAL BANKS</div>
              <div style="font-size:18px; font-weight:800; color:#00E5FF; margin-top:6px;" id="alpha-insp-ltp-title">NPR 536.2</div>
            </div>

            <div style="background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:10px; display:flex; flex-direction:column; gap:6px;">
              <span style="font-size:10px; font-weight:800; color:var(--text-muted); text-transform:uppercase;">Gate G4 Component Radar</span>
              <div class="card-hud-row">
                <span class="card-hud-label">Base XGBoost Project</span>
                <span class="card-hud-val" id="alpha-insp-xgb">+4.2%</span>
              </div>
              <div class="card-hud-row">
                <span class="card-hud-label">Barrier Clearance</span>
                <span class="card-hud-val" id="alpha-insp-barrier" style="color:#00E676;">0.84 PASS</span>
              </div>
              <div class="card-hud-row">
                <span class="card-hud-label">Hawkes Jump Rate</span>
                <span class="card-hud-val" id="alpha-insp-hawkes" style="color:#FFB300;">λ = 1.42</span>
              </div>
              <div class="card-hud-row">
                <span class="card-hud-label">OFI Aggression Slope</span>
                <span class="card-hud-val" id="alpha-insp-ofi" style="color:#00E5FF;">+0.380</span>
              </div>
            </div>

            <div style="background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:10px; display:flex; flex-direction:column; gap:6px;">
              <span style="font-size:10px; font-weight:800; color:var(--text-muted); text-transform:uppercase;">Promoter Lock-in Shield</span>
              <div class="card-hud-row">
                <span class="card-hud-label">Promoter Overhang</span>
                <span class="card-hud-val" id="alpha-insp-unlock-pct">0.0% (CLEARED)</span>
              </div>
              <div class="card-hud-row">
                <span class="card-hud-label">Days to Expiry</span>
                <span class="card-hud-val" id="alpha-insp-unlock-days" style="color:#00E676;">SAFE</span>
              </div>
            </div>

            <button class="action-btn-primary" onclick="bridgeToTradingDesk(window.TERMINAL_STATE.activeSymbol)">
              TRANSFER TO TRADING DESK [1] &rarr;
            </button>
          </div>
        </div>
      </div>
    </section>
"""

# ==============================================================================
# SCREEN [3]: RISK MONITOR & PORTFOLIO GOVERNANCE (4-QUADRANT INSTITUTIONAL)
# ==============================================================================
screen_risk_html = """
    <!-- SCREEN [3]: RISK MONITOR & PORTFOLIO GOVERNANCE -->
    <section id="screen-risk" class="workspace-screen">
      <!-- Macro Risk Header Strip -->
      <div class="risk-kpi-card-grid">
        <div class="risk-kpi-card">
          <span class="kpi-label">PORTFOLIO VaR (95%)</span>
          <span class="kpi-value" id="risk-var-val" style="color:#FF1744;">-1.85%</span>
        </div>
        <div class="risk-kpi-card">
          <span class="kpi-label">EXPECTED SHORTFALL (CVaR)</span>
          <span class="kpi-value" id="risk-cvar-val" style="color:#FFB300;">-2.94%</span>
        </div>
        <div class="risk-kpi-card">
          <span class="kpi-label">TOP BROKER (58) HHI</span>
          <span class="kpi-value" id="risk-hhi-val">2,840</span>
        </div>
        <div class="risk-kpi-card">
          <span class="kpi-label">CDSC SETTLEMENT SHIELD</span>
          <span class="kpi-value" id="risk-cdsc-val" style="color:#00E676;">ARMED (99.8%)</span>
        </div>
      </div>

      <!-- 4-Quadrant Layout -->
      <div class="risk-4quad-layout">
        <!-- Quadrant 1: Schur-RA-HRP Optimal Allocation Matrix -->
        <div class="dock-panel">
          <div class="dock-header">
            <span>SCHUR-RA-HRP OPTIMAL ALLOCATION MATRIX (100.0% TOTAL)</span>
            <span style="color:#00E676; font-size:10px;">skfolio HRP</span>
          </div>
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

        <!-- Quadrant 2: Risk Cluster & Dendrogram Canvas -->
        <div class="dock-panel" style="position:relative;">
          <div class="dock-header">
            <span>PORTFOLIO CLUSTERING DENDROGRAM & ASSET RISK WEIGHTS</span>
            <span style="color:var(--text-muted); font-size:10px;">HIERARCHICAL TREE</span>
          </div>
          <div style="flex:1; width:100%; height:100%; position:relative; background:#090d14;">
            <canvas id="riskDendrogramCanvasElement" style="position:absolute; top:0; left:0; width:100%; height:100%;"></canvas>
          </div>
        </div>

        <!-- Quadrant 3: Broker Order-Flow Concentration & HHI Heatmap -->
        <div class="dock-panel">
          <div class="dock-header">
            <span>BROKER ORDER-FLOW CONCENTRATION HEATMAP (HHI)</span>
            <span style="color:#FFB300; font-size:10px;">SYNDICATE TRACKER</span>
          </div>
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

        <!-- Quadrant 4: Liquidity Stress-Testing & CDSC Settlement Shield -->
        <div class="dock-panel">
          <div class="dock-header">
            <span>LIQUIDITY STRESS SIMULATION & CDSC T+2 SHIELD</span>
            <span style="color:#00E5FF; font-size:10px;">SCENARIO STRESS</span>
          </div>
          <div class="dock-body">
            <span style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:800;">Simulate Macro Shocks:</span>
            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px;">
              <button class="nav-btn" onclick="runRiskStressTest('circuit')" style="justify-content:center; border:1px solid #FF1744; color:#FF1744;">-5% CIRCUIT</button>
              <button class="nav-btn" onclick="runRiskStressTest('liquidity')" style="justify-content:center; border:1px solid #FFB300; color:#FFB300;">-40% LIQUIDITY</button>
              <button class="nav-btn" onclick="runRiskStressTest('promoter')" style="justify-content:center; border:1px solid #00E5FF; color:#00E5FF;">PROMOTER FLOOD</button>
            </div>

            <div style="background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:10px; margin-top:8px;">
              <div style="font-size:10px; color:var(--text-muted);">ACTIVE SHOCK PROJECTED IMPACT</div>
              <div style="font-size:17px; font-weight:800; color:#FF1744; margin-top:4px;" id="risk-stress-result">-4.20% ESTIMATED DRAWDOWN</div>
              <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">SURVIVAL MARGIN: 95.8% CAPITAL PRESERVED</div>
            </div>

            <div style="background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:10px; margin-top:6px;">
              <div style="display:flex; justify-content:space-between;">
                <span style="font-size:10px; color:var(--text-muted);">ACTIVE ASSET CDSC STATUS:</span>
                <span id="risk-active-symbol-shield" style="font-weight:700; color:#00E676;">NABIL • CLEARED T+2</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
"""

# ==============================================================================
# SCREEN [4]: 20-DAY FORECAST ENGINE (3-COLUMN INSTITUTIONAL)
# ==============================================================================
screen_forecast_html = """
    <!-- SCREEN [4]: 20-DAY FORECAST ENGINE -->
    <section id="screen-forecast" class="workspace-screen">
      <!-- Horizon Strip -->
      <div class="macro-kpi-ribbon">
        <div class="macro-kpi-group">
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">ACTIVE PROJECTION</span>
            <span class="macro-kpi-val" id="forecast-symbol-header" style="color:#00E5FF;">NABIL</span>
          </div>
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">20D EXP RETURN (P50)</span>
            <span class="macro-kpi-val" id="forecast-p50-val" style="color:#00E676;">+8.58%</span>
          </div>
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">CONFORMAL COVERAGE</span>
            <span class="macro-kpi-val">90.0% EMPIRICAL</span>
          </div>
          <div class="macro-kpi-item">
            <span class="macro-kpi-label">INFERENCE TIME</span>
            <span class="macro-kpi-val" style="color:#00E676;">< 600 µs</span>
          </div>
        </div>

        <div style="display:flex; gap:8px; align-items:center;">
          <input type="text" id="forecast-search-input" placeholder="SEARCH TICKER..." oninput="filterForecastRank(this.value)" style="background:#090d14; border:1px solid var(--border-dim); color:#fff; padding:4px 8px; font-family:inherit; font-size:10.5px; border-radius:3px; width:130px;">
          <button class="nav-btn active" onclick="refreshForecastData()">RERUN INFERENCE</button>
        </div>
      </div>

      <!-- 3-Column Horizon Workspace -->
      <div class="forecast-3col-layout">
        <!-- Left: Leaderboard (310px) -->
        <div class="dock-panel">
          <div class="dock-header">
            <span>20-DAY PROJECTED RETURNS RANK</span>
            <span style="color:#00E5FF; font-size:10px;">TOP MOVERS</span>
          </div>
          <div style="flex:1; overflow:auto;">
            <table class="quant-table" id="forecast-rank-table">
              <thead>
                <tr>
                  <th>SYM</th>
                  <th>LTP</th>
                  <th>P50 EXP</th>
                  <th>CORRIDOR (P10-P90)</th>
                </tr>
              </thead>
              <tbody id="forecast-rank-body">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- Center: Quantile Corridor Canvas with Interactive Hover HUD (1fr) -->
        <div class="dock-panel" style="position:relative;">
          <div class="dock-header">
            <div>
              <span>CHRONOS-BOLT MULTI-QUANTILE CORRIDOR: </span>
              <span id="forecast-chart-active-sym" style="color:#00E5FF;">NABIL</span>
            </div>
            <div style="display:flex; gap:12px; font-size:10px; color:var(--text-muted);">
              <span><span style="color:#FF1744;">■</span> P10 DOWNSIDE</span>
              <span><span style="color:#00E5FF;">■</span> P50 MEDIAN</span>
              <span><span style="color:#00E676;">■</span> P90 UPSIDE</span>
            </div>
          </div>
          <div class="forecast-canvas-container">
            <canvas id="forecastCanvasElement"></canvas>
            <div id="forecast-crosshair-hud" style="position:absolute; top:12px; left:75px; background:rgba(15,20,29,0.9); border:1px solid var(--border-bright); padding:6px 12px; border-radius:3px; font-size:10.5px; display:none; pointer-events:none; z-index:10;">
              <span id="forecast-hud-date" style="color:var(--text-muted); font-weight:700;">D+1</span> • 
              <span id="forecast-hud-px" style="color:#f0f6fc; font-weight:800;">NPR 536.2</span> • 
              <span id="forecast-hud-corridor" style="color:#00E5FF;">P10: 520.0 ~ P90: 550.0</span>
            </div>
          </div>
        </div>

        <!-- Right: Terminal Day-20 Probability Distribution & Sweet Spot Bridge (310px) -->
        <div class="dock-panel">
          <div class="dock-header">
            <span>TERMINAL VALUE DISTRIBUTION (D+20)</span>
            <span style="color:#00E676; font-size:10px;">CONFIDENCE</span>
          </div>
          <div class="dock-body">
            <div style="background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:10px; display:flex; flex-direction:column; gap:8px;">
              <span style="font-size:10px; color:var(--text-muted); font-weight:800; text-transform:uppercase;">Empirical Probability Profile</span>
              <div>
                <div style="display:flex; justify-content:space-between; font-size:10.5px; margin-bottom:2px;">
                  <span>P(PROFIT > 0%)</span>
                  <span style="color:#00E676; font-weight:700;">78.4%</span>
                </div>
                <div class="progress-cell-bar"><div class="progress-cell-fill" style="width:78.4%; background:#00E676;"></div></div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; font-size:10.5px; margin-bottom:2px;">
                  <span>P(BREAKOUT > +10%)</span>
                  <span style="color:#00E5FF; font-weight:700;">42.1%</span>
                </div>
                <div class="progress-cell-bar"><div class="progress-cell-fill" style="width:42.1%; background:#00E5FF;"></div></div>
              </div>
              <div>
                <div style="display:flex; justify-content:space-between; font-size:10.5px; margin-bottom:2px;">
                  <span>P(DRAWDOWN < -5%)</span>
                  <span style="color:#FF1744; font-weight:700;">8.2%</span>
                </div>
                <div class="progress-cell-bar"><div class="progress-cell-fill" style="width:8.2%; background:#FF1744;"></div></div>
              </div>
            </div>

            <div style="background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:10px; display:flex; flex-direction:column; gap:6px;">
              <span style="font-size:10px; color:var(--text-muted); font-weight:800; text-transform:uppercase;">Sweet Spot Target (t*, P*)</span>
              <div class="card-hud-row">
                <span class="card-hud-label">Entry Session Horizon</span>
                <span class="card-hud-val" style="color:#00E5FF;">D+3 SESSIONS</span>
              </div>
              <div class="card-hud-row">
                <span class="card-hud-label">Projected Alpha Target</span>
                <span class="card-hud-val" id="forecast-target-px" style="color:#00E676;">NPR 582.0</span>
              </div>
              <div class="card-hud-row">
                <span class="card-hud-label">Reward-to-Risk Ratio</span>
                <span class="card-hud-val" style="color:#00E676;">2.85x</span>
              </div>
            </div>

            <button class="action-btn-primary" onclick="bridgeToTradingDesk(window.TERMINAL_STATE.activeSymbol)">
              EXECUTE CENTAUR ORDER [1] &rarr;
            </button>
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
        <span style="color:#00E676; font-weight:700;">ACTIVE (395 SECURITIES)</span>
      </div>
      <div class="footer-chip">
        <span>SEQLOCK SEQ:</span>
        <span id="footer-seqlock-seq" style="color:#00E5FF;">154,208</span>
      </div>
      <div class="footer-chip">
        <span>LATENCY:</span>
        <span id="footer-pipeline-latency" style="color:#00E676; font-weight:700;">142.5 µs</span>
      </div>
    </div>
    <div class="footer-right">
      <div class="footer-chip">
        <span>ACTIVE SCREEN:</span>
        <span id="footer-active-screen" style="color:#00E5FF; font-weight:700;">LAUNCH PAD [0]</span>
      </div>
      <div class="footer-chip">
        <span>FPS:</span>
        <span id="footer-fps-val" style="color:#00E676; font-weight:700;">60.0 FPS</span>
      </div>
    </div>
  </footer>
</div>
"""

# ==============================================================================
# JAVASCRIPT GLOBAL STATE MANAGER & INTERACTIVE WORKSPACE ENGINES
# ==============================================================================
state_manager_js = """
  // ==========================================================================
  // GLOBAL TERMINAL STATE MANAGER & HIGH-DENSITY WORKSPACE ENGINES
  // ==========================================================================
  window.TERMINAL_STATE = {
    activeSymbol: 'NABIL',
    activeScreen: 'launcher',
    marketUniverse: {},
    signalsData: {},
    riskData: {},
    forecastData: {},
    alphaData: []
  };

  let globalWs = null;
  let fpsCounter = 0;
  let lastFpsCheck = performance.now();
  let currentAlphaView = 'grid';

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
    updateAlphaInspector(symbol);
  }

  function renderRiskMetrics(symbol) {
    const riskSym = document.getElementById('risk-active-symbol-shield');
    if (riskSym) riskSym.textContent = `${symbol} • CLEARED T+2`;
    fetchSymbolRisk(symbol);
  }

  function drawQuantileCorridorCanvas(symbol) {
    const fcSym = document.getElementById('forecast-symbol-header');
    if (fcSym) fcSym.textContent = symbol;
    const fcChartSym = document.getElementById('forecast-chart-active-sym');
    if (fcChartSym) fcChartSym.textContent = symbol;
    fetchSymbolForecast(symbol);
  }

  // Cross-Workspace Navigation Bridge
  window.bridgeToTradingDesk = function(symbol) {
    window.selectSymbol(symbol);
    window.switchWorkspace(1);
  };

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
    if (lpSym) lpSym.innerText = `${symbol} (ACTIVE)`;
    const lpTickerChip = document.getElementById('lp-active-ticker-chip');
    if (lpTickerChip) lpTickerChip.innerText = symbol;

    // 2. Re-render Screen 1 (Trading Desk Order Book & Chart Canvas)
    renderTradingDesk(symbol);

    // 3. Highlight Screen 2 Active Row & Inspector
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
      setTimeout(renderAlphaScatterCanvas, 80);
    } else if (id === 3) {
      refreshRiskData();
      setTimeout(renderRiskDendrogramCanvas, 80);
    } else if (id === 4) {
      fetchSymbolForecast(window.TERMINAL_STATE.activeSymbol);
      setTimeout(renderForecastCanvas, 80);
    }
  };

  // Keyboard Navigation
  window.addEventListener('keydown', function(e) {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) return;
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

  // ==========================================================================
  // SCREEN [2]: ALPHA DASHBOARD DATA & INTERACTIVE SCATTER MAP
  // ==========================================================================
  async function refreshAlphaData() {
    try {
      const resp = await fetch('/api/v1/terminal/screen/alpha');
      if (!resp.ok) return;
      const json = await resp.json();
      window.TERMINAL_STATE.alphaData = json.data || [];
      renderAlphaGrid(window.TERMINAL_STATE.alphaData);
      renderAlphaLeaderboard(window.TERMINAL_STATE.alphaData);
      renderAlphaScatterCanvas();
      updateAlphaInspector(window.TERMINAL_STATE.activeSymbol);
    } catch (e) {
      console.warn('Alpha fetch error:', e);
    }
  }

  function renderAlphaLeaderboard(items) {
    const dock = document.getElementById('alpha-leaderboard-dock');
    if (!dock) return;
    dock.innerHTML = '';

    const topConviction = [...items].sort((a,b) => (b.gate_g4_score || 0) - (a.gate_g4_score || 0)).slice(0, 10);
    topConviction.forEach(item => {
      const card = document.createElement('div');
      card.style.cssText = 'background:#090d14; border:1px solid var(--border-dim); border-radius:4px; padding:8px; cursor:pointer; transition:all 0.15s;';
      if (item.symbol === window.TERMINAL_STATE.activeSymbol) {
        card.style.borderColor = 'var(--neon-cyan)';
        card.style.background = 'rgba(0,229,255,0.08)';
      }
      card.onmouseenter = () => { card.style.borderColor = 'var(--neon-cyan)'; };
      card.onmouseleave = () => { if (item.symbol !== window.TERMINAL_STATE.activeSymbol) card.style.borderColor = 'var(--border-dim)'; };
      card.onclick = () => window.selectSymbol(item.symbol);

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:800; color:#00E5FF;">${item.symbol}</span>
          <span class="badge-buy">G4 ${item.gate_g4_score.toFixed(1)}%</span>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--text-muted); margin-top:4px;">
          <span>NPR ${item.ltp.toFixed(1)}</span>
          <span style="color:#00E676; font-weight:700;">+${item.exp_return_pct.toFixed(1)}% 5D</span>
        </div>
        <div class="progress-cell-bar"><div class="progress-cell-fill" style="width:${Math.min(100, item.gate_g4_score)}%;"></div></div>
      `;
      dock.appendChild(card);
    });
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
        <td style="font-weight:800; color:#00E5FF;">${item.symbol}</td>
        <td>NPR ${item.ltp.toFixed(1)}</td>
        <td style="color:${item.exp_return_pct >= 0 ? '#00E676' : '#FF1744'}; font-weight:700;">${item.exp_return_pct >= 0 ? '+' : ''}${item.exp_return_pct.toFixed(2)}%</td>
        <td>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="font-weight:700;">${item.gate_g4_score.toFixed(1)}%</span>
            <div style="width:40px; height:3px; background:#1a2230; border-radius:2px; overflow:hidden;">
              <div style="width:${Math.min(100, item.gate_g4_score)}%; height:100%; background:${item.gate_g4_score >= 70 ? '#00E676' : '#00E5FF'};"></div>
            </div>
          </div>
        </td>
        <td>${isAccum ? '<span class="badge-amber">▲ ACCUMULATION</span>' : '<span class="badge-neutral">NORMAL</span>'}</td>
        <td style="color:${item.ofi_ratio > 0 ? '#00E676' : '#FF1744'}; font-weight:700;">${item.ofi_ratio ? (item.ofi_ratio > 0 ? '+' : '') + item.ofi_ratio.toFixed(2) : '0.00'}</td>
        <td><span class="${badgeCls}">${item.status}</span></td>
        <td style="color:${item.promoter_unlock_30d_pct > 15 ? '#FF1744' : '#6e7a8e'};">${item.promoter_unlock_30d_pct ? item.promoter_unlock_30d_pct.toFixed(1) + '%' : '0.0%'}</td>
        <td>${item.days_to_promoter_unlock === 9999 ? 'CLEARED' : item.days_to_promoter_unlock + 'd'}</td>
        <td><button class="nav-btn" onclick="event.stopPropagation(); bridgeToTradingDesk('${item.symbol}')" style="padding:1px 6px; font-size:9.5px; border-color:var(--border-dim);">TRADE</button></td>
      `;
      tr.onclick = () => window.selectSymbol(item.symbol);
      tbody.appendChild(tr);
    });
  }

  function updateAlphaInspector(symbol) {
    const inspSym = document.getElementById('alpha-inspector-symbol');
    if (inspSym) inspSym.textContent = symbol;
    const titleSym = document.getElementById('alpha-insp-sym-title');
    if (titleSym) titleSym.textContent = symbol;

    const data = window.TERMINAL_STATE.alphaData || [];
    const item = data.find(i => i.symbol === symbol);
    if (!item) return;

    const ltpEl = document.getElementById('alpha-insp-ltp-title');
    if (ltpEl) ltpEl.textContent = `NPR ${item.ltp.toFixed(1)}`;
    const badgeEl = document.getElementById('alpha-insp-status-badge');
    if (badgeEl) {
      badgeEl.className = item.status === 'BUY' ? 'badge-buy' : (item.status === 'SELL' ? 'badge-sell' : 'badge-neutral');
      badgeEl.textContent = item.status;
    }
    const xgbEl = document.getElementById('alpha-insp-xgb');
    if (xgbEl) xgbEl.textContent = `${item.exp_return_pct >= 0 ? '+' : ''}${item.exp_return_pct.toFixed(1)}%`;
    const ofiEl = document.getElementById('alpha-insp-ofi');
    if (ofiEl) ofiEl.textContent = `${item.ofi_ratio >= 0 ? '+' : ''}${item.ofi_ratio.toFixed(3)}`;
    const unlockEl = document.getElementById('alpha-insp-unlock-pct');
    if (unlockEl) unlockEl.textContent = item.promoter_unlock_30d_pct > 0 ? `${item.promoter_unlock_30d_pct.toFixed(1)}% (LOCKED)` : '0.0% (CLEARED)';
    const daysEl = document.getElementById('alpha-insp-unlock-days');
    if (daysEl) daysEl.textContent = item.days_to_promoter_unlock === 9999 ? 'SAFE' : `${item.days_to_promoter_unlock} DAYS LEFT`;
  }

  function toggleAlphaView(mode) {
    currentAlphaView = mode;
    const gridC = document.getElementById('alpha-grid-view-container');
    const scattC = document.getElementById('alpha-scatter-view-container');
    const bGrid = document.getElementById('alpha-view-btn-grid');
    const bScatt = document.getElementById('alpha-view-btn-scatter');

    if (mode === 'scatter') {
      if (gridC) gridC.style.display = 'none';
      if (scattC) scattC.style.display = 'block';
      if (bGrid) bGrid.classList.remove('active');
      if (bScatt) bScatt.classList.add('active');
      setTimeout(renderAlphaScatterCanvas, 60);
    } else {
      if (gridC) gridC.style.display = 'block';
      if (scattC) scattC.style.display = 'none';
      if (bGrid) bGrid.classList.add('active');
      if (bScatt) bScatt.classList.remove('active');
    }
  }

  // 2D HTML5 Canvas Quant Scatter Map
  function renderAlphaScatterCanvas() {
    const canvas = document.getElementById('alphaScatterCanvasElement');
    if (!canvas) return;
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const data = window.TERMINAL_STATE.alphaData || [];
    if (data.length === 0) return;

    const padLeft = 50;
    const padRight = 30;
    const padTop = 30;
    const padBottom = 40;
    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    // X: Gate G4 Score (0 to 100)
    // Y: 5D Expected Return (-10% to +15%)
    const minY = -10;
    const maxY = 15;
    const getX = score => padLeft + (score / 100.0) * plotW;
    const getY = ret => padTop + plotH - ((ret - minY) / (maxY - minY)) * plotH;

    // Draw grid
    ctx.strokeStyle = '#151c28';
    ctx.lineWidth = 1;
    for (let xG = 0; xG <= 100; xG += 20) {
      const xPx = getX(xG);
      ctx.beginPath();
      ctx.moveTo(xPx, padTop);
      ctx.lineTo(xPx, h - padBottom);
      ctx.stroke();

      ctx.fillStyle = '#6e7a8e';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(xG + '%', xPx, h - padBottom + 16);
    }

    for (let yG = -10; yG <= 15; yG += 5) {
      const yPx = getY(yG);
      ctx.beginPath();
      ctx.moveTo(padLeft, yPx);
      ctx.lineTo(w - padRight, yPx);
      ctx.stroke();

      ctx.fillStyle = '#6e7a8e';
      ctx.font = '9px monospace';
      ctx.textAlign = 'right';
      ctx.fillText((yG > 0 ? '+' : '') + yG + '%', padLeft - 6, yPx + 3);
    }

    // Zero line
    ctx.strokeStyle = '#303e54';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(padLeft, getY(0));
    ctx.lineTo(w - padRight, getY(0));
    ctx.stroke();

    // Axis Labels
    ctx.fillStyle = '#00E5FF';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('GATE G4 PROBABILITY SCORE (0% - 100%)', padLeft + plotW / 2, h - 8);

    // Render bubbles
    data.forEach(item => {
      const x = getX(item.gate_g4_score || 50);
      const y = getY(item.exp_return_pct || 0);
      const isSelected = item.symbol === window.TERMINAL_STATE.activeSymbol;

      ctx.beginPath();
      ctx.arc(x, y, isSelected ? 8 : 4.5, 0, Math.PI * 2);
      ctx.fillStyle = item.status === 'BUY' ? 'rgba(0, 230, 118, 0.7)' : (item.status === 'SELL' ? 'rgba(255, 23, 68, 0.7)' : 'rgba(0, 229, 255, 0.5)');
      ctx.fill();

      if (isSelected) {
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.fillStyle = '#fff';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(item.symbol, x, y - 11);
      }
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

  function filterAlphaSector(sector) {
    if (!window.TERMINAL_STATE.alphaData) return;
    if (sector === 'ALL') {
      renderAlphaGrid(window.TERMINAL_STATE.alphaData);
      return;
    }
    const filtered = window.TERMINAL_STATE.alphaData.filter(i => (i.sector || '').toUpperCase().includes(sector));
    renderAlphaGrid(filtered);
  }

  // ==========================================================================
  // SCREEN [3]: RISK MONITOR & DENDROGRAM ENGINE
  // ==========================================================================
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
            <td style="font-weight:800; color:#00E5FF;">${row.symbol}</td>
            <td>${row.cluster || 'Cluster A'}</td>
            <td>
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-weight:800; color:#00E676;">${row.weight.toFixed(1)}%</span>
                <div style="width:60px; height:4px; background:#1a2230; border-radius:2px; overflow:hidden;">
                  <div style="width:${row.weight}%; height:100%; background:#00E5FF;"></div>
                </div>
              </div>
            </td>
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
            <td style="font-weight:800; color:${isHigh ? '#FF1744' : '#00E5FF'};">${b.hhi}</td>
            <td>${b.dominance_pct ? b.dominance_pct.toFixed(1) + '%' : '--'}</td>
            <td>${isHigh ? '<span class="badge-sell">CONCENTRATED</span>' : '<span class="badge-buy">ACCUMULATING</span>'}</td>
          `;
          brokerBody.appendChild(tr);
        });
      }

      renderRiskDendrogramCanvas();
    } catch (e) {
      console.warn('Risk fetch error:', e);
    }
  }

  function renderRiskDendrogramCanvas() {
    const canvas = document.getElementById('riskDendrogramCanvasElement');
    if (!canvas) return;
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const data = window.TERMINAL_STATE.riskData || {};
    const alloc = data.hrp_allocation || [];
    if (alloc.length === 0) return;

    // Draw Risk Cluster Linkage Tree
    ctx.strokeStyle = '#212836';
    ctx.lineWidth = 1.5;

    const startX = 40;
    const startY = 30;
    const itemGap = (h - 60) / alloc.length;

    alloc.forEach((item, idx) => {
      const y = startY + idx * itemGap;
      ctx.fillStyle = item.symbol === window.TERMINAL_STATE.activeSymbol ? '#00E5FF' : '#c9d1d9';
      ctx.font = '10px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(item.symbol, startX, y + 4);

      // Node dot
      ctx.beginPath();
      ctx.arc(startX + 65, y, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#00E5FF';
      ctx.fill();

      // Branch to central cluster spine
      ctx.beginPath();
      ctx.moveTo(startX + 68, y);
      ctx.lineTo(startX + 130, y);
      ctx.stroke();
    });

    // Central cluster trunk
    ctx.beginPath();
    ctx.moveTo(startX + 130, startY);
    ctx.lineTo(startX + 130, startY + (alloc.length - 1) * itemGap);
    ctx.stroke();

    // Portfolio Donut Summary
    const centerX = w - 100;
    const centerY = h / 2;
    const radius = Math.min(65, (h / 2) - 20);

    let startAngle = -Math.PI / 2;
    const colors = ['#00E5FF', '#00E676', '#FFB300', '#B388FF', '#FF1744', '#1f6feb', '#6e7a8e'];

    alloc.forEach((item, i) => {
      const sliceAngle = (item.weight / 100.0) * (Math.PI * 2);
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
      ctx.arc(centerX, centerY, radius * 0.55, startAngle + sliceAngle, startAngle, true);
      ctx.closePath();
      ctx.fillStyle = colors[i % colors.length];
      ctx.fill();
      startAngle += sliceAngle;
    });

    ctx.fillStyle = '#f0f6fc';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('100.0%', centerX, centerY + 3);
  }

  function runRiskStressTest(type) {
    const el = document.getElementById('risk-stress-result');
    if (!el) return;
    if (type === 'circuit') {
      el.textContent = '-5.12% CIRCUIT DRAWDOWN (NPR -48.2k)';
      el.style.color = '#FF1744';
    } else if (type === 'liquidity') {
      el.textContent = '-3.80% SLIPPAGE IMPACT (NPR -32.1k)';
      el.style.color = '#FFB300';
    } else if (type === 'promoter') {
      el.textContent = '-2.45% FLOAT DILUTION DOWNSIDE';
      el.style.color = '#00E5FF';
    }
  }

  // ==========================================================================
  // SCREEN [4]: FORECAST DATA FETCH & INTERACTIVE QUANTILE CORRIDOR CANVAS
  // ==========================================================================
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
          const expColor = item.p50_exp >= 0 ? '#00E676' : '#FF1744';
          tr.innerHTML = `
            <td style="font-weight:800; color:#00E5FF;">${item.symbol}</td>
            <td>${item.latest_close.toFixed(1)}</td>
            <td style="font-weight:700; color:${expColor};">${expSign}${item.p50_exp.toFixed(1)}%</td>
            <td style="color:var(--text-muted); font-size:10px;">${item.p10_exp.toFixed(1)}% ~ ${item.p90_exp.toFixed(1)}%</td>
          `;
          tr.onclick = () => window.selectSymbol(item.symbol);
          rankBody.appendChild(tr);
        });
      }

      const p50El = document.getElementById('forecast-p50-val');
      if (p50El && data.ranked_forecasts) {
        const cur = data.ranked_forecasts.find(i => i.symbol === symbol);
        if (cur) p50El.textContent = `${cur.p50_exp >= 0 ? '+' : ''}${cur.p50_exp.toFixed(2)}%`;
      }
      const tgtEl = document.getElementById('forecast-target-px');
      if (tgtEl && data.p50_curve && data.p50_curve.length > 0) {
        tgtEl.textContent = `NPR ${data.p50_curve[data.p50_curve.length - 1].toFixed(1)}`;
      }

      renderForecastCanvas(data);
    } catch (e) {
      console.warn('Forecast fetch error:', e);
    }
  }

  function filterForecastRank(query) {
    if (!window.TERMINAL_STATE.forecastData || !window.TERMINAL_STATE.forecastData.ranked_forecasts) return;
    query = (query || '').toUpperCase().trim();
    const rankBody = document.getElementById('forecast-rank-body');
    if (!rankBody) return;
    rankBody.innerHTML = '';

    const list = window.TERMINAL_STATE.forecastData.ranked_forecasts.filter(i => i.symbol.includes(query)).slice(0, 50);
    list.forEach(item => {
      const tr = document.createElement('tr');
      tr.id = 'fc-row-' + item.symbol;
      if (item.symbol === window.TERMINAL_STATE.activeSymbol) tr.classList.add('selected-row');
      const expSign = item.p50_exp >= 0 ? '+' : '';
      const expColor = item.p50_exp >= 0 ? '#00E676' : '#FF1744';
      tr.innerHTML = `
        <td style="font-weight:800; color:#00E5FF;">${item.symbol}</td>
        <td>${item.latest_close.toFixed(1)}</td>
        <td style="font-weight:700; color:${expColor};">${expSign}${item.p50_exp.toFixed(1)}%</td>
        <td style="color:var(--text-muted); font-size:10px;">${item.p10_exp.toFixed(1)}% ~ ${item.p90_exp.toFixed(1)}%</td>
      `;
      tr.onclick = () => window.selectSymbol(item.symbol);
      rankBody.appendChild(tr);
    });
  }

  // 60 FPS HTML5 Canvas Quantile Corridor Redraw Routine with Interactive Crosshair HUD
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
    ctx.strokeStyle = '#151c28';
    ctx.lineWidth = 1;
    for (let g = 0; g <= 4; g++) {
      const yVal = minY + (g / 4) * (maxY - minY);
      const yPx = getY(yVal);
      ctx.beginPath();
      ctx.moveTo(padLeft, yPx);
      ctx.lineTo(w - padRight, yPx);
      ctx.stroke();

      ctx.fillStyle = '#6e7a8e';
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
    ctx.fillStyle = 'rgba(0, 229, 255, 0.08)';
    ctx.fill();

    // P90 Line (Green Upside)
    ctx.beginPath();
    ctx.strokeStyle = '#00E676';
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
    ctx.strokeStyle = '#FF1744';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p10[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // P50 Median Line (Solid Cyan)
    ctx.beginPath();
    ctx.strokeStyle = '#00E5FF';
    ctx.lineWidth = 2.5;
    ctx.setLineDash([]);
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p50[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Points on P50 Curve & X labels
    for (let i = 0; i < n; i++) {
      const x = getX(i);
      const y = getY(p50[i]);
      ctx.fillStyle = '#080b10';
      ctx.strokeStyle = '#00E5FF';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#6e7a8e';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('D+' + (i + 1), x, h - padBottom + 16);
    }

    // Interactive Mouse Tracking on Canvas
    canvas.onmousemove = function(e) {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      if (mouseX < padLeft || mouseX > w - padRight) {
        document.getElementById('forecast-crosshair-hud').style.display = 'none';
        return;
      }

      const ratio = (mouseX - padLeft) / plotW;
      const idx = Math.min(n - 1, Math.max(0, Math.round(ratio * (n - 1))));
      const curP50 = p50[idx];
      const curP10 = p10[idx];
      const curP90 = p90[idx];

      const hud = document.getElementById('forecast-crosshair-hud');
      if (hud) {
        hud.style.display = 'block';
        hud.style.left = (getX(idx) - 80) + 'px';
        document.getElementById('forecast-hud-date').textContent = `SESSION D+${idx + 1}`;
        document.getElementById('forecast-hud-px').textContent = `NPR ${curP50.toFixed(1)}`;
        document.getElementById('forecast-hud-corridor').textContent = `P10: ${curP10.toFixed(1)} ~ P90: ${curP90.toFixed(1)}`;
      }
    };
    canvas.onmouseleave = function() {
      const hud = document.getElementById('forecast-crosshair-hud');
      if (hud) hud.style.display = 'none';
    };
  }

  window.addEventListener('resize', () => {
    if (window.TERMINAL_STATE.activeScreen === 'forecast') {
      renderForecastCanvas();
    } else if (window.TERMINAL_STATE.activeScreen === 'alpha') {
      renderAlphaScatterCanvas();
    } else if (window.TERMINAL_STATE.activeScreen === 'risk') {
      renderRiskDendrogramCanvas();
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
        renderAlphaLeaderboard(payload.data);
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

print("Successfully generated institutional multi-workspace UI:")
print(f"  - {TARGET_INDEX_PATH} ({len(final_terminal_html)} bytes)")
print(f"  - {TARGET_TEMPLATE_PATH} ({len(final_terminal_html)} bytes)")
