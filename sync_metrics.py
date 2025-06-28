import os
import requests
from datetime import datetime
from supabase import create_client
from web3 import Web3
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Load env ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
RPC_URL = os.getenv("RPC_URL")

# --- Supabase client ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- HTTP session with retry ---
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[502,503,504])
session.mount("https://", HTTPAdapter(max_retries=retries))

# --- 1. Fetch positions ---
params = {
    "user": WALLET_ADDRESS,
    "limit": 500,
    "sortBy": "CURRENT",
    "sortDirection": "DESC"
}
resp = session.get("https://data-api.polymarket.com/positions",
                   params=params,
                   timeout=10,
                   headers={"User-Agent":"Mozilla/5.0"})
resp.raise_for_status()
positions = resp.json()  # list of pos dicts

# --- 2. Compute metrics ---
# Total realized = sum of realizedPnl
# Total unrealized = sum of cashPnl where not redeemable
# Win rate = fraction of positions with cashPnl>0
total_realized = sum(p.get("realizedPnl", 0) for p in positions)
total_unreal = sum(p.get("cashPnl", 0) for p in positions if not p.get("redeemable", False))
total_pnl = total_realized + total_unreal
win_rate = (sum(1 for p in positions if p.get("cashPnl",0)>0) / len(positions)) if positions else 0

# --- 3. Upsert positions into Supabase ---
for p in positions:
    record = {
        "trader_address": WALLET_ADDRESS,
        "market_id":       p["conditionId"],
        "outcome":         p["outcome"],
        "entry_time":      p.get("entryTimestamp") or p.get("timestamp"),
        "exit_time":       None,
        "entry_price":     p.get("avgPrice"),
        "exit_price":      p.get("curPrice"),
        "size":            p.get("size"),
        "realized_pnl":    p.get("realizedPnl"),
        "unrealized_pnl":  p.get("cashPnl"),
        "redeemable":      p.get("redeemable"),
        "win":             (p.get("cashPnl",0) > 0)
    }
    supabase.table("positions") \
      .upsert(record, on_conflict="trader_address,market_id,outcome") \
      .execute()

# --- 4. Upsert metrics ---
metrics = {
    "trader_address":       WALLET_ADDRESS,
    "total_pnl":            total_pnl,
    "total_realized_pnl":   total_realized,
    "total_unrealized_pnl": total_unreal,
    "win_rate":             win_rate
}
supabase.table("trader_metrics") \
  .upsert(metrics, on_conflict="trader_address") \
  .execute()

print("Synced positions and metrics:")
print(f" Total PnL: {total_pnl}")
print(f" Realized PnL: {total_realized}")
print(f" Unrealized PnL: {total_unreal}")
print(f" Win Rate: {win_rate:.2%}")