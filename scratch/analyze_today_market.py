import pandas as pd
import numpy as np

df = pd.read_csv("nepse_data_all/2026_10_06.csv")

total_turnover = df['totalTradedValue'].sum()
total_volume = df['totalTradedQuantity'].sum()
total_trades = df['totalTrades'].sum()
ticker_count = len(df)

df['change_pct'] = ((df['closePrice'] - df['previousDayClosePrice']) / df['previousDayClosePrice']) * 100

gainers = df[df['change_pct'] > 0]
losers = df[df['change_pct'] < 0]
unchanged = df[df['change_pct'] == 0]

avg_mkt_change = df['change_pct'].mean()
median_mkt_change = df['change_pct'].median()

print("=" * 80)
print("NEPSE MARKET REPORT: TODAY (TUESDAY, OCTOBER 6, 2026)")
print("=" * 80)
print(f"Total Traded Securities:   {ticker_count}")
print(f"Total Market Turnover:     NPR {total_turnover:,.2f} ({total_turnover / 1e9:.2f} Billion)")
print(f"Total Traded Shares:       {total_volume:,.0f}")
print(f"Total Market Transactions: {total_trades:,.0f}")
print(f"Market Breadth:            Gainers: {len(gainers)} | Losers: {len(losers)} | Unchanged: {len(unchanged)}")
print(f"Equal-Weight Market Move:  {avg_mkt_change:+.2f}% (Median: {median_mkt_change:+.2f}%)")
print("-" * 80)

print("\n--- TOP 5 GAINERS TODAY ---")
top_g = df.sort_values('change_pct', ascending=False).head(5)
for idx, r in top_g.iterrows():
    print(f"  {r['symbol']:<10} | Close: NPR {r['closePrice']:>7.2f} | Change: {r['change_pct']:>+6.2f}% | Turnover: NPR {r['totalTradedValue']:>12,.2f}")

print("\n--- TOP 5 LOSERS TODAY ---")
top_l = df.sort_values('change_pct', ascending=True).head(5)
for idx, r in top_l.iterrows():
    print(f"  {r['symbol']:<10} | Close: NPR {r['closePrice']:>7.2f} | Change: {r['change_pct']:>+6.2f}% | Turnover: NPR {r['totalTradedValue']:>12,.2f}")

print("\n--- TOP 5 TURNOVER LEADERS TODAY ---")
top_t = df.sort_values('totalTradedValue', ascending=False).head(5)
for idx, r in top_t.iterrows():
    print(f"  {r['symbol']:<10} | Close: NPR {r['closePrice']:>7.2f} | Change: {r['change_pct']:>+6.2f}% | Turnover: NPR {r['totalTradedValue']:>12,.2f}")

# Check yesterday's top 10 recommended tickers:
print("\n--- OCT 5 AUDITED RECOMMENDATIONS PERFORMANCE TODAY (OCT 6) ---")
oct5_recs = ["GFCL", "MEN", "BANDIPUR", "SHIVM", "MFIL", "PFL", "TTL", "SARBTM", "BBC", "SOHL"]
held = df[df['symbol'].isin(oct5_recs)].sort_values('symbol')
for idx, r in held.iterrows():
    print(f"  {r['symbol']:<10} | Close: NPR {r['closePrice']:>7.2f} | PrevClose: NPR {r['previousDayClosePrice']:>7.2f} | Change: {r['change_pct']:>+6.2f}% | Turnover: NPR {r['totalTradedValue']:>12,.2f}")
print("=" * 80)
