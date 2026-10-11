import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Set style
plt.style.use('dark_background')
fig = plt.figure(figsize=(14, 8), dpi=200)

# Load data
DATA_PATH = Path("C:/Users/achar/Downloads/neps/02_processed_parquet/nepse_index.parquet")
df = pd.read_parquet(DATA_PATH)
df['date'] = pd.to_datetime(df['date'])
df = df[df['date'] >= '2014-01-01'].sort_values('date').reset_index(drop=True)

# Weekly Friday resample for Friday Closings
df.set_index('date', inplace=True)
friday_df = df['close'].resample('W-FRI').last().dropna().reset_index()

# Calculate returns
friday_df['ret'] = friday_df['close'].pct_change().fillna(0)

# Key Historical News / Regulatory Shock Windows in NEPSE
# (NRB Capital Directive, Interest Rate Shocks, Margin Cap Introductions/Relaxations)
news_events = [
    {"date": "2015-07-24", "label": "2015: NRB 4x Bank Capital Mandate", "type": "bull", "impact": 0.08},
    {"date": "2016-07-22", "label": "2016: Peak Capital Right Share Gluts", "type": "bear", "impact": -0.06},
    {"date": "2017-02-15", "label": "2017: NRB Liquidity Tightening", "type": "bear", "impact": -0.05},
    {"date": "2020-03-20", "label": "2020: COVID-19 Stimulus & Online TMS", "type": "bull", "impact": 0.09},
    {"date": "2021-08-13", "label": "2021: NRB 4/12 Cr Margin Cap & 150% Risk Weight", "type": "bear", "impact": -0.12},
    {"date": "2022-06-20", "label": "2022: NRB Policy Rate Hike to 8.5%", "type": "bear", "impact": -0.07},
    {"date": "2023-12-10", "label": "2023: NRB Monetary Review Easing", "type": "bull", "impact": 0.05},
    {"date": "2024-07-26", "label": "2024: Margin Lending Cap Lifted to 20 Cr", "type": "bull", "impact": 0.07},
    {"date": "2026-08-15", "label": "2026: Institutional Margin Ceiling Removed", "type": "bull", "impact": 0.06},
]

# Separate News Shock vs Non-News Drift
# Identify weeks adjacent to major news events or high volatility policy announcements
news_dates = [pd.to_datetime(e["date"]) for e in news_events]

friday_df['is_news_shock'] = False
friday_df['news_shock_ret'] = 0.0

for nd in news_dates:
    # Match closest Friday
    idx = (friday_df['date'] - nd).abs().idxmin()
    # Tag window (-1 to +2 weeks around event)
    for offset in range(-1, 3):
        cur_idx = idx + offset
        if 0 <= cur_idx < len(friday_df):
            friday_df.loc[cur_idx, 'is_news_shock'] = True

# For high absolute return weeks exceeding 2.5 sigma, tag as market-moving news disclosures
mean_ret = friday_df['ret'].mean()
std_ret = friday_df['ret'].std()
outlier_mask = (friday_df['ret'] - mean_ret).abs() > 2.0 * std_ret
friday_df['is_news_shock'] = friday_df['is_news_shock'] | outlier_mask

# Decompose return:
# non-news return is smoothed market drift
friday_df['non_news_ret'] = np.where(
    friday_df['is_news_shock'],
    np.sign(friday_df['ret']) * np.minimum(np.abs(friday_df['ret']), 0.003), # capped fundamental drift
    friday_df['ret']
)
friday_df['news_impact_ret'] = friday_df['ret'] - friday_df['non_news_ret']

# Construct trajectories starting at 2014 base
base_price = friday_df.loc[0, 'close']
friday_df['actual_index'] = friday_df['close']
friday_df['without_news_index'] = base_price * (1 + friday_df['non_news_ret']).cumprod()
friday_df['cum_news_impact_multiplier'] = (1 + friday_df['news_impact_ret']).cumprod()

# ----------------- PLOTTING -----------------
gs = fig.add_gridspec(2, 1, height_ratios=[2.5, 1.2], hspace=0.18)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1], sharex=ax1)

# Colors
COLOR_ACTUAL = "#00F0FF"      # Electric Cyan
COLOR_NO_NEWS = "#FFAA00"     # Amber / Gold
COLOR_BULL = "#00E676"        # Vivid Green
COLOR_BEAR = "#FF1744"        # Crimson Red
COLOR_GRID = "#22272E"
COLOR_TEXT = "#E6EDF3"

# Top Panel: Trajectories
ax1.plot(friday_df['date'], friday_df['actual_index'], color=COLOR_ACTUAL, lw=2.2, label='Actual NEPSE Friday Close (With All News & Policy Shocks)')
ax1.plot(friday_df['date'], friday_df['without_news_index'], color=COLOR_NO_NEWS, lw=1.8, ls='--', alpha=0.9, label='Counterfactual Trajectory (Without News Shocks — Fundamental Drift Only)')

# Fill between to show the massive news spread
ax1.fill_between(friday_df['date'], friday_df['actual_index'], friday_df['without_news_index'],
                 where=(friday_df['actual_index'] >= friday_df['without_news_index']),
                 color='#00F0FF', alpha=0.12, label='News-Driven Bull Expansion')
ax1.fill_between(friday_df['date'], friday_df['actual_index'], friday_df['without_news_index'],
                 where=(friday_df['actual_index'] < friday_df['without_news_index']),
                 color='#FF1744', alpha=0.12, label='News-Driven Policy Compression')

# Annotations for key news catalysts
annotations = [
    (pd.to_datetime('2016-07-22'), 1881, "2016 Right Share Frenzy\n(NRB 4x Capital Mandate)", (-80, 45)),
    (pd.to_datetime('2019-03-01'), 1100, "2019 Liquidity Crunch\n(Pre-COVID Lows)", (30, -50)),
    (pd.to_datetime('2021-08-13'), 3198, "ATH 3,198 (Aug 2021)\nNRB 4/12 Cr Margin Cap Crash", (-110, 30)),
    (pd.to_datetime('2024-07-26'), 2760, "2024 Policy Easing\n(20 Cr Ceiling Removed)", (-70, 35)),
    (friday_df['date'].iloc[-1], friday_df['actual_index'].iloc[-1], f"Oct 2026 Friday Close: {friday_df['actual_index'].iloc[-1]:.1f}", (25, -15))
]

for d, val, txt, offset in annotations:
    ax1.annotate(
        txt,
        xy=(d, val),
        xytext=(offset[0], offset[1]),
        textcoords="offset points",
        arrowprops=dict(arrowstyle="->", color="#FFFFFF", lw=1.0, alpha=0.8),
        fontsize=8.5,
        fontweight='bold',
        color="#FFFFFF",
        bbox=dict(boxstyle="round,pad=0.25", fc="#161B22", ec="#30363D", lw=1.0, alpha=0.9)
    )

ax1.set_ylabel("NEPSE Index Points", fontsize=11, fontweight='bold', color=COLOR_TEXT)
ax1.set_ylim(500, 3600)
ax1.grid(True, color=COLOR_GRID, linestyle=':', alpha=0.7)
ax1.legend(loc='upper left', frameon=True, facecolor='#161B22', edgecolor='#30363D', fontsize=9.5)
ax1.set_title("NEPSE 2014 – 2026 Friday Closing: Actual Market vs. Without News Shocks", fontsize=14, fontweight='bold', pad=12, color='#FFFFFF')

# Bottom Panel: Net News Shocks & Impact Multiplier
bar_colors = [COLOR_BULL if r >= 0 else COLOR_BEAR for r in friday_df['news_impact_ret']]
ax2.bar(friday_df['date'], friday_df['news_impact_ret'] * 100, color=bar_colors, width=5, alpha=0.65, label='Weekly News Event Return Shock (%)')

ax2_twin = ax2.twinx()
ax2_twin.plot(friday_df['date'], (friday_df['cum_news_impact_multiplier'] - 1.0) * 100, color='#D2A8FF', lw=1.8, label='Cumulative News Impact Multiplier (%)')
ax2_twin.set_ylabel("Cumulative News Multiplier (%)", fontsize=10, fontweight='bold', color='#D2A8FF')
ax2_twin.grid(False)

ax2.set_ylabel("News Shock (%)", fontsize=10, fontweight='bold', color=COLOR_TEXT)
ax2.set_xlabel("Year (2014 to Friday Close Oct 2026)", fontsize=11, fontweight='bold', color=COLOR_TEXT)
ax2.grid(True, color=COLOR_GRID, linestyle=':', alpha=0.7)
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

# Combined legend for bottom panel
lines1, labels1 = ax2.get_legend_handles_labels()
lines2, labels2 = ax2_twin.get_legend_handles_labels()
ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, facecolor='#161B22', edgecolor='#30363D', fontsize=8.5)

plt.tight_layout()

# Save outputs to both artifact locations and workspace
out_dir1 = Path(r"C:\Users\achar\.local\share\openresearch\files\neps\news-intelligence\figures")
out_dir1.mkdir(parents=True, exist_ok=True)
p1 = out_dir1 / "nepse_news_impact_2014_2026.png"

out_dir2 = Path(r"C:\Users\achar\.gemini\antigravity-cli\brain\c047247d-5384-41e4-bf68-cbfd0a8bf1bc")
p2 = out_dir2 / "nepse_news_impact_2014_2026.png"

out_dir3 = Path("figures")
out_dir3.mkdir(parents=True, exist_ok=True)
p3 = out_dir3 / "nepse_news_impact_2014_2026.png"

fig.savefig(p1, bbox_inches='tight')
fig.savefig(p2, bbox_inches='tight')
fig.savefig(p3, bbox_inches='tight')
print(f"Saved figure to:\n {p1}\n {p2}\n {p3}")
plt.close(fig)
