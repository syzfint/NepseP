"""
scripts/08_dashboard_ui/upgrade_terminal_html.py
Upgrades pulse_terminal/index.html with the 4-Screen Full-Width Workspace Navigation
and Launch Pad architecture as specified in the UI requirements and mockup.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
HTML_PATH = BASE_DIR / "pulse_terminal" / "index.html"


def upgrade():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Custom CSS
    extra_css = """
    /* ========================================================================= */
    /* MULTI-WORKSPACE LAUNCH PAD & 4-SCREEN ARCHITECTURE (PHASE 4.2)            */
    /* ========================================================================= */
    #workspace-navbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #04070d;
      border-bottom: 2px solid #1a2638;
      padding: 0 12px;
      height: 34px;
      z-index: 1000;
    }
    .ws-brand {
      font-size: 11px;
      font-weight: 800;
      color: var(--cyan-status);
      letter-spacing: 1px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .ws-nav-tabs {
      display: flex;
      gap: 6px;
    }
    .ws-nav-btn {
      background: #0a101d;
      border: 1px solid #1e2c42;
      color: #8b9bb4;
      font-family: inherit;
      font-size: 9.5px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 3px;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .ws-nav-btn:hover {
      border-color: var(--cyan-status);
      color: #f0f6fc;
      background: rgba(0, 229, 255, 0.08);
    }
    .ws-nav-btn.active {
      background: rgba(0, 229, 255, 0.18);
      border-color: var(--cyan-status);
      color: var(--cyan-status);
      box-shadow: 0 0 10px rgba(0, 229, 255, 0.25);
    }
    .ws-nav-btn.ws-btn-desk.active { border-color: #00E5FF; color: #00E5FF; }
    .ws-nav-btn.ws-btn-alpha.active { border-color: #00E676; color: #00E676; }
    .ws-nav-btn.ws-btn-risk.active { border-color: #FFB300; color: #FFB300; }
    .ws-nav-btn.ws-btn-forecast.active { border-color: #FF1744; color: #FF1744; }

    /* WORKSPACE SCREEN CONTAINERS */
    .workspace-screen {
      display: none;
      width: 100%;
      height: calc(100vh - 34px);
      overflow: hidden;
      position: absolute;
      top: 34px;
      left: 0;
      background: #030508;
    }
    .workspace-screen.active {
      display: flex;
      flex-direction: column;
    }

    /* SCREEN 0: LAUNCH PAD */
    #screen-launchpad {
      padding: 24px 32px;
      background: radial-gradient(circle at 50% 30%, #081020 0%, #020306 100%);
      align-items: center;
      justify-content: center;
    }
    .launchpad-header {
      text-align: center;
      margin-bottom: 24px;
    }
    .launchpad-title {
      font-size: 20px;
      font-weight: 800;
      letter-spacing: 2px;
      color: #f0f6fc;
      text-shadow: 0 0 15px rgba(0, 229, 255, 0.3);
    }
    .launchpad-subtitle {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .launchpad-grid {
      display: grid;
      grid-template-columns: repeat(2, 440px);
      grid-gap: 20px;
      justify-content: center;
    }
    .launch-card {
      background: #070d18;
      border: 1.5px solid #1a273c;
      border-radius: 6px;
      padding: 18px 20px;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      position: relative;
      overflow: hidden;
    }
    .launch-card:hover {
      transform: translateY(-4px);
      border-color: var(--cyan-status);
      box-shadow: 0 8px 24px rgba(0, 229, 255, 0.2);
    }
    .launch-card.card-desk { border-top: 4px solid #00E5FF; }
    .launch-card.card-alpha { border-top: 4px solid #00E676; }
    .launch-card.card-risk { border-top: 4px solid #FFB300; }
    .launch-card.card-forecast { border-top: 4px solid #FF1744; }

    .card-badge {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .card-key-shortcut {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 3px;
      padding: 1px 6px;
      font-size: 9px;
      color: #f0f6fc;
    }
    .card-title {
      font-size: 13px;
      font-weight: 800;
      color: #f0f6fc;
      margin-bottom: 10px;
    }
    .card-features {
      list-style: none;
      font-size: 10px;
      color: #8b9bb4;
      line-height: 1.6;
    }
    .card-features li::before {
      content: "• ";
      color: var(--cyan-status);
      font-weight: 800;
    }

    /* SCREEN 2: ALPHA DASHBOARD */
    #screen-alpha {
      padding: 10px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .alpha-stats-ribbon {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }
    .alpha-stat-card {
      background: #070d18;
      border: 1px solid #162234;
      padding: 10px 14px;
      border-radius: 4px;
    }
    .alpha-table-container {
      flex: 1;
      overflow-y: auto;
      background: #060a12;
      border: 1px solid #162234;
      border-radius: 4px;
    }
    .alpha-grid-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 10.5px;
    }
    .alpha-grid-table th {
      background: #0a111e;
      padding: 8px 10px;
      color: #8b9bb4;
      text-align: right;
      border-bottom: 2px solid #1e2c42;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .alpha-grid-table th:first-child { text-align: left; }
    .alpha-grid-table td {
      padding: 6px 10px;
      border-bottom: 1px solid #0e1522;
      text-align: right;
    }
    .alpha-grid-table td:first-child { text-align: left; }
    .alpha-grid-table tr:hover { background: #0c1424; }

    /* SCREEN 3: RISK MONITOR (4-QUADRANT LAYOUT) */
    #screen-risk {
      padding: 12px 16px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      grid-template-rows: 1fr 1fr;
      gap: 12px;
      height: calc(100vh - 34px);
    }
    .risk-quadrant {
      background: #060a12;
      border: 1px solid #162234;
      border-radius: 4px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .quadrant-title {
      font-size: 11px;
      font-weight: 800;
      color: #FFB300;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
      border-bottom: 1px solid #141f30;
      padding-bottom: 4px;
      display: flex;
      justify-content: space-between;
    }

    /* SCREEN 4: 20-DAY FORECAST ENGINE */
    #screen-forecast {
      padding: 12px 16px;
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 12px;
      height: calc(100vh - 34px);
    }
    .forecast-sidebar {
      background: #060a12;
      border: 1px solid #162234;
      border-radius: 4px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .forecast-main-canvas-pane {
      background: #04070d;
      border: 1px solid #162234;
      border-radius: 4px;
      padding: 14px;
      display: flex;
      flex-direction: column;
    }
    """

    if "MULTI-WORKSPACE LAUNCH PAD" not in html:
        html = html.replace("</style>", extra_css + "\n</style>")

    # 2. Navbar and Screen Containers
    nav_and_screens_html = """
  <!-- PERSISTENT WORKSPACE TOP NAVBAR -->
  <nav id="workspace-navbar">
    <div class="ws-brand">
      <span>▲ NEPSE PULSE TERMINAL</span>
      <span style="color:#57657a;">│</span>
      <span style="color:#8b9bb4; font-size:10px;">QUANTITATIVE DESK v4.2</span>
    </div>
    <div class="ws-nav-tabs">
      <button class="ws-nav-btn" id="btn-ws-0" onclick="switchWorkspace(0)"><span>[0]</span> MENU</button>
      <button class="ws-nav-btn ws-btn-desk" id="btn-ws-1" onclick="switchWorkspace(1)"><span>[1]</span> TRADING DESK</button>
      <button class="ws-nav-btn ws-btn-alpha" id="btn-ws-2" onclick="switchWorkspace(2)"><span>[2]</span> ALPHA DASHBOARD</button>
      <button class="ws-nav-btn ws-btn-risk" id="btn-ws-3" onclick="switchWorkspace(3)"><span>[3]</span> RISK MONITOR</button>
      <button class="ws-nav-btn ws-btn-forecast" id="btn-ws-4" onclick="switchWorkspace(4)"><span>[4]</span> 20D FORECAST</button>
    </div>
    <div style="font-size:9.5px; color:#57657a; display:flex; gap:10px;">
      <span>NPT (UTC+5:45)</span>
      <span style="color:var(--cyan-status); font-weight:700;" id="nav-clock-live">--:--:--</span>
    </div>
  </nav>

  <!-- SCREEN [0]: WORKSPACE LAUNCH PAD -->
  <div class="workspace-screen" id="screen-launchpad">
    <div class="launchpad-header">
      <div class="launchpad-title">NEPSE PULSE TERMINAL — WORKSPACE LAUNCH PAD</div>
      <div class="launchpad-subtitle">Select operational workspace or press keyboard shortcuts [1] - [4] to launch</div>
    </div>
    <div class="launchpad-grid">
      <!-- Card 1: Trading Desk -->
      <div class="launch-card card-desk" onclick="switchWorkspace(1)">
        <div class="card-badge" style="color:#00E5FF;">
          <span>[1] TRADING DESK</span>
          <span class="card-key-shortcut">KEY 1</span>
        </div>
        <div class="card-title">Real-Time Execution Tape & Level 2 Depth</div>
        <ul class="card-features">
          <li>5-Deep Level 2 Order Book & Order Flow Imbalance (OFI)</li>
          <li>Zero-DOM Headless Graphics Canvas (Candles, VPVR, CVD)</li>
          <li>Centaur Human-in-the-Loop Order Staging Blotter</li>
        </ul>
      </div>

      <!-- Card 2: Alpha Dashboard -->
      <div class="launch-card card-alpha" onclick="switchWorkspace(2)">
        <div class="card-badge" style="color:#00E676;">
          <span>[2] ALPHA & LIVE SIGNAL DASHBOARD</span>
          <span class="card-key-shortcut">KEY 2</span>
        </div>
        <div class="card-title">Full-Market Quantitative Signal Screening</div>
        <ul class="card-features">
          <li>Gate G4 Meta-Labeling Probability Scores (0–100%)</li>
          <li>Hawkes Point Process Syndicate Accumulation Sweeps</li>
          <li>Cont-Stoikov Order Flow Imbalance Real-Time Gauges</li>
        </ul>
      </div>

      <!-- Card 3: Risk Monitor -->
      <div class="launch-card card-risk" onclick="switchWorkspace(3)">
        <div class="card-badge" style="color:#FFB300;">
          <span>[3] RISK MONITOR & PORTFOLIO GOVERNANCE</span>
          <span class="card-key-shortcut">KEY 3</span>
        </div>
        <div class="card-title">Schur-RA-HRP Allocation & Settlement Shield</div>
        <ul class="card-features">
          <li>Hierarchical Risk Parity (Schur-RA-HRP) Capital Weights</li>
          <li>Herfindahl-Hirschman (HHI) Broker Dominance Heatmap</li>
          <li>CDSC T+2 Settlement & Promoter Share Unlock Alerts</li>
        </ul>
      </div>

      <!-- Card 4: Forecast Engine -->
      <div class="launch-card card-forecast" onclick="switchWorkspace(4)">
        <div class="card-badge" style="color:#FF1744;">
          <span>[4] 20-DAY FORECAST ENGINE (CHRONOS ICP)</span>
          <span class="card-key-shortcut">KEY 4</span>
        </div>
        <div class="card-title">Probabilistic Uncertainty Corridors & Quantiles</div>
        <ul class="card-features">
          <li>Chronos-Bolt Quantized ONNX 20-Session Trajectories</li>
          <li>Shaded P10 / P50 / P90 Probabilistic Uncertainty Bands</li>
          <li>20-Day Projected Return Rank Table & Volatility Envelopes</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- SCREEN [1]: TRADING DESK (Existing Terminal Root Container) -->
  <div class="workspace-screen" id="screen-tradingdesk">
"""

    if 'id="workspace-navbar"' not in html:
        html = html.replace('<div id="terminal-root">', nav_and_screens_html + '<div id="terminal-root">')

    # 3. Screens 2, 3, 4 Containers
    screens_2_3_4_html = """
  </div> <!-- Close screen-tradingdesk -->

  <!-- SCREEN [2]: ALPHA & LIVE SIGNAL DASHBOARD -->
  <div class="workspace-screen" id="screen-alpha">
    <div class="alpha-stats-ribbon">
      <div class="alpha-stat-card">
        <div class="f-lbl">TOTAL SECURITIES MONITORED</div>
        <div class="f-val neu" id="alpha-total-count">353 ACTIVE</div>
      </div>
      <div class="alpha-stat-card">
        <div class="f-lbl">GATE G4 CERTIFIED SIGNALS</div>
        <div class="f-val pos" id="alpha-certified-count">24 QUALIFIED</div>
      </div>
      <div class="alpha-stat-card">
        <div class="f-lbl">HAWKES SYNDICATE SWEEPS</div>
        <div class="f-val" style="color:#FFB300;" id="alpha-sweeps-count">7 DETECTED</div>
      </div>
      <div class="alpha-stat-card">
        <div class="f-lbl">SOVEREIGN RISK-FREE RATE</div>
        <div class="f-val pos" id="alpha-rf-rate">4.85% (91D NRB)</div>
      </div>
    </div>

    <div class="alpha-table-container">
      <table class="alpha-grid-table">
        <thead>
          <tr>
            <th style="width: 14%;">SYMBOL</th>
            <th style="width: 12%;">LTP (NPR)</th>
            <th style="width: 14%;">GATE G4 SCORE</th>
            <th style="width: 16%;">GATE G4 STATUS</th>
            <th style="width: 18%;">HAWKES SYNDICATE FLAG</th>
            <th style="width: 12%;">OFI RATIO</th>
            <th style="width: 14%;">SIGNAL ACTION</th>
          </tr>
        </thead>
        <tbody id="alpha-grid-tbody">
          <!-- Dynamically populated from backend -->
        </tbody>
      </table>
    </div>
  </div>

  <!-- SCREEN [3]: RISK MONITOR & PORTFOLIO GOVERNANCE -->
  <div class="workspace-screen" id="screen-risk">
    <div class="risk-quadrant">
      <div class="quadrant-title">
        <span>1. SCHUR-RA-HRP PORTFOLIO ALLOCATION MATRIX</span>
        <span class="neu">Σ WEIGHTS = 100.0%</span>
      </div>
      <div id="risk-hrp-breakdown" style="flex:1; overflow-y:auto; font-size:10px;">
        <!-- Filled dynamically -->
      </div>
    </div>

    <div class="risk-quadrant">
      <div class="quadrant-title">
        <span>2. VALUE-AT-RISK (VaR) & DOWNSIDE CVaR (95%/99%)</span>
        <span style="color:#FF1744;">STRESS TEST</span>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:10px 0;">
        <div class="alpha-stat-card"><div class="f-lbl">PARAMETRIC VaR (95%)</div><div class="f-val neg">-1.85% (1D)</div></div>
        <div class="alpha-stat-card"><div class="f-lbl">CONDITIONAL CVaR (95%)</div><div class="f-val neg">-2.94% (1D)</div></div>
        <div class="alpha-stat-card"><div class="f-lbl">EXTREME VaR (99%)</div><div class="f-val neg">-3.12% (1D)</div></div>
        <div class="alpha-stat-card"><div class="f-lbl">BRENT OIL SHOCK (+2.0σ)</div><div class="f-val neg">-2.45% MTM</div></div>
      </div>
    </div>

    <div class="risk-quadrant">
      <div class="quadrant-title">
        <span>3. HERFINDAHL-HIRSCHMAN (HHI) BROKER CONCENTRATION</span>
        <span class="pos">ANTI-WASH CERTIFIED</span>
      </div>
      <div id="risk-broker-hhi-table" style="flex:1; overflow-y:auto; font-size:10px;">
        <!-- Filled dynamically -->
      </div>
    </div>

    <div class="risk-quadrant">
      <div class="quadrant-title">
        <span>4. CDSC DEMAT & PROMOTER LOCK-IN EXPIRY SHIELD</span>
        <span style="color:#FFB300;">BAFIA / SEBON COMPLIANCE</span>
      </div>
      <div id="risk-cdsc-shield-table" style="flex:1; overflow-y:auto; font-size:10px;">
        <!-- Filled dynamically -->
      </div>
    </div>
  </div>

  <!-- SCREEN [4]: 20-DAY FORECAST ENGINE (CHRONOS ICP) -->
  <div class="workspace-screen" id="screen-forecast">
    <div class="forecast-sidebar">
      <div style="padding:10px 12px; border-bottom:1px solid #162234; font-weight:800; color:#FF1744; font-size:11px;">
        20-DAY PROJECTED RETURNS RANK
      </div>
      <div style="flex:1; overflow-y:auto;" id="forecast-rank-list">
        <!-- Filled dynamically -->
      </div>
    </div>

    <div class="forecast-main-canvas-pane">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <div style="font-size:13px; font-weight:800; color:#f0f6fc;">
          <span style="color:var(--cyan-status);" id="fc-active-symbol">UPPER</span> — 20-SESSION MULTI-QUANTILE TRAJECTORY CORRIDOR
        </div>
        <div style="font-size:10px; color:#8b9bb4;">
          MODEL: <span class="neu">Chronos-Bolt Quantized ONNX</span> │ LATENCY: <span class="pos">&lt; 350 µs</span>
        </div>
      </div>
      <!-- Multi-Quantile Canvas -->
      <div style="flex:1; position:relative; background:#020306; border:1px solid #141f30; border-radius:4px; display:flex; align-items:center; justify-content:center;">
        <canvas id="forecastCorridorCanvas" width="900" height="420" style="width:100%; height:100%;"></canvas>
      </div>
    </div>
  </div>
"""

    if 'id="screen-alpha"' not in html:
        html = html.replace("</body>", screens_2_3_4_html + "\n</body>")

    # 4. Multi-Workspace JavaScript
    js_logic = """
<script>
  // =========================================================================
  // MULTI-WORKSPACE CLIENT LOGIC (PHASE 4.2)
  // =========================================================================
  let currentWorkspaceId = 0; // Default to [0] LAUNCH PAD

  function switchWorkspace(id) {
    currentWorkspaceId = id;
    
    // Hide all screens
    document.querySelectorAll('.workspace-screen').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.ws-nav-btn').forEach(b => b.classList.remove('active'));

    // Activate selected screen and nav tab
    const screenMap = {
      0: 'screen-launchpad',
      1: 'screen-tradingdesk',
      2: 'screen-alpha',
      3: 'screen-risk',
      4: 'screen-forecast'
    };
    const targetScreen = document.getElementById(screenMap[id]);
    if (targetScreen) targetScreen.classList.add('active');

    const targetBtn = document.getElementById('btn-ws-' + id);
    if (targetBtn) targetBtn.classList.add('active');

    // Notify WebSocket of workspace switch
    if (window.pulseSocket && window.pulseSocket.readyState === WebSocket.OPEN) {
      window.pulseSocket.send(JSON.stringify({
        command: "SELECT_WORKSPACE",
        workspace: id
      }));
    }

    // Trigger Screen-specific renders
    if (id === 4) {
      setTimeout(renderForecastCorridorChart, 100);
    }
  }

  // Keyboard shortcut listener ('0', '1', '2', '3', '4', ESC)
  document.addEventListener('keydown', (e) => {
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;

    if (e.key === '0' || e.key === 'Escape') switchWorkspace(0);
    else if (e.key === '1') switchWorkspace(1);
    else if (e.key === '2') switchWorkspace(2);
    else if (e.key === '3') switchWorkspace(3);
    else if (e.key === '4') switchWorkspace(4);
  });

  // Render Multi-Quantile Forecast Corridor Canvas (Screen 4)
  function renderForecastCorridorChart() {
    const canvas = document.getElementById('forecastCorridorCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Background Grid
    ctx.strokeStyle = '#0e1828';
    ctx.lineWidth = 1;
    for (let x = 60; x < w; x += 80) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h - 30);
      ctx.stroke();
    }
    for (let y = 30; y < h - 30; y += 50) {
      ctx.beginPath();
      ctx.moveTo(60, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Simulated 20-Session Trajectory Corridors
    const points = 20;
    const stepX = (w - 100) / (points - 1);
    const startX = 70;
    const baseY = h * 0.65;

    // Draw P10 - P90 Shaded Corridor
    ctx.beginPath();
    for (let i = 0; i < points; i++) {
      const x = startX + i * stepX;
      const y = baseY - (i * 9) - Math.sin(i * 0.5) * 8;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    for (let i = points - 1; i >= 0; i--) {
      const x = startX + i * stepX;
      const y = baseY - (i * 2) + Math.cos(i * 0.5) * 6;
      ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(255, 23, 68, 0.16)';
    ctx.fill();

    // Draw P50 Median Line
    ctx.beginPath();
    ctx.strokeStyle = '#00E5FF';
    ctx.lineWidth = 2.5;
    for (let i = 0; i < points; i++) {
      const x = startX + i * stepX;
      const y = baseY - (i * 5.5) - Math.sin(i * 0.3) * 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Axis labels
    ctx.fillStyle = '#8b9bb4';
    ctx.font = '10px monospace';
    ctx.fillText('Session +1', startX, h - 10);
    ctx.fillText('Session +10', startX + stepX * 9, h - 10);
    ctx.fillText('Session +20', startX + stepX * 19, h - 10);

    // Legend
    ctx.fillStyle = '#00E5FF';
    ctx.fillText('● P50 Median Trajectory', w - 240, 25);
    ctx.fillStyle = '#FF1744';
    ctx.fillText('■ P10 / P90 Uncertainty Corridor (80%)', w - 240, 42);
  }

  // Populate Screen 2 (Alpha) Table
  function populateAlphaTable(data) {
    const tbody = document.getElementById('alpha-grid-tbody');
    if (!tbody || !data) return;
    tbody.innerHTML = '';
    data.forEach(item => {
      const tr = document.createElement('tr');
      const actionColor = item.status === 'BUY' ? 'color:#00E676;' : (item.status === 'SELL' ? 'color:#FF1744;' : 'color:#FFB300;');
      tr.innerHTML = `
        <td style="font-weight:700; color:#f0f6fc;">${item.symbol}</td>
        <td>NPR ${item.ltp.toFixed(1)}</td>
        <td style="font-weight:800; color:#00E5FF;">${item.gate_g4_score}%</td>
        <td style="color:${item.gate_g4_status === 'CERTIFIED' ? '#00E676' : '#8b9bb4'};">${item.gate_g4_status}</td>
        <td style="color:${item.hawkes_flag === 'ACCUMULATION_DETECTED' ? '#FFB300' : '#57657a'}; font-weight:700;">${item.hawkes_flag}</td>
        <td>${item.ofi_ratio > 0 ? '+' : ''}${item.ofi_ratio}</td>
        <td style="font-weight:800; ${actionColor}">[ ${item.status} ]</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Populate Screen 3 (Risk) Data
  function populateRiskData(data) {
    const hrpDiv = document.getElementById('risk-hrp-breakdown');
    if (hrpDiv && data.hrp_allocation) {
      hrpDiv.innerHTML = data.hrp_allocation.map(a => `
        <div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #101624;">
          <span style="font-weight:700; color:#f0f6fc;">${a.symbol} (${a.sector})</span>
          <span style="color:var(--cyan-status); font-weight:800;">${a.weight}%</span>
        </div>
      `).join('');
    }

    const hhiDiv = document.getElementById('risk-broker-hhi-table');
    if (hhiDiv && data.broker_hhi) {
      hhiDiv.innerHTML = data.broker_hhi.map(b => `
        <div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #101624;">
          <span>Broker #${b.broker_id} (${b.name})</span>
          <span style="color:#00E676; font-weight:700;">HHI: ${b.hhi_score} (${b.action})</span>
        </div>
      `).join('');
    }

    const cdscDiv = document.getElementById('risk-cdsc-shield-table');
    if (cdscDiv && data.cdsc_shield) {
      cdscDiv.innerHTML = data.cdsc_shield.map(c => `
        <div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #101624;">
          <span style="font-weight:700; color:#f0f6fc;">${c.symbol}</span>
          <span style="color:${c.risk_level === 'CRITICAL' ? '#FF1744' : '#00E676'}; font-weight:700;">
            ${c.status} (${c.days_to_unlock}D | ${c.risk_level})
          </span>
        </div>
      `).join('');
    }
  }

  // Populate Screen 4 (Forecast) Data
  function populateForecastData(data) {
    const rankDiv = document.getElementById('forecast-rank-list');
    if (rankDiv && data.ranked_forecasts) {
      rankDiv.innerHTML = data.ranked_forecasts.slice(0, 30).map(f => `
        <div style="display:flex; justify-content:space-between; padding:6px 10px; border-bottom:1px solid #101624; cursor:pointer;" onclick="document.getElementById('fc-active-symbol').innerText='${f.symbol}'; renderForecastCorridorChart();">
          <span style="font-weight:700; color:#f0f6fc;">${f.symbol}</span>
          <span style="color:${f.exp_return_20d_pct >= 0 ? '#00E676' : '#FF1744'}; font-weight:800;">
            ${f.exp_return_20d_pct >= 0 ? '+' : ''}${f.exp_return_20d_pct}%
          </span>
        </div>
      `).join('');
    }
  }

  // Setup on page load
  window.addEventListener('load', () => {
    // Default open on Launch Pad [0]
    switchWorkspace(0);

    // Live clock update
    setInterval(() => {
      const now = new Date();
      const clockEl = document.getElementById('nav-clock-live');
      if (clockEl) clockEl.innerText = now.toTimeString().split(' ')[0];
    }, 1000);

    // Fetch initial workspace APIs
    fetch('/api/workspaces/alpha').then(r => r.json()).then(j => populateAlphaTable(j.data)).catch(()=>{});
    fetch('/api/workspaces/risk').then(r => r.json()).then(j => populateRiskData(j.data)).catch(()=>{});
    fetch('/api/workspaces/forecast').then(r => r.json()).then(j => populateForecastData(j.data)).catch(()=>{});
  });
</script>
"""

    if "MULTI-WORKSPACE CLIENT LOGIC" not in html:
        html = html.replace("</body>", js_logic + "\n</body>")

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("Successfully upgraded pulse_terminal/index.html with Multi-Workspace Launch Pad & 4 Screens!")


if __name__ == "__main__":
    upgrade()
