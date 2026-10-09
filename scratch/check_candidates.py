import pandas as pd

df = pd.read_csv('nepse_data_all/2026_10_06.csv')
for sym in ['SLBSL', 'HLBSL', 'ACLBSL', 'CGH', 'SHIVM', 'FOWAD']:
    sub = df[df['symbol'] == sym]
    if not sub.empty:
        r = sub.iloc[0]
        print(f"{sym:<8} | Close: NPR {r['closePrice']:>7.2f} | Prev: NPR {r['previousDayClosePrice']:>7.2f} | High: NPR {r['highPrice']:>7.2f} | Low: NPR {r['lowPrice']:>7.2f} | Vol: {r['totalTradedQuantity']:>6} shares | Val: NPR {r['totalTradedValue']:>10,.2f}")
