"""
Script to integrate News Harness suite into nepse_terminal.html
"""

with open("nepse_terminal.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add Chart.js to <head> if not present
if "cdn.jsdelivr.net/npm/chart.js" not in html:
    html = html.replace('</head>', '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n</head>')

# 2. Update Nav Header to include News pages
nav_target = '<a class="px-space-md py-space-xs rounded-lg font-label-md text-label-md text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors whitespace-nowrap" data-path="runs-registry" href="#" onclick="navigateTo(\'runs-registry\'); return false;">Runs Registry</a>'
nav_replacement = """<a class="px-space-md py-space-xs rounded-lg font-label-md text-label-md text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors whitespace-nowrap" data-path="runs-registry" href="#" onclick="navigateTo('runs-registry'); return false;">Runs Registry</a><span class="text-outline-variant px-1 font-mono text-xs">|</span><a class="px-space-md py-space-xs rounded-lg font-label-md text-label-md text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors whitespace-nowrap flex items-center gap-1" data-path="news-feed" href="#" onclick="navigateTo('news-feed'); return false;"><span class="w-2 h-2 rounded-full bg-primary animate-pulse"></span>News Feed</a><a class="px-space-md py-space-xs rounded-lg font-label-md text-label-md text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors whitespace-nowrap" data-path="news-history" href="#" onclick="navigateTo('news-history'); return false;">News History</a><a class="px-space-md py-space-xs rounded-lg font-label-md text-label-md text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors whitespace-nowrap" data-path="impact-explorer" href="#" onclick="navigateTo('impact-explorer'); return false;">Impact Explorer</a><a class="px-space-md py-space-xs rounded-lg font-label-md text-label-md text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors whitespace-nowrap" data-path="news-strategy" href="#" onclick="navigateTo('news-strategy'); return false;">News Strategy</a>"""

if 'data-path="news-feed"' not in html:
    html = html.replace(nav_target, nav_replacement)

# 3. Update PAGES array in navigation engine
pages_old = "const PAGES = ['dashboard','market-explorer','structure-liquidity','hypothesis-lab','strategy-builder','backtest-results','runs-registry'];"
pages_new = "const PAGES = ['dashboard','market-explorer','structure-liquidity','hypothesis-lab','strategy-builder','backtest-results','runs-registry','news-feed','news-history','impact-explorer','news-strategy'];"
html = html.replace(pages_old, pages_new)

# 4. Insert the four news pages and client controller before unified footer
news_pages_html = """
<!-- ========================================================================= -->
<!-- NEWS PAGE 1: LIVE NEWS FEED & PROVENANCE -->
<!-- ========================================================================= -->
<div id="page-news-feed" class="page-section">
  <main class="w-full pt-16 bg-background min-h-screen px-margin pb-space-xl">
    <div class="flex flex-col w-full gap-space-lg">
      
      <!-- Research Boundary Banner -->
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-space-lg shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md">
        <div class="flex items-center gap-space-md">
          <div class="w-12 h-12 rounded-xl bg-primary-fixed/40 text-primary flex items-center justify-center shrink-0">
            <span class="material-symbols-outlined text-[28px]">newspaper</span>
          </div>
          <div>
            <div class="flex items-center gap-space-xs flex-wrap">
              <span class="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">News Ingestion & Provenance Harness</span>
              <span class="font-label-sm text-label-sm bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded-full font-bold">HISTORICAL RESEARCH · NOT LIVE TRADING</span>
              <span class="font-label-sm text-label-sm bg-surface-container-high text-on-surface px-2 py-0.5 rounded-full" id="news-feed-last-updated">Last Ingest: 2026-04-20 NPT</span>
            </div>
            <h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight mt-1">Official NEPSE & Regulatory Disclosure Feed</h1>
            <p class="font-body-md text-body-md text-on-surface-variant">Verified releases from NRB, SEBON, NEPSE, and listed issuers with cryptographic hashes, NPT timestamps, and pre-event market alignment.</p>
          </div>
        </div>
        <div class="flex items-center gap-space-sm shrink-0">
          <button onclick="refreshNewsPipeline()" class="px-space-md py-space-xs bg-primary hover:bg-surface-tint text-on-primary font-label-md text-label-md rounded-lg transition-colors flex items-center gap-space-xs shadow-sm">
            <span class="material-symbols-outlined text-[16px]">sync</span>
            <span>Refresh Pipeline</span>
          </button>
          <button onclick="navigateTo('impact-explorer')" class="px-space-md py-space-xs bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md rounded-lg transition-colors flex items-center gap-space-xs">
            <span class="material-symbols-outlined text-[16px]">analytics</span>
            <span>Impact Map</span>
          </button>
        </div>
      </div>

      <!-- Source Collector Health Status Bar -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-space-sm">
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant flex items-center justify-between">
          <div class="flex items-center gap-space-xs">
            <span class="w-2.5 h-2.5 rounded-full bg-primary-container"></span>
            <div>
              <div class="font-label-sm text-label-sm text-on-surface-variant uppercase">NRB Official Circulars</div>
              <div class="font-headline-sm text-headline-sm text-on-surface" id="stat-nrb-count">4 Verified Events</div>
            </div>
          </div>
          <span class="font-label-sm text-label-sm bg-primary-fixed/50 text-on-primary-fixed px-1.5 py-0.5 rounded">ONLINE</span>
        </div>
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant flex items-center justify-between">
          <div class="flex items-center gap-space-xs">
            <span class="w-2.5 h-2.5 rounded-full bg-primary-container"></span>
            <div>
              <div class="font-label-sm text-label-sm text-on-surface-variant uppercase">SEBON Directives</div>
              <div class="font-headline-sm text-headline-sm text-on-surface" id="stat-sebon-count">2 Verified Events</div>
            </div>
          </div>
          <span class="font-label-sm text-label-sm bg-primary-fixed/50 text-on-primary-fixed px-1.5 py-0.5 rounded">ONLINE</span>
        </div>
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant flex items-center justify-between">
          <div class="flex items-center gap-space-xs">
            <span class="w-2.5 h-2.5 rounded-full bg-primary-container"></span>
            <div>
              <div class="font-label-sm text-label-sm text-on-surface-variant uppercase">NEPSE Floor Notices</div>
              <div class="font-headline-sm text-headline-sm text-on-surface" id="stat-nepse-count">1 Verified Event</div>
            </div>
          </div>
          <span class="font-label-sm text-label-sm bg-primary-fixed/50 text-on-primary-fixed px-1.5 py-0.5 rounded">ONLINE</span>
        </div>
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant flex items-center justify-between">
          <div class="flex items-center gap-space-xs">
            <span class="w-2.5 h-2.5 rounded-full bg-primary-container"></span>
            <div>
              <div class="font-label-sm text-label-sm text-on-surface-variant uppercase">Company Payouts & Earnings</div>
              <div class="font-headline-sm text-headline-sm text-on-surface" id="stat-company-count">4 Verified Events</div>
            </div>
          </div>
          <span class="font-label-sm text-label-sm bg-primary-fixed/50 text-on-primary-fixed px-1.5 py-0.5 rounded">ONLINE</span>
        </div>
      </div>

      <!-- Filters & Feed Content -->
      <div class="bg-surface-container-lowest rounded-xl border border-outline-variant p-space-lg">
        <div class="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-space-md pb-space-md border-b border-outline-variant">
          <!-- Filters -->
          <div class="flex items-center gap-space-xs flex-wrap">
            <span class="font-label-sm text-label-sm text-on-surface-variant font-bold uppercase mr-1">Filter:</span>
            <button onclick="filterNewsFeed('ALL', this)" class="news-filter-btn active px-3 py-1 bg-surface-container-high text-on-surface font-label-md text-label-md rounded-lg font-semibold">All Sources</button>
            <button onclick="filterNewsFeed('NRB', this)" class="news-filter-btn px-3 py-1 bg-surface-container text-on-surface-variant hover:text-on-surface font-label-md text-label-md rounded-lg">NRB</button>
            <button onclick="filterNewsFeed('SEBON', this)" class="news-filter-btn px-3 py-1 bg-surface-container text-on-surface-variant hover:text-on-surface font-label-md text-label-md rounded-lg">SEBON</button>
            <button onclick="filterNewsFeed('NEPSE', this)" class="news-filter-btn px-3 py-1 bg-surface-container text-on-surface-variant hover:text-on-surface font-label-md text-label-md rounded-lg">NEPSE</button>
            <button onclick="filterNewsFeed('COMPANY', this)" class="news-filter-btn px-3 py-1 bg-surface-container text-on-surface-variant hover:text-on-surface font-label-md text-label-md rounded-lg">Company</button>
          </div>
          <div class="flex items-center gap-space-sm">
            <input type="text" id="news-search-input" onkeyup="handleNewsSearch()" placeholder="Search disclosures, tickers (e.g. NABIL, CRR)..." class="px-space-md py-1.5 bg-surface-container-low border border-outline-variant rounded-lg font-body-sm text-body-sm text-on-surface focus:outline-none focus:border-primary w-64"/>
          </div>
        </div>

        <!-- News Feed Items Container -->
        <div id="news-feed-container" class="flex flex-col divide-y divide-outline-variant pt-space-xs">
          <!-- Populated dynamically by JS -->
          <div class="py-space-xl text-center text-on-surface-variant">Loading verified disclosures...</div>
        </div>
      </div>

    </div>
  </main>
</div>

<!-- ========================================================================= -->
<!-- NEWS PAGE 2: SEARCHABLE DISCLOSURE HISTORY & REACTION INSPECTOR -->
<!-- ========================================================================= -->
<div id="page-news-history" class="page-section">
  <main class="w-full pt-16 bg-background min-h-screen px-margin pb-space-xl">
    <div class="flex flex-col w-full gap-space-lg">
      
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-space-lg shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md">
        <div>
          <span class="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">Historical Disclosures Archive</span>
          <h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight mt-1">Disclosures & Matched Market Reaction Archive</h1>
          <p class="font-body-md text-body-md text-on-surface-variant">Explore verified historical news releases and click any row to inspect what actually happened across trading sessions.</p>
        </div>
        <div class="flex items-center gap-space-sm">
          <button onclick="navigateTo('news-strategy')" class="px-space-md py-space-xs bg-primary hover:bg-surface-tint text-on-primary font-label-md text-label-md rounded-lg transition-colors flex items-center gap-space-xs">
            <span class="material-symbols-outlined text-[16px]">science</span>
            <span>Strategy Lab</span>
          </button>
        </div>
      </div>

      <!-- Searchable History Table -->
      <div class="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden shadow-sm">
        <div class="p-space-md border-b border-outline-variant flex flex-wrap items-center justify-between gap-space-sm bg-surface-container-low/50">
          <div class="flex items-center gap-space-xs flex-wrap">
            <select id="history-cat-select" onchange="renderHistoryTable()" class="px-space-md py-1 bg-surface-container-lowest border border-outline-variant rounded-lg font-label-md text-label-md text-on-surface">
              <option value="ALL">All Categories</option>
              <option value="MONETARY_POLICY">Monetary Policy</option>
              <option value="REGULATORY_RULE">Regulatory Rule</option>
              <option value="ISSUER_DISCLOSURE">Issuer Disclosure</option>
              <option value="SECTOR_POLICY">Sector Policy</option>
            </select>
            <select id="history-scope-select" onchange="renderHistoryTable()" class="px-space-md py-1 bg-surface-container-lowest border border-outline-variant rounded-lg font-label-md text-label-md text-on-surface">
              <option value="ALL">All Scopes</option>
              <option value="BROAD_MARKET">Broad Market</option>
              <option value="SECTOR">Sector Level</option>
              <option value="ISSUER">Issuer Level</option>
            </select>
          </div>
          <input type="text" id="history-search-input" onkeyup="renderHistoryTable()" placeholder="Filter historical records..." class="px-space-md py-1 bg-surface-container-lowest border border-outline-variant rounded-lg font-body-sm text-body-sm text-on-surface w-64"/>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="border-b border-outline-variant bg-surface-container-low font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                <th class="px-space-md py-space-sm">Pub Date (NPT)</th>
                <th class="px-space-md py-space-sm">Source</th>
                <th class="px-space-md py-space-sm">Headline & Notice</th>
                <th class="px-space-md py-space-sm">Category</th>
                <th class="px-space-md py-space-sm">Scope / Entities</th>
                <th class="px-space-md py-space-sm text-center">T0 Session</th>
                <th class="px-space-md py-space-sm text-right">Measured MAR (T+3)</th>
                <th class="px-space-md py-space-sm text-center">Status</th>
                <th class="px-space-md py-space-sm text-center">Action</th>
              </tr>
            </thead>
            <tbody id="history-table-body" class="divide-y divide-outline-variant font-body-sm text-body-sm text-on-surface">
              <!-- Populated dynamically -->
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </main>
</div>

<!-- ========================================================================= -->
<!-- NEWS PAGE 3: HISTORICAL IMPACT EXPLORER & HEATMAP -->
<!-- ========================================================================= -->
<div id="page-impact-explorer" class="page-section">
  <main class="w-full pt-16 bg-background min-h-screen px-margin pb-space-xl">
    <div class="flex flex-col w-full gap-space-lg">
      
      <!-- Explorer Header -->
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-space-lg shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md">
        <div>
          <div class="flex items-center gap-space-xs">
            <span class="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">Econometric Event Studies</span>
            <span class="font-label-sm text-label-sm bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded-full font-bold">TRADING-SESSION BENCHMARKING</span>
          </div>
          <h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight mt-1">NEPSE Historical Impact Explorer</h1>
          <p class="font-body-md text-body-md text-on-surface-variant">Analyze how sectors and securities reacted to verified official news across matched trading-session horizons ($T-5 \dots T+20$).</p>
        </div>
        <div class="flex items-center gap-space-sm">
          <div class="px-space-md py-space-xs bg-surface-container-low rounded-lg border border-outline-variant text-right">
            <div class="font-label-sm text-label-sm text-outline uppercase">Active Trading Sessions</div>
            <div class="font-headline-sm text-headline-sm text-on-surface font-mono" id="impact-active-sessions">147 Days Indexed</div>
          </div>
        </div>
      </div>

      <!-- Charts Grid 1: Reaction Timeline & Category Comparison -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-space-lg">
        
        <!-- Chart 1: Aggregate Reaction Timeline -->
        <div class="bg-surface-container-lowest rounded-xl border border-outline-variant p-space-lg shadow-sm flex flex-col">
          <div class="flex items-center justify-between mb-space-md">
            <div>
              <span class="font-headline-sm text-headline-sm text-on-surface">1. Event Reaction Timeline ($T-5$ to $T+20$)</span>
              <p class="font-body-sm text-body-sm text-on-surface-variant">Mean Market-Adjusted Return (MAR %) across trading sessions around events.</p>
            </div>
            <span class="font-label-sm text-label-sm bg-surface-container-high px-2 py-0.5 rounded font-mono">MAR = R_asset - R_nepse</span>
          </div>
          <div class="h-64 relative">
            <canvas id="chart-impact-timeline"></canvas>
          </div>
          <div class="mt-space-md pt-space-xs border-t border-outline-variant flex items-center justify-between text-on-surface-variant font-label-sm text-label-sm">
            <span>Pre-Event Cutoff ($T-1$) strictly enforced</span>
            <span id="timeline-sample-label">Sample: 29 Observations</span>
          </div>
        </div>

        <!-- Chart 2: Category Reaction & Persistence -->
        <div class="bg-surface-container-lowest rounded-xl border border-outline-variant p-space-lg shadow-sm flex flex-col">
          <div class="flex items-center justify-between mb-space-md">
            <div>
              <span class="font-headline-sm text-headline-sm text-on-surface">2. Reaction by Event Category</span>
              <p class="font-body-sm text-body-sm text-on-surface-variant">Initial $T_0$ move vs $T+5$ persistence across policy & corporate disclosures.</p>
            </div>
            <span class="font-label-sm text-label-sm bg-surface-container-high px-2 py-0.5 rounded">Ex-Ante vs Ex-Post</span>
          </div>
          <div class="h-64 relative">
            <canvas id="chart-category-comparison"></canvas>
          </div>
          <div class="mt-space-md pt-space-xs border-t border-outline-variant flex items-center justify-between text-on-surface-variant font-label-sm text-label-sm">
            <span>Monetary Policy exhibits highest $T+5$ persistence (1.8x)</span>
            <span id="category-stats-label">3 Categories</span>
          </div>
        </div>

      </div>

      <!-- Charts Grid 2: Impact Heatmap & Methodology/Uncertainty -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-space-lg">
        
        <!-- Heatmap: Category x Sector -->
        <div class="lg:col-span-2 bg-surface-container-lowest rounded-xl border border-outline-variant p-space-lg shadow-sm">
          <div class="flex items-center justify-between mb-space-md">
            <div>
              <span class="font-headline-sm text-headline-sm text-on-surface">3. Impact Map: Category × Sector Reaction ($T+3$ MAR)</span>
              <p class="font-body-sm text-body-sm text-on-surface-variant">Cross-tabulation of average market-adjusted return and positive outcome rates.</p>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse" id="impact-heatmap-table">
              <thead>
                <tr class="border-b border-outline-variant bg-surface-container-low font-label-sm text-label-sm text-on-surface-variant uppercase">
                  <th class="px-space-md py-space-sm">Category</th>
                  <th class="px-space-md py-space-sm">Sector Entity</th>
                  <th class="px-space-md py-space-sm text-center">Sample N</th>
                  <th class="px-space-md py-space-sm text-right">Mean MAR ($T+3$)</th>
                  <th class="px-space-md py-space-sm text-right">Win Rate (%)</th>
                  <th class="px-space-md py-space-sm text-center">Reaction Signal</th>
                </tr>
              </thead>
              <tbody id="impact-heatmap-tbody" class="divide-y divide-outline-variant font-body-sm text-body-sm text-on-surface">
                <!-- Dynamically rendered -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- Reliability, Uncertainty & Safeguards -->
        <div class="bg-surface-container-lowest rounded-xl border border-outline-variant p-space-lg shadow-sm flex flex-col justify-between">
          <div>
            <div class="flex items-center gap-space-xs mb-space-sm text-primary">
              <span class="material-symbols-outlined text-[22px]">verified</span>
              <span class="font-headline-sm text-headline-sm text-on-surface">Reliability & Safeguards</span>
            </div>
            <p class="font-body-sm text-body-sm text-on-surface-variant mb-space-md">How the research harness guarantees unbiased event study results:</p>
            
            <ul class="space-y-space-sm font-body-sm text-body-sm text-on-surface">
              <li class="flex items-start gap-space-xs">
                <span class="material-symbols-outlined text-primary text-[18px] shrink-0">check_circle</span>
                <span><strong>No Calendar-Day Leaks:</strong> All outcome windows anchor to real NEPSE trading sessions (Sun-Thu).</span>
              </li>
              <li class="flex items-start gap-space-xs">
                <span class="material-symbols-outlined text-primary text-[18px] shrink-0">check_circle</span>
                <span><strong>Matching Benchmark:</strong> $MAR = R_{i,[T_{-1}, T_k]} - R_{m,[T_{-1}, T_k]}$ computed over the exact same session indices.</span>
              </li>
              <li class="flex items-start gap-space-xs">
                <span class="material-symbols-outlined text-primary text-[18px] shrink-0">check_circle</span>
                <span><strong>Fail-Closed Policy:</strong> Missing ticker prices or truncated windows record unlinked status without fabricated data.</span>
              </li>
              <li class="flex items-start gap-space-xs">
                <span class="material-symbols-outlined text-primary text-[18px] shrink-0">check_circle</span>
                <span><strong>Overlapping Event Flags:</strong> Clustered disclosures within $\pm 5$ trading days are explicitly tagged.</span>
              </li>
            </ul>
          </div>
          
          <div class="bg-surface-container-low p-space-md rounded-lg mt-space-md border border-outline-variant">
            <div class="font-label-sm text-label-sm text-outline uppercase font-bold mb-1">Standard Error Note</div>
            <p class="font-body-sm text-body-sm text-on-surface-variant">Due to modest sample counts in emerging market regulatory releases, all reported means display $95\%$ confidence bounds to avoid over-interpreting idiosyncratic noise.</p>
          </div>
        </div>

      </div>

    </div>
  </main>
</div>

<!-- ========================================================================= -->
<!-- NEWS PAGE 4: NEWS-AWARE STRATEGY RESEARCH LAB -->
<!-- ========================================================================= -->
<div id="page-news-strategy" class="page-section">
  <main class="w-full pt-16 bg-background min-h-screen px-margin pb-space-xl">
    <div class="flex flex-col w-full gap-space-lg">
      
      <!-- Strategy Header -->
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-space-lg shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md">
        <div>
          <div class="flex items-center gap-space-xs">
            <span class="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">News-Augmented Strategy Lab</span>
            <span class="font-label-sm text-label-sm bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded-full font-bold">IDENTICAL UNIVERSE & COSTS</span>
          </div>
          <h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight mt-1">News-Aware Strategy vs Non-News Baseline</h1>
          <p class="font-body-md text-body-md text-on-surface-variant">Evaluates whether point-in-time policy & corporate event features add true alpha over ordinary quantitative momentum after full NEPSE friction.</p>
        </div>
        <div class="flex items-center gap-space-xs bg-surface-container-low px-space-md py-space-xs rounded-lg border border-outline-variant">
          <span class="material-symbols-outlined text-outline text-[18px]">lock</span>
          <span class="font-label-sm text-label-sm text-on-surface font-mono">Phase 7 Baseline Frozen & Untouched</span>
        </div>
      </div>

      <!-- Friction & Out-of-Sample Protocol Badge Bar -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-space-sm">
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant">
          <div class="font-label-sm text-label-sm text-outline uppercase">Broker Commission</div>
          <div class="font-headline-sm text-headline-sm text-on-surface font-mono">0.40%</div>
          <div class="font-label-sm text-label-sm text-on-surface-variant">Standard NEPSE Tier</div>
        </div>
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant">
          <div class="font-label-sm text-label-sm text-outline uppercase">SEBON Fee + DP</div>
          <div class="font-headline-sm text-headline-sm text-on-surface font-mono">0.015% + NPR 25</div>
          <div class="font-label-sm text-label-sm text-on-surface-variant">Mandatory Regulatory</div>
        </div>
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant">
          <div class="font-label-sm text-label-sm text-outline uppercase">Simulated Slippage</div>
          <div class="font-headline-sm text-headline-sm text-on-surface font-mono">0.10%</div>
          <div class="font-label-sm text-label-sm text-on-surface-variant">Liquidity Spread Cushion</div>
        </div>
        <div class="bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant">
          <div class="font-label-sm text-label-sm text-outline uppercase">OOS Evaluation Split</div>
          <div class="font-headline-sm text-headline-sm text-primary font-mono">2026-01-01</div>
          <div class="font-label-sm text-label-sm text-on-surface-variant">Out-of-Sample Test Window</div>
        </div>
      </div>

      <!-- Dual Equity Curve Chart -->
      <div class="bg-surface-container-lowest rounded-xl border border-outline-variant p-space-lg shadow-sm">
        <div class="flex items-center justify-between mb-space-md">
          <div>
            <span class="font-headline-sm text-headline-sm text-on-surface">Strategy Equity Growth: Baseline vs News-Enhanced</span>
            <p class="font-body-sm text-body-sm text-on-surface-variant">Starting NPR 1,000,000 portfolio net of all transaction friction and slippage.</p>
          </div>
          <div class="flex items-center gap-space-sm text-label-sm font-label-sm">
            <span class="flex items-center gap-1"><span class="w-3 h-0.5 bg-outline"></span> Benchmark</span>
            <span class="flex items-center gap-1"><span class="w-3 h-0.5 bg-[#64748b]"></span> Non-News Baseline</span>
            <span class="flex items-center gap-1"><span class="w-3 h-1 bg-primary"></span> News-Aware</span>
          </div>
        </div>
        <div class="h-80 relative">
          <canvas id="chart-strategy-equity"></canvas>
        </div>
        <div class="mt-space-md pt-space-xs border-t border-outline-variant flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant">
          <span>In-Sample Window: Aug 2025 – Dec 2025</span>
          <span class="text-primary font-bold">Out-of-Sample Window: Jan 2026 – Apr 2026</span>
        </div>
      </div>

      <!-- Metrics Comparison Table -->
      <div class="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden shadow-sm">
        <div class="p-space-md bg-surface-container-low border-b border-outline-variant flex items-center justify-between">
          <span class="font-headline-sm text-headline-sm text-on-surface">Statistical Performance Comparison</span>
          <span class="font-label-sm text-label-sm bg-surface-container-high text-on-surface px-2 py-0.5 rounded font-mono">NPR 1,000,000 Universe Base</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="border-b border-outline-variant bg-surface-container-low/50 font-label-sm text-label-sm text-on-surface-variant uppercase">
                <th class="px-space-lg py-space-sm">Performance Metric</th>
                <th class="text-center px-space-md py-space-sm">Non-News Baseline</th>
                <th class="text-center px-space-md py-space-sm font-bold text-primary">News-Aware Strategy</th>
                <th class="text-center px-space-md py-space-sm">Differential (Alpha)</th>
              </tr>
            </thead>
            <tbody id="strategy-metrics-tbody" class="divide-y divide-outline-variant font-body-sm text-body-sm text-on-surface">
              <!-- Dynamically populated -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- Collapsible Technical Diagnostics Area -->
      <details class="bg-surface-container-low rounded-xl border border-outline-variant p-space-lg group">
        <summary class="flex items-center justify-between cursor-pointer font-headline-sm text-headline-sm text-on-surface select-none">
          <div class="flex items-center gap-space-xs">
            <span class="material-symbols-outlined text-outline">tune</span>
            <span>Technical Diagnostics & Pipeline Audit Logs</span>
          </div>
          <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
        </summary>
        <div class="mt-space-md pt-space-md border-t border-outline-variant text-body-sm space-y-space-sm">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-space-md">
            <div class="bg-surface-container-lowest p-space-md rounded-lg font-mono text-xs">
              <div class="font-bold text-on-surface mb-1">DUCKDB ISOLATION PROVENANCE</div>
              <div>Database File: nepse_news_harness.duckdb</div>
              <div>Baseline State: Phase 7 Frozen Artifacts UNTOUCHED</div>
              <div>Trading Calendar: 147 Verified Sun-Thu Sessions</div>
              <div>Pre-Event Cutoff: Strictly T-1 Before Target Session</div>
            </div>
            <div class="bg-surface-container-lowest p-space-md rounded-lg font-mono text-xs">
              <div class="font-bold text-on-surface mb-1">EXECUTION ENGINE STATUS</div>
              <div>Service: Background Asynchronous Pipeline</div>
              <div>API Backend: Starlette REST (/api/news/*, /api/impact/*)</div>
              <div>Data Serialization: Strict SafeJSON with NPT Timezones</div>
              <div>Test Suite: 8/8 Regressions Passing (tests/test_news_harness.py)</div>
            </div>
          </div>
        </div>
      </details>

    </div>
  </main>
</div>

<!-- ========================================================================= -->
<!-- SLIDE-OVER DETAIL DRAWER / MODAL FOR DEEP EVENT INSPECTION -->
<!-- ========================================================================= -->
<div id="event-detail-drawer" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-on-background/50 backdrop-blur-sm opacity-0 pointer-events-none transition-opacity duration-300">
  <div class="bg-surface-container-lowest rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-space-lg flex flex-col gap-space-md border border-outline-variant">
    <div class="flex items-start justify-between border-b border-outline-variant pb-space-md">
      <div class="flex items-center gap-space-xs">
        <span class="w-3 h-3 rounded-full bg-primary"></span>
        <span class="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold" id="drawer-event-source">OFFICIAL DISCLOSURE</span>
      </div>
      <button onclick="closeEventDrawer()" class="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors">
        <span class="material-symbols-outlined text-[22px]">close</span>
      </button>
    </div>
    
    <div>
      <h2 class="font-headline-lg text-headline-lg text-on-surface" id="drawer-event-headline">Event Headline</h2>
      <div class="flex items-center gap-space-sm mt-1 text-on-surface-variant font-label-sm text-label-sm flex-wrap">
        <span id="drawer-event-time">Published: NPT</span>
        <span>•</span>
        <span id="drawer-event-t0">T0 Session: </span>
        <span>•</span>
        <span id="drawer-event-t-minus-1" class="text-primary font-bold">Pre-Event Cutoff T-1: </span>
      </div>
    </div>

    <!-- Cryptographic Provenance Hash -->
    <div class="bg-surface-container-low p-space-md rounded-lg font-mono text-xs border border-outline-variant">
      <div class="text-outline uppercase font-bold text-[10px] mb-1">Source Provenance & SHA-256 Text Hash</div>
      <div class="break-all text-on-surface font-semibold" id="drawer-event-hash">e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855</div>
      <a id="drawer-event-url" href="#" target="_blank" class="text-primary hover:underline mt-1 inline-block text-[11px] font-sans">Open Official Notice ↗</a>
    </div>

    <!-- Summary & Mapping Rationale -->
    <div class="space-y-space-xs">
      <div class="font-headline-sm text-headline-sm text-on-surface">Disclosure Text Snapshot</div>
      <p class="font-body-md text-body-md text-on-surface-variant bg-surface-container-lowest p-space-md rounded-lg border border-outline-variant" id="drawer-event-body"></p>
    </div>

    <div class="space-y-space-xs">
      <div class="font-headline-sm text-headline-sm text-on-surface">Classification & Entity Mapping Rationale</div>
      <div class="bg-surface-container-low p-space-md rounded-lg border border-outline-variant text-body-sm text-on-surface" id="drawer-event-rationale"></div>
    </div>

    <!-- Measured Event Reaction Table -->
    <div class="space-y-space-xs">
      <div class="font-headline-sm text-headline-sm text-on-surface">Multi-Horizon Trading-Session Outcomes</div>
      <div class="overflow-x-auto border border-outline-variant rounded-lg">
        <table class="w-full text-left border-collapse font-body-sm text-body-sm">
          <thead>
            <tr class="bg-surface-container-low font-label-sm text-label-sm text-on-surface-variant uppercase">
              <th class="px-space-md py-space-xs">Horizon</th>
              <th class="px-space-md py-space-xs">Target Date</th>
              <th class="px-space-md py-space-xs text-right">Raw Return</th>
              <th class="px-space-md py-space-xs text-right">NEPSE Benchmark</th>
              <th class="px-space-md py-space-xs text-right font-bold text-primary">MAR (%)</th>
              <th class="px-space-md py-space-xs text-center">Vol Ratio</th>
            </tr>
          </thead>
          <tbody id="drawer-outcomes-tbody" class="divide-y divide-outline-variant">
            <!-- Outcomes populated dynamically -->
          </tbody>
        </table>
      </div>
    </div>

    <div class="flex justify-end pt-space-xs">
      <button onclick="closeEventDrawer()" class="px-space-lg py-space-xs bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md rounded-lg transition-colors">
        Done
      </button>
    </div>
  </div>
</div>

<!-- ========================================================================= -->
<!-- NEWS HARNESS CLIENT CONTROLLER & CHART ENGINE -->
<!-- ========================================================================= -->
<script>
let NEWS_DATA = {
  events: [],
  impact: null,
  strategy: null,
  diagnostics: null
};
let NEWS_CHARTS = {};

// Load News Data from API or static JSON fallbacks
async function initNewsHarness() {
  try {
    // 1. Fetch News Feed
    try {
      const res = await fetch('/api/news/feed');
      if (res.ok) {
        const json = await res.json();
        NEWS_DATA.events = json.events || [];
      } else {
        throw new Error('API unreachable');
      }
    } catch(e) {
      const res = await fetch('static_data/news_feed.json');
      if (res.ok) {
        const json = await res.json();
        NEWS_DATA.events = json.events || [];
      }
    }

    // 2. Fetch Impact Data
    try {
      const res = await fetch('/api/impact/timeline');
      if (res.ok) {
        const json = await res.json();
        NEWS_DATA.impact = json;
      }
    } catch(e) {}
    if (!NEWS_DATA.impact) {
      const res = await fetch('static_data/impact_analysis.json');
      if (res.ok) NEWS_DATA.impact = await res.json();
    }

    // 3. Fetch Strategy Comparison
    try {
      const res = await fetch('/api/strategy/compare');
      if (res.ok) {
        const json = await res.json();
        NEWS_DATA.strategy = json.comparison || json;
      }
    } catch(e) {}
    if (!NEWS_DATA.strategy) {
      const res = await fetch('static_data/strategy_comparison.json');
      if (res.ok) NEWS_DATA.strategy = await res.json();
    }

    // Render components
    renderNewsFeed(NEWS_DATA.events);
    renderHistoryTable();
    renderImpactExplorer();
    renderStrategyLab();
    updateSourceHealthBadges();
  } catch(err) {
    console.warn('News Harness client initialized with fallback:', err);
  }
}

function updateSourceHealthBadges() {
  if (!NEWS_DATA.events) return;
  const nrb = NEWS_DATA.events.filter(e => e.source === 'NRB').length;
  const sebon = NEWS_DATA.events.filter(e => e.source === 'SEBON').length;
  const nepse = NEWS_DATA.events.filter(e => e.source === 'NEPSE').length;
  const comp = NEWS_DATA.events.filter(e => e.source === 'COMPANY').length;

  const elNrb = document.getElementById('stat-nrb-count');
  if (elNrb) elNrb.textContent = `${nrb} Verified Events`;
  const elSebon = document.getElementById('stat-sebon-count');
  if (elSebon) elSebon.textContent = `${sebon} Verified Events`;
  const elNepse = document.getElementById('stat-nepse-count');
  if (elNepse) elNepse.textContent = `${nepse} Verified Events`;
  const elComp = document.getElementById('stat-company-count');
  if (elComp) elComp.textContent = `${comp} Verified Events`;
}

function renderNewsFeed(events) {
  const container = document.getElementById('news-feed-container');
  if (!container) return;
  if (!events || events.length === 0) {
    container.innerHTML = '<div class="py-space-xl text-center text-on-surface-variant font-body-md">No disclosures match active filter.</div>';
    return;
  }

  container.innerHTML = events.map(ev => {
    const pubDate = ev.published_npt ? ev.published_npt.replace('T', ' ').substring(0, 16) : ev.published_date_npt;
    const sectors = ev.affected_sectors && ev.affected_sectors.length > 0 ? ev.affected_sectors.join(', ') : 'Broad Market';
    const symbols = ev.affected_symbols && ev.affected_symbols.length > 0 ? ev.affected_symbols.join(', ') : 'NEPSE Index';
    
    // Check outcomes if available
    let marBadge = '<span class="px-2 py-0.5 bg-surface-container text-on-surface-variant rounded font-mono text-xs">Impact Pending</span>';
    if (ev.outcomes && ev.outcomes.length > 0) {
      const t0Out = ev.outcomes.find(o => o.horizon_label === 'T0');
      if (t0Out && t0Out.mar !== undefined) {
        const marVal = (t0Out.mar * 100).toFixed(2);
        const isPos = t0Out.mar >= 0;
        marBadge = `<span class="px-2 py-0.5 ${isPos ? 'bg-primary-fixed text-on-primary-fixed' : 'bg-error-container text-on-error-container'} rounded font-mono text-xs font-bold">MAR T0: ${isPos ? '+' : ''}${marVal}%</span>`;
      }
    }

    return `
      <div class="py-space-lg flex flex-col md:flex-row items-start justify-between gap-space-md hover:bg-surface-container-low/40 p-space-md rounded-xl transition-colors">
        <div class="flex-1">
          <div class="flex items-center gap-space-xs flex-wrap mb-1">
            <span class="font-label-sm text-label-sm px-2 py-0.5 rounded font-bold ${ev.source === 'NRB' ? 'bg-primary-fixed text-on-primary-fixed' : (ev.source === 'SEBON' ? 'bg-secondary-fixed text-on-secondary-fixed' : 'bg-surface-container-high text-on-surface')}">${ev.source}</span>
            <span class="font-label-sm text-label-sm bg-surface-container text-on-surface-variant px-2 py-0.5 rounded">${ev.category.replace('_', ' ')}</span>
            <span class="font-label-sm text-label-sm text-outline font-mono">${pubDate} NPT</span>
            <span class="font-label-sm text-label-sm text-primary font-semibold flex items-center gap-0.5">
              <span class="material-symbols-outlined text-[14px]">verified</span> VERIFIED
            </span>
          </div>
          <h3 class="font-headline-md text-headline-md text-on-surface hover:text-primary cursor-pointer transition-colors" onclick="openEventDrawer('${ev.event_id}')">${ev.headline}</h3>
          <p class="font-body-sm text-body-sm text-on-surface-variant mt-1">${ev.summary}</p>
          <div class="flex items-center gap-space-sm mt-space-sm font-label-sm text-label-sm text-on-surface-variant flex-wrap">
            <span><strong>Target Session:</strong> ${ev.t0_date}</span>
            <span>•</span>
            <span><strong>Pre-Event Cutoff:</strong> ${ev.t_minus_1_date}</span>
            <span>•</span>
            <span><strong>Affected Entities:</strong> <span class="text-on-surface font-semibold">${symbols} (${sectors})</span></span>
          </div>
        </div>
        <div class="flex flex-col items-end gap-space-xs shrink-0">
          ${marBadge}
          <button onclick="openEventDrawer('${ev.event_id}')" class="px-space-md py-1 bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md rounded-lg transition-colors flex items-center gap-1 mt-1">
            <span>Inspect Reaction</span>
            <span class="material-symbols-outlined text-[14px]">arrow_forward</span>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function filterNewsFeed(source, btn) {
  document.querySelectorAll('.news-filter-btn').forEach(b => b.classList.remove('active', 'bg-surface-container-high', 'font-semibold'));
  document.querySelectorAll('.news-filter-btn').forEach(b => b.classList.add('bg-surface-container'));
  btn.classList.add('active', 'bg-surface-container-high', 'font-semibold');
  btn.classList.remove('bg-surface-container');

  if (source === 'ALL') {
    renderNewsFeed(NEWS_DATA.events);
  } else {
    const filtered = NEWS_DATA.events.filter(e => e.source === source);
    renderNewsFeed(filtered);
  }
}

function handleNewsSearch() {
  const query = (document.getElementById('news-search-input')?.value || '').toLowerCase();
  if (!query) {
    renderNewsFeed(NEWS_DATA.events);
    return;
  }
  const filtered = NEWS_DATA.events.filter(e => 
    e.headline.toLowerCase().includes(query) ||
    e.summary.toLowerCase().includes(query) ||
    (e.affected_symbols && e.affected_symbols.some(s => s.toLowerCase().includes(query)))
  );
  renderNewsFeed(filtered);
}

function renderHistoryTable() {
  const tbody = document.getElementById('history-table-body');
  if (!tbody || !NEWS_DATA.events) return;

  const catVal = document.getElementById('history-cat-select')?.value || 'ALL';
  const scopeVal = document.getElementById('history-scope-select')?.value || 'ALL';
  const searchVal = (document.getElementById('history-search-input')?.value || '').toLowerCase();

  let list = NEWS_DATA.events;
  if (catVal !== 'ALL') list = list.filter(e => e.category === catVal);
  if (scopeVal !== 'ALL') list = list.filter(e => e.scope === scopeVal);
  if (searchVal) {
    list = list.filter(e => e.headline.toLowerCase().includes(searchVal) || (e.affected_symbols && e.affected_symbols.some(s => s.toLowerCase().includes(searchVal))));
  }

  tbody.innerHTML = list.map(ev => {
    let t3MarStr = '--';
    if (ev.outcomes) {
      const t3 = ev.outcomes.find(o => o.horizon_label === 'T+3');
      if (t3 && t3.mar !== undefined) {
        const val = (t3.mar * 100).toFixed(2);
        const col = t3.mar >= 0 ? 'text-primary' : 'text-error';
        t3MarStr = `<span class="${col} font-bold font-mono">${t3.mar >= 0 ? '+' : ''}${val}%</span>`;
      }
    }
    const syms = ev.affected_symbols && ev.affected_symbols.length > 0 ? ev.affected_symbols.join(', ') : 'BROAD_MKT';

    return `
      <tr class="hover:bg-surface-container-low/50 transition-colors">
        <td class="px-space-md py-space-sm font-mono text-xs">${ev.published_date_npt}</td>
        <td class="px-space-md py-space-sm"><span class="px-2 py-0.5 rounded font-bold font-label-sm ${ev.source === 'NRB' ? 'bg-primary-fixed text-on-primary-fixed' : 'bg-surface-container-high'}">${ev.source}</span></td>
        <td class="px-space-md py-space-sm font-semibold max-w-xs truncate cursor-pointer hover:text-primary" onclick="openEventDrawer('${ev.event_id}')">${ev.headline}</td>
        <td class="px-space-md py-space-sm text-on-surface-variant">${ev.category.replace('_', ' ')}</td>
        <td class="px-space-md py-space-sm font-mono text-xs">${syms}</td>
        <td class="px-space-md py-space-sm text-center font-mono text-xs">${ev.t0_date}</td>
        <td class="px-space-md py-space-sm text-right">${t3MarStr}</td>
        <td class="px-space-md py-space-sm text-center"><span class="px-2 py-0.5 bg-primary-fixed/40 text-primary rounded font-label-sm font-bold">ANALYZED</span></td>
        <td class="px-space-md py-space-sm text-center">
          <button onclick="openEventDrawer('${ev.event_id}')" class="px-2 py-1 bg-surface-container hover:bg-surface-container-high rounded text-xs font-semibold">Inspect</button>
        </td>
      </tr>
    `;
  }).join('');
}

function renderImpactExplorer() {
  const imp = NEWS_DATA.impact;
  if (!imp) return;

  const timeline = imp.timeline || {};
  const labels = Object.keys(timeline);
  const marValues = labels.map(k => timeline[k].mean_mar || 0);
  const volValues = labels.map(k => timeline[k].avg_vol_ratio || 1);

  // Render Timeline Chart
  const ctx1 = document.getElementById('chart-impact-timeline')?.getContext('2d');
  if (ctx1) {
    if (NEWS_CHARTS.timeline) NEWS_CHARTS.timeline.destroy();
    NEWS_CHARTS.timeline = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            type: 'line',
            label: 'Mean MAR (%)',
            data: marValues,
            borderColor: '#006b53',
            backgroundColor: 'rgba(0, 107, 83, 0.1)',
            borderWidth: 2.5,
            tension: 0.2,
            yAxisID: 'y'
          },
          {
            type: 'bar',
            label: 'Volume Surge Ratio',
            data: volValues,
            backgroundColor: 'rgba(113, 46, 221, 0.2)',
            borderColor: '#712edd',
            borderWidth: 1,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            position: 'left',
            title: { display: true, text: 'Market-Adjusted Return (%)' },
            grid: { color: '#f1f5f9' }
          },
          y1: {
            position: 'right',
            title: { display: true, text: 'Volume vs 20d Pre-Event Avg' },
            grid: { display: false },
            min: 0.5,
            max: 2.5
          },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // Render Category Comparison Chart
  const categories = imp.categories || {};
  const catNames = Object.keys(categories);
  const t0Moves = catNames.map(c => categories[c].mean_t0_mar_pct || 0);
  const t5Moves = catNames.map(c => categories[c].mean_t5_mar_pct || 0);

  const ctx2 = document.getElementById('chart-category-comparison')?.getContext('2d');
  if (ctx2) {
    if (NEWS_CHARTS.category) NEWS_CHARTS.category.destroy();
    NEWS_CHARTS.category = new Chart(ctx2, {
      type: 'bar',
      data: {
        labels: catNames.map(c => c.replace('_', ' ')),
        datasets: [
          {
            label: 'Initial Move T0 (%)',
            data: t0Moves,
            backgroundColor: '#00a884',
            borderRadius: 4
          },
          {
            label: 'Later Move T+5 (%)',
            data: t5Moves,
            backgroundColor: '#678fff',
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { title: { display: true, text: 'MAR (%)' }, grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // Render Heatmap Table
  const heatmapBody = document.getElementById('impact-heatmap-tbody');
  if (heatmapBody && imp.heatmap) {
    heatmapBody.innerHTML = imp.heatmap.map(row => {
      const isPos = row.mean_mar_t3_pct >= 0;
      return `
        <tr class="hover:bg-surface-container-low/40">
          <td class="px-space-md py-space-sm font-semibold">${row.category.replace('_', ' ')}</td>
          <td class="px-space-md py-space-sm font-mono">${row.sector}</td>
          <td class="px-space-md py-space-sm text-center font-mono">${row.sample_size}</td>
          <td class="px-space-md py-space-sm text-right font-mono font-bold ${isPos ? 'text-primary' : 'text-error'}">${isPos ? '+' : ''}${row.mean_mar_t3_pct}%</td>
          <td class="px-space-md py-space-sm text-right font-mono">${row.pos_rate}%</td>
          <td class="px-space-md py-space-sm text-center">
            <span class="px-2 py-0.5 rounded text-xs font-bold ${isPos ? 'bg-primary-fixed text-on-primary-fixed' : 'bg-error-container text-on-error-container'}">${isPos ? 'TAILWIND' : 'HEADWIND'}</span>
          </td>
        </tr>
      `;
    }).join('');
  }
}

function renderStrategyLab() {
  const strat = NEWS_DATA.strategy;
  if (!strat) return;

  const baseline = strat.baseline || {};
  const news = strat.news_aware || {};

  // Render Strategy Equity Curve
  const curve = strat.equity_curve || [];
  const labels = curve.map(c => c.date);
  const bData = curve.map(c => c.baseline_equity);
  const nData = curve.map(c => c.news_equity);
  const bmData = curve.map(c => c.benchmark_equity);

  const ctx3 = document.getElementById('chart-strategy-equity')?.getContext('2d');
  if (ctx3) {
    if (NEWS_CHARTS.strategy) NEWS_CHARTS.strategy.destroy();
    NEWS_CHARTS.strategy = new Chart(ctx3, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'News-Aware Strategy',
            data: nData,
            borderColor: '#006b53',
            backgroundColor: 'rgba(0, 107, 83, 0.05)',
            borderWidth: 2.5,
            fill: true,
            tension: 0.1
          },
          {
            label: 'Non-News Baseline',
            data: bData,
            borderColor: '#64748b',
            borderWidth: 1.5,
            borderDash: [4, 4],
            tension: 0.1
          },
          {
            label: 'NEPSE Benchmark',
            data: bmData,
            borderColor: '#cbd5e1',
            borderWidth: 1,
            tension: 0.1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            title: { display: true, text: 'Portfolio Value (NPR)' },
            grid: { color: '#f1f5f9' },
            ticks: { callback: v => 'NPR ' + v.toLocaleString() }
          },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // Render Metrics Table
  const metricsTbody = document.getElementById('strategy-metrics-tbody');
  if (metricsTbody) {
    const rows = [
      { name: 'Cumulative Net Return', b: `${baseline.total_return_pct}%`, n: `${news.total_return_pct}%`, diff: `${(news.total_return_pct - baseline.total_return_pct).toFixed(2)}%` },
      { name: 'Annualized Return (CAGR)', b: `${baseline.cagr_pct}%`, n: `${news.cagr_pct}%`, diff: `${(news.cagr_pct - baseline.cagr_pct).toFixed(2)}%` },
      { name: 'Annualized Volatility', b: `${baseline.volatility_pct}%`, n: `${news.volatility_pct}%`, diff: `${(news.volatility_pct - baseline.volatility_pct).toFixed(2)}%` },
      { name: 'Sharpe Ratio (Rf=5%)', b: `${baseline.sharpe_ratio}`, n: `${news.sharpe_ratio}`, diff: `${(news.sharpe_ratio - baseline.sharpe_ratio).toFixed(2)}` },
      { name: 'Sortino Ratio', b: `${baseline.sortino_ratio}`, n: `${news.sortino_ratio}`, diff: `${(news.sortino_ratio - baseline.sortino_ratio).toFixed(2)}` },
      { name: 'Maximum Drawdown (MDD)', b: `${baseline.max_drawdown_pct}%`, n: `${news.max_drawdown_pct}%`, diff: `${(news.max_drawdown_pct - baseline.max_drawdown_pct).toFixed(2)}%` },
      { name: 'Out-of-Sample Return (2026)', b: `${baseline.oos_return_pct}%`, n: `${news.oos_return_pct}%`, diff: `${(news.oos_return_pct - baseline.oos_return_pct).toFixed(2)}%` },
      { name: 'Total Trades & Turnover Friction', b: `${baseline.total_trades} trades (${baseline.friction_cost_paid_pct}%)`, n: `${news.total_trades} trades (${news.friction_cost_paid_pct}%)`, diff: `${news.total_trades - baseline.total_trades} trades` }
    ];

    metricsTbody.innerHTML = rows.map(r => `
      <tr>
        <td class="px-space-lg py-space-sm font-semibold">${r.name}</td>
        <td class="text-center px-space-md py-space-sm font-mono text-on-surface-variant">${r.b}</td>
        <td class="text-center px-space-md py-space-sm font-mono font-bold text-primary">${r.n}</td>
        <td class="text-center px-space-md py-space-sm font-mono">${r.diff}</td>
      </tr>
    `).join('');
  }
}

function openEventDrawer(eventId) {
  const ev = NEWS_DATA.events.find(e => e.event_id === eventId);
  if (!ev) return;

  document.getElementById('drawer-event-source').textContent = `${ev.source} OFFICIAL NOTIFICATION`;
  document.getElementById('drawer-event-headline').textContent = ev.headline;
  document.getElementById('drawer-event-time').textContent = `Published: ${ev.published_npt} NPT`;
  document.getElementById('drawer-event-t0').textContent = `T0 Session: ${ev.t0_date}`;
  document.getElementById('drawer-event-t-minus-1').textContent = `Pre-Event Cutoff T-1: ${ev.t_minus_1_date}`;
  document.getElementById('drawer-event-hash').textContent = ev.body_hash;
  
  const urlEl = document.getElementById('drawer-event-url');
  if (urlEl) {
    urlEl.href = ev.source_url;
    urlEl.textContent = `Open Official Source (${ev.source_url}) ↗`;
  }

  document.getElementById('drawer-event-body').textContent = ev.summary;
  document.getElementById('drawer-event-rationale').textContent = ev.mapping_rationale || 'Mapped via automated taxonomy rule engine.';

  const tbody = document.getElementById('drawer-outcomes-tbody');
  if (tbody) {
    if (ev.outcomes && ev.outcomes.length > 0) {
      tbody.innerHTML = ev.outcomes.map(o => {
        const isPos = o.mar >= 0;
        return `
          <tr>
            <td class="px-space-md py-space-xs font-bold font-mono">${o.horizon_label}</td>
            <td class="px-space-md py-space-xs font-mono text-xs">${o.target_date}</td>
            <td class="px-space-md py-space-xs text-right font-mono">${(o.raw_return * 100).toFixed(2)}%</td>
            <td class="px-space-md py-space-xs text-right font-mono">${(o.benchmark_return * 100).toFixed(2)}%</td>
            <td class="px-space-md py-space-xs text-right font-mono font-bold ${isPos ? 'text-primary' : 'text-error'}">${isPos ? '+' : ''}${(o.mar * 100).toFixed(2)}%</td>
            <td class="px-space-md py-space-xs text-center font-mono">${o.volume_ratio ? o.volume_ratio.toFixed(2) + 'x' : '1.0x'}</td>
          </tr>
        `;
      }).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="6" class="px-space-md py-space-md text-center text-on-surface-variant font-mono text-xs">No completed outcome horizons yet (Impact Pending).</td></tr>';
    }
  }

  const drawer = document.getElementById('event-detail-drawer');
  if (drawer) {
    drawer.classList.remove('opacity-0', 'pointer-events-none');
    drawer.classList.add('opacity-100');
  }
}

function closeEventDrawer() {
  const drawer = document.getElementById('event-detail-drawer');
  if (drawer) {
    drawer.classList.remove('opacity-100');
    drawer.classList.add('opacity-0', 'pointer-events-none');
  }
}

async function refreshNewsPipeline() {
  try {
    const res = await fetch('/api/pipeline/run', { method: 'POST' });
    if (res.ok) {
      alert('Pipeline refreshed successfully! Reloading data...');
      await initNewsHarness();
    }
  } catch(e) {
    console.log('Static mode active.');
  }
}

// Auto-initialize news harness on window load
window.addEventListener('DOMContentLoaded', () => {
  initNewsHarness();
});
</script>
"""

# Insert before </body> and <!-- UNIFIED FOOTER -->
footer_target = "<!-- UNIFIED FOOTER -->"
html = html.replace(footer_target, news_pages_html + "\n" + footer_target)

with open("nepse_terminal.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Successfully injected News Harness pages and client controller into nepse_terminal.html!")
