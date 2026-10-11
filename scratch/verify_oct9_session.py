import json
import duckdb
import pandas as pd
from pathlib import Path

# 1. Load Summary
with open('01_raw_data/nepse_summary_2026-10-09.json') as f:
    summary = json.load(f)

summary_dict = {item['detail'].strip(): item['value'] for item in summary}

# 2. Load Indices
with open('01_raw_data/nepse_indices_2026-10-09.json') as f:
    indices = json.load(f)

nepse_idx = next(i for i in indices if i['index'] == 'NEPSE Index')

# 3. Load Price Volume
with open('01_raw_data/nepse_price_volume_2026-10-09.json') as f:
    pv = json.load(f)
df_pv = pd.DataFrame(pv)

# Advanced / Declined / Unchanged
adv = df_pv[df_pv['percentageChange'] > 0]
dec = df_pv[df_pv['percentageChange'] < 0]
unc = df_pv[df_pv['percentageChange'] == 0]

# Top 5 Gainers
gainers = df_pv.sort_values(by='percentageChange', ascending=False).head(5)

# Top 5 Losers
losers = df_pv.sort_values(by='percentageChange', ascending=True).head(5)

# 4. Load Floorsheet
conn = duckdb.connect()
df_sample = conn.execute("SELECT * FROM read_parquet('01_raw_data/nepse_floorsheet_2026-10-09.parquet') LIMIT 1").df()
cols = df_sample.columns.tolist()
print("Floorsheet columns:", cols)

sym_col = 'stockSymbol' if 'stockSymbol' in cols else ('symbol' if 'symbol' in cols else 'stock_symbol')
qty_col = 'contractQuantity' if 'contractQuantity' in cols else 'quantity'
amt_col = 'contractAmount' if 'contractAmount' in cols else 'amount'

fs_stats = conn.execute(f"""
    SELECT 
        {sym_col} as stock_symbol,
        COUNT(*) as total_transactions,
        SUM({qty_col}) as total_volume,
        SUM({amt_col}) as total_turnover
    FROM read_parquet('01_raw_data/nepse_floorsheet_2026-10-09.parquet')
    GROUP BY {sym_col}
""").df()

# Merge with securityName from pv if available
symbol_to_name = dict(zip(df_pv['symbol'], df_pv['securityName']))
fs_stats['security_name'] = fs_stats['stock_symbol'].map(symbol_to_name).fillna('')

top_turnover = fs_stats.sort_values(by='total_turnover', ascending=False).head(5)
top_volume = fs_stats.sort_values(by='total_volume', ascending=False).head(5)
top_transactions = fs_stats.sort_values(by='total_transactions', ascending=False).head(5)

print("=" * 80)
print("NEPSE SESSION VERIFICATION: OCTOBER 9, 2026")
print("=" * 80)
print(f"NEPSE CLOSING: {nepse_idx['close']} (Current/Point: {nepse_idx['currentValue']}, Change: +{nepse_idx['change']}, % Change: +{nepse_idx['perChange']}%)")
print(f"High: {nepse_idx['high']}, Low: {nepse_idx['low']}, Prev Close: {nepse_idx['previousClose']}")
print()
print(f"ADVANCED   : {len(adv)}")
print(f"DECLINED   : {len(dec)}")
print(f"UNCHANGED  : {len(unc)}")
print(f"TOTAL SCRIPS EVALUATED (PRICE/VOLUME): {len(df_pv)}")
print()

print("--- TOP 5 GAINERS ---")
for i, (_, r) in enumerate(gainers.iterrows(), 1):
    print(f"{i}. {r['symbol']} | {r['securityName']} | LTP: NPR {r['lastTradedPrice']:.2f} | Change: +{r['percentageChange']:.2f}% | Prev: NPR {r['previousClose']:.2f}")

print("\n--- TOP 5 LOSERS ---")
for i, (_, r) in enumerate(losers.iterrows(), 1):
    print(f"{i}. {r['symbol']} | {r['securityName']} | LTP: NPR {r['lastTradedPrice']:.2f} | Change: {r['percentageChange']:.2f}% | Prev: NPR {r['previousClose']:.2f}")

print("\n--- TOP 5 TURNOVER ---")
for i, (_, r) in enumerate(top_turnover.iterrows(), 1):
    print(f"{i}. {r['stock_symbol']} | {r['security_name']} | Turnover: NPR {r['total_turnover']:,.2f} | Traded Vol: {int(r['total_volume']):,} | Txns: {int(r['total_transactions']):,}")

print("\n--- TOP 5 VOLUME ---")
for i, (_, r) in enumerate(top_volume.iterrows(), 1):
    print(f"{i}. {r['stock_symbol']} | {r['security_name']} | Volume: {int(r['total_volume']):,} shares | Turnover: NPR {r['total_turnover']:,.2f} | Txns: {int(r['total_transactions']):,}")

print("\n--- TOP 5 TRANSACTIONS ---")
for i, (_, r) in enumerate(top_transactions.iterrows(), 1):
    print(f"{i}. {r['stock_symbol']} | {r['security_name']} | Transactions: {int(r['total_transactions']):,} txns | Volume: {int(r['total_volume']):,} | Turnover: NPR {r['total_turnover']:,.2f}")

print("\n--- AGGREGATE SESSION SUMMARY METRICS ---")
print(f"MARKET TURNOVER (NPR)            : {summary_dict.get('Total Turnover Rs:', 0):,.2f}")
print(f"TOTAL TRADED SHARES              : {int(summary_dict.get('Total Traded Shares', 0)):,}")
print(f"TOTAL TRANSACTIONS               : {int(summary_dict.get('Total Transactions', 0)):,}")
print(f"TOTAL SCRIPS TRADED              : {int(summary_dict.get('Total Scrips Traded', 0))}")
print(f"TOTAL MARKET CAPITALIZATION (RS) : {summary_dict.get('Total Market Capitalization Rs:', 0):,.2f}")
print(f"TOTAL FLOAT MARKET CAP (RS)      : {summary_dict.get('Total Float Market Capitalization Rs:', 0):,.2f}")
print("=" * 80)
