import requests
import json
from datetime import datetime
import time
import os
from py_clob_client.client import ClobClient
from ether import PolymarketEtherscanAnalyzer
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

url = "https://data-api.polymarket.com/activity"

querystring = {"limit":"10","sortDirection":"DESC","user":"0x0540f430df85c770e0a4fb79d8499d71ebc298eb","type":"trade","sortBy":"TIMESTAMP"}

fields = [
    "proxyWallet",
    "conditionId",
    "type",
    "size",
    "usdcSize",
    "transactionHash",
    "price",
    "side",
    "title",
    "tokenId",
    # 'datetime' will be added
]

filtered_file = "response_filtered.json"

# Initialize Polymarket client for getting balances
host = "https://clob.polymarket.com"
key = "24404937bdac68dc1e5e8a368ffe9340a15985d0cfd6127dbf5341c56afe17fb"
chain_id = 137
POLYMARKET_PROXY_ADDRESS = "0xF02024352ED99e13a5a3f1492769aBD2fE322029"

# Initialize client
client = ClobClient(host, key=key, chain_id=chain_id, funder=POLYMARKET_PROXY_ADDRESS)
client.set_api_creds(client.create_or_derive_api_creds())

# Initialize Etherscan analyzer for balance checking
etherscan_analyzer = PolymarketEtherscanAnalyzer(etherscan_api_key="IMTRI7NK8JNTA4IXXUZX8RF3R3BHTIPFF2")

# --- SETUP RETRY SESSION ---
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET", "POST"]
)
session.mount('https://', HTTPAdapter(max_retries=retries))

def get_user_portfolio_value(user_address):
    """Get the user's total portfolio value from their trades/positions"""
    try:
        # Get user's recent trades to estimate portfolio value
        portfolio_url = "https://data-api.polymarket.com/activity"
        portfolio_params = {
            "limit": "100",
            "user": user_address,
            "type": "trade",
            "sortBy": "TIMESTAMP",
            "sortDirection": "DESC"
        }
        
        response = session.get(portfolio_url, params=portfolio_params, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            trades = response.json()
            
            # Calculate total USD value from recent trades as proxy for portfolio
            total_value = 0
            for trade in trades[:20]:  # Use last 20 trades as sample
                usd_size = trade.get('usdcSize', 0)
                if usd_size:
                    total_value += float(usd_size)
            
            # Average trade size * 10 as rough portfolio estimate
            estimated_portfolio = (total_value / len(trades[:20])) * 10 if trades else 1000
            print(f"Estimated user portfolio value: ${estimated_portfolio:.2f}")
            return estimated_portfolio
        
    except Exception as e:
        print(f"Error getting user portfolio: {e}")
    
    # Default fallback
    return 1000.0

def get_my_usdc_balance():
    """Get my USDC balance using Etherscan API"""
    try:
        # Get my wallet address from the client
        my_address = client.get_address()
        print(f"Getting USDC balance for address: {my_address}")
        
        # Use ether.py to get USDC balance
        usdc_balance = etherscan_analyzer.get_usdc_balance(my_address)
        
        if usdc_balance > 0:
            print(f"My USDC balance (from Etherscan): ${usdc_balance:.2f}")
            return usdc_balance
        else:
            print("USDC balance is 0 or could not be retrieved")
            return 100.0  # Default fallback
        
    except Exception as e:
        print(f"Error getting USDC balance via Etherscan: {e}")
        return 100.0

def calculate_my_order_size(user_trade_size, user_portfolio_value, my_balance, max_percentage=0.15):
    """
    Calculate my order size based on the proportion of the user's portfolio they used
    
    Args:
        user_trade_size: USD size of the user's trade
        user_portfolio_value: Estimated total portfolio value of the user
        my_balance: My available USDC balance
        max_percentage: Maximum percentage of my balance to risk (default 15%)
    
    Returns:
        Calculated order size for me
    """
    try:
        # Calculate what percentage of their portfolio the user used
        portfolio_percentage = user_trade_size / user_portfolio_value if user_portfolio_value > 0 else 0.01
        
        # Calculate my proportional size
        my_proportional_size = portfolio_percentage * my_balance
        
        # Apply maximum limit (15% of balance)
        max_allowed_size = my_balance * max_percentage
        
        # Use the smaller of proportional size or max allowed
        final_size = min(my_proportional_size, max_allowed_size)
        
        print(f"User trade: ${user_trade_size:.2f} ({portfolio_percentage:.1%} of their ${user_portfolio_value:.2f} portfolio)")
        print(f"My proportional size: ${my_proportional_size:.2f}")
        print(f"Max allowed (15%): ${max_allowed_size:.2f}")
        print(f"Final order size: ${final_size:.2f}")
        
        return final_size
        
    except Exception as e:
        print(f"Error calculating order size: {e}")
        return min(10.0, my_balance * 0.01)  # Fallback to 1% of balance or $10

# Load existing transactionHashes
if os.path.exists(filtered_file):
    with open(filtered_file, "r", encoding="utf-8") as f:
        try:
            filtered = json.load(f)
        except json.JSONDecodeError:
            filtered = []
else:
    filtered = []

logged_transaction_hashes = set(entry["transactionHash"] for entry in filtered if "transactionHash" in entry)

# Get my balance once at startup
my_balance = get_my_usdc_balance()

while True:
    response = session.get(url, params=querystring, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    try:
        data = response.json()
    except Exception as e:
        print(f"Error parsing response: {e}")
        time.sleep(3)
        continue
    if not data:
        print("No data returned.")
        time.sleep(3)
        continue
    
    # Process all trades, checking each one
    new_trades_found = 0
    for entry in data:
        transaction_hash = entry.get("transactionHash")
        if transaction_hash and transaction_hash not in logged_transaction_hashes:
            # Get user's portfolio value
            user_address = entry.get("proxyWallet")
            user_portfolio_value = get_user_portfolio_value(user_address)
            
            # Get original trade details
            original_usd_size = float(entry.get("usdcSize", 0))
            original_size = float(entry.get("size", 0))
            
            # Calculate my proportional order size
            my_order_size = calculate_my_order_size(
                user_trade_size=original_usd_size,
                user_portfolio_value=user_portfolio_value,
                my_balance=my_balance
            )
            
            # Calculate my token size (keeping same price ratio)
            price = float(entry.get("price", 0.5))
            my_token_size = my_order_size / price if price > 0 else my_order_size
            
            # Create filtered entry with MY calculated sizes
            filtered_entry = {k: entry.get(k) for k in fields}
            filtered_entry["tokenId"] = entry.get("asset")
            
            # Replace size and usdcSize with MY calculated values
            filtered_entry["size"] = my_token_size
            filtered_entry["usdcSize"] = my_order_size
            
            # Add metadata about the calculation
            filtered_entry["original_size"] = original_size
            filtered_entry["original_usdcSize"] = original_usd_size
            filtered_entry["user_portfolio_value"] = user_portfolio_value
            filtered_entry["my_balance"] = my_balance
            filtered_entry["portfolio_percentage"] = (original_usd_size / user_portfolio_value) if user_portfolio_value > 0 else 0
            
            if "timestamp" in entry:
                filtered_entry["datetime"] = datetime.utcfromtimestamp(entry["timestamp"]).strftime('%Y-%m-%d %H:%M:%S UTC')
            
            filtered.append(filtered_entry)
            logged_transaction_hashes.add(transaction_hash)
            new_trades_found += 1
            
            print(f"Logged new trade with transactionHash: {transaction_hash}")
            print(f"Original: {original_size} tokens (${original_usd_size:.2f}) -> My order: {my_token_size:.2f} tokens (${my_order_size:.2f})")
    
    # Save file only if new trades were found
    if new_trades_found > 0:
        with open(filtered_file, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=4)
        print(f"✅ Found and logged {new_trades_found} new trade(s)")
    else:
        print("No new trades to log.")
    
    time.sleep(3)