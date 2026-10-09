import json
import pandas as pd

with open('static_data/live_nepse_snapshot.json', 'r') as f:
    d = json.load(f)

prices = d.get('today_prices', [])
df = pd.DataFrame(prices)

df['prev_close'] = pd.to_numeric(df['previousDayClosePrice'], errors='coerce')
df['ltp'] = pd.to_numeric(df['lastUpdatedPrice'], errors='coerce')
df['turnover'] = pd.to_numeric(df['totalTradedValue'], errors='coerce')
df['volume'] = pd.to_numeric(df['totalTradedQuantity'], errors='coerce')
df['pct_change'] = ((df['ltp'] - df['prev_close']) / df['prev_close']) * 100

print('=== TOP 5 GAINERS RIGHT NOW ===')
gainers = df.sort_values('pct_change', ascending=False).head(5)
for _, r in gainers.iterrows():
    val_str = f"{r['turnover']:,.2f}"
    print(f"{r['symbol']:<10} | LTP: NPR {r['ltp']:>8.2f} | Change: {r['pct_change']:>+6.2f}% | Vol: {r['volume']:>6.0f} | Turnover: NPR {val_str:>12}")

print('\n=== TOP 5 LOSERS RIGHT NOW ===')
losers = df.sort_values('pct_change', ascending=True).head(5)
for _, r in losers.iterrows():
    val_str = f"{r['turnover']:,.2f}"
    print(f"{r['symbol']:<10} | LTP: NPR {r['ltp']:>8.2f} | Change: {r['pct_change']:>+6.2f}% | Vol: {r['volume']:>6.0f} | Turnover: NPR {val_str:>12}")

print('\n=== TOP 5 TURNOVER LEADERS RIGHT NOW ===')
top_turnover = df.sort_values('turnover', ascending=False).head(5)
for _, r in top_turnover.iterrows():
    val_str = f"{r['turnover']:,.2f}"
    print(f"{r['symbol']:<10} | LTP: NPR {r['ltp']:>8.2f} | Change: {r['pct_change']:>+6.2f}% | Turnover: NPR {val_str:>14}")

print('\n=== BELLWETHERS STATUS ===')
for sym in ['NABIL', 'SHIVM', 'NTC', 'CIT', 'HDL', 'GBIME', 'EBL', 'SCB']:
    sub = df[df['symbol'] == sym]
    if not sub.empty:
        r = sub.iloc[0]
        print(f"{sym:<10} | LTP: NPR {r['ltp']:>8.2f} | Change: {r['pct_change']:>+6.2f}% | Vol: {r['volume']:>6.0f}")
