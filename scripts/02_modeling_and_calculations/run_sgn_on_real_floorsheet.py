import duckdb
import json
import pandas as pd
import importlib.util
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.03_data_access_and_storage.duckdb_connection_manager import connection_manager

sgn_path = Path("scripts/02_modeling_and_calculations/syndicate_graph_network.py")
spec = importlib.util.spec_from_file_location("syndicate_graph_network", sgn_path)
sgn_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sgn_mod)
SyndicateGraphNetwork = sgn_mod.SyndicateGraphNetwork
asdict = sgn_mod.asdict

p = "01_raw_data/nepse_floorsheet_2026-10-07.parquet"
with connection_manager.acquire() as conn:
  # Explicit clean SQL projection to avoid duplicate columns
  df_clean = conn.execute(f"""
      SELECT 
          stockSymbol as symbol,
          buyerMemberId as buyer_broker,
          sellerMemberId as seller_broker,
          contractQuantity as quantity,
          contractRate as rate
      FROM "{p}"
  """).df()

print(f"Loaded {len(df_clean)} ticks from Oct 7, 2026.")
sgn = SyndicateGraphNetwork(coordination_threshold=0.55, min_brokers_in_cartel=2)

symbols_to_test = ["SAHAS", "NGPL", "NABIL", "SHIVM", "API", "CHCL"]
results = []

for sym in symbols_to_test:
    res = sgn.detect_collusion_subgraph(df_clean, sym)
    results.append(asdict(res))

print("\n--- ACTUAL REAL-WORLD OCTOBER 7, 2026 BROKER SYNDICATE DETECTION ---")
print(json.dumps(results, indent=2))
