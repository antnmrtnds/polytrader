"""
Polymarket Trade Copier
- Reads trades from response_filtered.json
- Attempts each trade only once (no retries)
- Logs successful trades to successful_trades.json
- Tracks attempted trades in placed_trades.json to avoid re-attempts
"""

import json
import time
import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

# Debug: Print the constants
print(f"BUY constant: {BUY} (type: {type(BUY)})")
print(f"SELL constant: {SELL} (type: {type(SELL)})")

# --- User config ---
host = "https://clob.polymarket.com"
key = "24404937bdac68dc1e5e8a368ffe9340a15985d0cfd6127dbf5341c56afe17fb"
chain_id = 137
POLYMARKET_PROXY_ADDRESS = "0xF02024352ED99e13a5a3f1492769aBD2fE322029"
# signature_type = 2  # 1 for email/magic, 2 for browser wallet, or omit for EOA

# Maximum percentage of balance to use per trade (15%)
MAX_TRADE_PERCENTAGE = 0.15

# --- Initialize client ---
# Using EOA (no signature_type specified) since we're using a raw private key
client = ClobClient(host, key=key, chain_id=chain_id, funder=POLYMARKET_PROXY_ADDRESS)
client.set_api_creds(client.create_or_derive_api_creds())

def get_my_usdc_balance():
    """Get my current USDC balance from Polymarket"""
    try:
        # Direct API call to get balance
        try:
            my_address = client.get_address()
            balance_url = f"https://clob.polymarket.com/balances/{my_address}"
            
            headers = {}
            if hasattr(client, 'get_auth_headers'):
                try:
                    headers = client.get_auth_headers()
                except:
                    pass
            
            import requests
            response = requests.get(balance_url, headers=headers)
            if response.status_code == 200:
                balance_data = response.json()
                usdc_balance = 0
                
                for item in balance_data:
                    if item.get('token_id') == "0" or 'usdc' in str(item.get('token_id', '')).lower():
                        usdc_balance += float(item.get('balance', 0))
                
                if usdc_balance > 0:
                    print(f"Current USDC balance: ${usdc_balance:.2f}")
                    return usdc_balance
        except Exception as e:
            print(f"API balance method failed: {e}")
        
        # Fallback: Use a reasonable default for testing
        print("Could not get USDC balance, using default $100")
        return 100.0
        
    except Exception as e:
        print(f"Error getting USDC balance: {e}")
        return 100.0

def validate_and_adjust_order_size(usd_size, current_balance):
    """
    Validate and adjust order size to not exceed maximum percentage of balance
    
    Args:
        usd_size: Requested USD size of the order
        current_balance: Current available USDC balance
    
    Returns:
        Adjusted USD size that respects the maximum limit
    """
    max_allowed = current_balance * MAX_TRADE_PERCENTAGE
    
    if usd_size > max_allowed:
        print(f"⚠️  Order size ${usd_size:.2f} exceeds maximum allowed ${max_allowed:.2f} (15% of ${current_balance:.2f})")
        print(f"Adjusting order size to ${max_allowed:.2f}")
        return max_allowed
    else:
        print(f"✅ Order size ${usd_size:.2f} is within limit (15% = ${max_allowed:.2f})")
        return usd_size

# --- Helper: Map side string to constant ---
def get_side_enum(side_str):
    result = BUY if side_str.upper() == "BUY" else SELL
    print(f"get_side_enum('{side_str}') -> {result} (type: {type(result)})")
    return result

# --- Helper: Get token_id for a trade (you may need to implement this) ---
def get_token_id_for_trade(trade):
    # If your log includes token_id, use it directly.
    # Otherwise, you must map from title/conditionId to token_id using the Markets API.
    # For now, raise an error if not present.
    if "token_id" in trade:
        return trade["token_id"]
    raise NotImplementedError("You must implement token_id lookup for the trade.")

# --- Main loop ---
logged_trades_file = "response_filtered.json"
placed_trades_file = "placed_trades.json"
successful_trades_file = "successful_trades.json"

# Load already attempted trades (by transactionHash) - to avoid re-attempting
if os.path.exists(placed_trades_file):
    with open(placed_trades_file, "r", encoding="utf-8") as f:
        attempted_trades = set(json.load(f))
else:
    attempted_trades = set()

# Load successful trades list
if os.path.exists(successful_trades_file):
    with open(successful_trades_file, "r", encoding="utf-8") as f:
        successful_trades = json.load(f)
else:
    successful_trades = []

while True:
    if not os.path.exists(logged_trades_file):
        print("No logged trades file found.")
        time.sleep(3)
        continue

    try:
        with open(logged_trades_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                print(f"⚠️  {logged_trades_file} is empty, skipping this iteration...")
                time.sleep(3)
                continue
            trades = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"⚠️  Error reading {logged_trades_file}: {e}")
        print("File might be being written to by another process. Retrying in 3 seconds...")
        time.sleep(3)
        continue

    for trade in trades:
        transaction_hash = trade.get("transactionHash")
        if not transaction_hash or transaction_hash in attempted_trades:
            continue  # Skip trades we've already attempted

        # Mark this trade as attempted immediately to avoid re-attempts
        attempted_trades.add(transaction_hash)
        with open(placed_trades_file, "w", encoding="utf-8") as pf:
            json.dump(list(attempted_trades), pf, ensure_ascii=False, indent=4)

        try:
            # Get current balance for validation
            current_balance = get_my_usdc_balance()
            
            side = get_side_enum(trade["side"])
            price = float(trade["price"])
            
            # Get the calculated USD size (already adjusted for my balance in get_user.py)
            usd_size = float(trade["usdcSize"])
            
            # Additional validation: ensure we don't exceed 15% of current balance
            validated_usd_size = validate_and_adjust_order_size(usd_size, current_balance)
            
            # Calculate token size based on validated USD size
            size = validated_usd_size / price if price > 0 else validated_usd_size

            # --- Enforce Polymarket minimums ---
            min_usd = 1.0
            min_tokens = 5.0
            # Calculate what $1 is in tokens
            tokens_for_1usd = min_usd / price if price > 0 else min_tokens
            # If either is below minimum, bump both up to the higher minimum
            if validated_usd_size < min_usd or size < min_tokens:
                # Determine which minimum is higher in value
                usd_for_5tokens = price * min_tokens
                if usd_for_5tokens > min_usd:
                    # 5 tokens is the higher minimum
                    size = min_tokens
                    validated_usd_size = size * price
                else:
                    # $1 is the higher minimum
                    validated_usd_size = min_usd
                    size = validated_usd_size / price if price > 0 else min_tokens
                print(f"⚠️  Trade size below Polymarket minimum. Bumping to at least ${validated_usd_size:.2f} or {size:.2f} tokens.")

            token_id = trade["tokenId"]

            print(f"\n📊 Trade Details:")
            print(f"   Market: {trade.get('title', 'Unknown')[:50]}...")
            print(f"   Side: {trade['side']}")
            print(f"   Price: ${price:.3f}")
            print(f"   Original size: {trade.get('original_size', 'N/A')} tokens (${trade.get('original_usdcSize', 'N/A')})")
            print(f"   My calculated size: {size:.2f} tokens (${validated_usd_size:.2f})")
            print(f"   Portfolio %: {trade.get('portfolio_percentage', 0):.1%}")

            order_args = OrderArgs(
                price=price,
                size=size,
                side=side,
                token_id=token_id,
            )
            print("OrderArgs to be signed:", order_args.__dict__, "side type:", type(order_args.side))
            print("Using key:", key)
            print("Using funder address:", POLYMARKET_PROXY_ADDRESS)
            resp = client.create_and_post_order(order_args)
            print(f"✅ Successfully placed order for conditionId {transaction_hash}: {resp}")

            # Log successful trade with full details
            successful_trade = {
                "conditionId": transaction_hash,
                "tokenId": token_id,
                "side": trade["side"],
                "price": price,
                "size": size,
                "usdcSize": validated_usd_size,
                "title": trade.get('title', 'Unknown'),
                "original_trade": trade,
                "order_response": resp,
                "placed_at": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
            }
            
            successful_trades.append(successful_trade)
            with open(successful_trades_file, "w", encoding="utf-8") as sf:
                json.dump(successful_trades, sf, ensure_ascii=False, indent=4)
            
            print(f"🎯 Trade logged to {successful_trades_file}")

        except Exception as e:
            print(f"❌ Failed to place order for conditionId {transaction_hash}: {e}")
            print(f"   This trade will not be retried.")

    time.sleep(3)