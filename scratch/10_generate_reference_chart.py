import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def generate_reference_dashboard():
    # Set style
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig = plt.figure(figsize=(14, 9), dpi=300)
    
    # -------------------------------------------------------------------------
    # DATA DEFINITIONS (October 2 Base -> October 4 Forecast)
    # -------------------------------------------------------------------------
    dates = ['09/28', '09/29', '09/30', '10/01', '10/02 (Actual)', '10/04 (Pred)']
    
    # OHLC Data
    opens  = [2540.0, 2560.0, 2580.0, 2595.0, 2592.04, 2586.58]
    highs  = [2558.0, 2582.0, 2605.0, 2616.0, 2600.41, 2612.80]
    lows   = [2520.0, 2541.0, 2567.0, 2579.0, 2582.36, 2572.50]
    closes = [2552.0, 2578.0, 2595.0, 2599.0, 2586.58, 2594.15]
    
    turnover = [3.20, 3.80, 4.50, 4.80, 4.28, 4.45]
    
    top_stocks = ['NICA', 'NABIL', 'CHCL', 'AKJCL']
    top_returns = [0.51, 0.79, 0.98, 1.23]

    # Grid layout: 2 rows (Top: Main Candlestick, Bottom: 2 Subplots)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.8, 1.0], hspace=0.35, wspace=0.25)
    
    ax_main = fig.add_subplot(gs[0, :])
    ax_turnover = fig.add_subplot(gs[1, 0])
    ax_top = fig.add_subplot(gs[1, 1])

    # -------------------------------------------------------------------------
    # MAIN SUBPLOT: 5-Day Movement & Oct 4 Forecast Corridor
    # -------------------------------------------------------------------------
    x = np.arange(len(dates))
    width = 0.4
    
    # Plot Triple-Barrier Shaded Corridor around Oct 4
    ax_main.axvspan(4.3, 5.3, color='#e6f0ff', alpha=0.7, label='2.0σ Triple-Barrier Corridor')
    
    # Draw Candlesticks
    for i in range(len(dates)):
        op, cl = opens[i], closes[i]
        hi, lo = highs[i], lows[i]
        
        # Color coding
        if i == 5:
            # Predicted candle
            color = '#3b82f6'
            edge_color = '#1d4ed8'
        elif cl >= op:
            color = '#2ecc71'
            edge_color = '#27ae60'
        else:
            color = '#e74c3c'
            edge_color = '#c0392b'
            
        # Wick
        ax_main.plot([i, i], [lo, hi], color=edge_color if i!=5 else '#1d4ed8', linewidth=1.5, zorder=3)
        
        # Body
        body_bottom = min(op, cl)
        body_height = max(abs(cl - op), 1.5)
        rect = patches.Rectangle(
            (i - width/2, body_bottom), width, body_height,
            facecolor=color, edgecolor=edge_color, linewidth=1.5 if i==5 else 1.0, zorder=4
        )
        ax_main.add_patch(rect)

    # Dashed Trendline connecting Closes
    ax_main.plot(x, closes, color='#5a6b7c', linestyle='--', linewidth=1.8, alpha=0.8, zorder=2)
    
    # Horizontal Limit Barriers
    ax_main.axhline(2612.80, color='#1d4ed8', linestyle=':', linewidth=1.8, label='Upper Resistance Barrier: 2,612.80')
    ax_main.axhline(2572.50, color='#d97706', linestyle=':', linewidth=1.8, label='Stop-Loss Support Floor: 2,572.50')

    # Annotations & Barrier Labels
    ax_main.text(4.2, 2615.0, 'Upper Resistance Barrier: 2,612.80', color='#1d4ed8', fontweight='bold', fontsize=10)
    ax_main.text(4.2, 2567.0, 'Stop-Loss Support Floor: 2,572.50', color='#d97706', fontweight='bold', fontsize=10)

    # Callout Box pointing to Oct 4 Prediction
    callout_text = "Target: 2,594.15 (+0.29%)\nMeta-Prob: 0.68"
    ax_main.annotate(
        callout_text, xy=(5, 2595.0), xytext=(3.9, 2603.0),
        arrowprops=dict(arrowstyle='->', color='#1d4ed8', lw=1.2),
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#e6f0ff', edgecolor='#1d4ed8', lw=1.2),
        fontsize=10, fontweight='bold', color='#1e3a8a'
    )

    ax_main.set_xticks(x)
    ax_main.set_xticklabels(dates, fontweight='bold', fontsize=11)
    ax_main.set_ylabel('NEPSE Index Level', fontweight='bold', fontsize=12)
    ax_main.set_ylim(2510, 2630)
    ax_main.set_title('5-Day Price Movement & Oct 4 Forecast Corridor', fontweight='bold', fontsize=14, pad=12)
    ax_main.grid(True, linestyle='--', alpha=0.5)

    # -------------------------------------------------------------------------
    # BOTTOM LEFT SUBPLOT: Market Turnover
    # -------------------------------------------------------------------------
    bar_colors = ['#8fa1b3', '#8fa1b3', '#8fa1b3', '#8fa1b3', '#5a6b7c', '#3b82f6']
    bars = ax_turnover.bar(x, turnover, color=bar_colors, width=0.55, edgecolor='none')
    
    for bar in bars:
        yval = bar.get_height()
        ax_turnover.text(bar.get_x() + bar.get_width()/2.0, yval + 0.15, f'Rs. {yval:.2f}B', ha='center', va='bottom', fontsize=8.5, fontweight='bold')

    ax_turnover.set_xticks(x)
    ax_turnover.set_xticklabels(['09/28', '09/29', '09/30', '10/01', '10/02 (Actual)', '10/04 (Pred)'], fontsize=8.5)
    ax_turnover.set_ylabel('Turnover (Rs. Billion)', fontweight='bold', fontsize=10)
    ax_turnover.set_ylim(0, 6.0)
    ax_turnover.set_title('Market Turnover (Rs. 4.45B Projected)', fontweight='bold', fontsize=12)
    ax_turnover.grid(True, linestyle='--', alpha=0.5)

    # -------------------------------------------------------------------------
    # BOTTOM RIGHT SUBPLOT: Top Equities Projection
    # -------------------------------------------------------------------------
    y_pos = np.arange(len(top_stocks))
    hbars = ax_top.barh(y_pos, top_returns, color=['#a7f3d0', '#6ee7b7', '#34d399', '#10b981'], height=0.5, edgecolor='#047857')
    
    for bar in hbars:
        xval = bar.get_width()
        ax_top.text(xval + 0.05, bar.get_y() + bar.get_height()/2.0, f'+{xval:.2f}%', ha='left', va='center', fontsize=9.5, fontweight='bold', color='#065f46')

    ax_top.set_yticks(y_pos)
    ax_top.set_yticklabels(top_stocks, fontweight='bold', fontsize=10)
    ax_top.set_xlabel('Projected % Change', fontweight='bold', fontsize=10)
    ax_top.set_xlim(0, 1.6)
    ax_top.set_title('Top Equities Projection (Oct 4)', fontweight='bold', fontsize=12)
    ax_top.grid(True, linestyle='--', alpha=0.5)

    # Overall Header Title
    fig.suptitle('NEPSE Index Projected to Rebound +0.29% to 2,594.15 on Oct 4, 2026', fontweight='bold', fontsize=17, y=0.98)

    # Save artifact
    output_path = r"c:\Users\achar\Downloads\neps\scratch\nepse_oct4_reference_prediction_chart.png"
    brain_path = r"C:\Users\achar\.gemini\antigravity\brain\8d3104f3-ffe3-4b5a-a695-08ec92faa952\nepse_oct4_reference_prediction_chart.png"
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.savefig(brain_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Chart generated and saved to: {output_path}")

if __name__ == "__main__":
    generate_reference_dashboard()
