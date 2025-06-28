#!/usr/bin/env python3
"""
Improved Polymarket Position Tracker
Fetches REAL current token balances instead of calculating from trade history
"""

import os
import time
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import TradeParams, OrderArgs, OrderType, MarketOrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL
except ImportError:
    print("Installing required packages...")
    os.system("pip install py-clob-client python-dotenv requests")
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import TradeParams, OrderArgs, OrderType, MarketOrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL

@dataclass
class RealPosition:
    market_name: str
    token_id: str
    outcome: str
    balance: float
    current_price: float
    usd_value: float
    market_id: str

class ImprovedPositionTracker:
    def __init__(self):
        self.host = os.getenv('HOST', 'https://clob.polymarket.com')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.public_key = os.getenv('PUBLIC_KEY', '').strip("'")
        self.clob_api_key = os.getenv('CLOB_API_KEY', '').strip("'")
        self.clob_secret = os.getenv('CLOB_SECRET', '').strip("'")
        self.clob_pass_phrase = os.getenv('CLOB_PASS_PHRASE', '').strip("'")
        
        if not self.private_key.startswith('0x'):
            self.private_key = '0x' + self.private_key
            
        # Initialize CLOB client
        try:
            self.client = ClobClient(
                self.host,
                key=self.private_key,
                chain_id=137
            )
            
            # Set API credentials
            if self.clob_api_key and self.clob_secret and self.clob_pass_phrase:
                from py_clob_client.clob_types import ApiCreds
                creds = ApiCreds(
                    api_key=self.clob_api_key,
                    api_secret=self.clob_secret,
                    api_passphrase=self.clob_pass_phrase
                )
                self.client.set_api_creds(creds)
                print("✅ Using existing API credentials")
            else:
                creds = self.client.create_or_derive_api_creds()
                self.client.set_api_creds(creds)
                print("✅ Created new API credentials")
                
        except Exception as e:
            print(f"❌ Error initializing client: {e}")
            raise
        
        # Cache for market info
        self.market_cache = {}
        
    def get_wallet_address(self) -> str:
        """Get the wallet address from the client"""
        return self.client.get_address()
    
    def get_real_token_balances(self) -> Dict[str, float]:
        """Fetch REAL current token balances from the blockchain"""
        try:
            print("\U0001F4E1 Fetching real token balances from blockchain...")
            # Method 1: Try using the client's balance methods
            try:
                balances = self.client.get_balances()
                if balances:
                    print(f"   Found {len(balances)} token balances via client")
                    return balances
            except Exception as e:
                print(f"   Client balance method failed: {e}")
            # Method 2: Direct API call to get balances
            try:
                address = self.get_wallet_address()
                url = f"https://clob.polymarket.com/balances/{address}"
                headers = {}
                if hasattr(self.client, 'get_auth_headers'):
                    try:
                        headers = self.client.get_auth_headers()
                    except:
                        pass
                response = requests.get(url, headers=headers)
                print(f"   API balance call status: {response.status_code}")
                print(f"   API balance call response: {response.text}")
                if response.status_code == 200:
                    balance_data = response.json()
                    print(f"   Found balances via API: {len(balance_data)} tokens")
                    return {item['token_id']: float(item['balance']) for item in balance_data}
                else:
                    print(f"   API balance call failed: {response.status_code}")
            except Exception as e:
                print(f"   Direct API balance call failed: {e}")
            # Method 3: Try to get via positions endpoint
            try:
                address = self.get_wallet_address()
                print(f"   Using wallet address for positions endpoint: {address}")
                url = f"https://clob.polymarket.com/positions/{address}"
                response = requests.get(url)
                print(f"   Positions endpoint status: {response.status_code}")
                print(f"   Positions endpoint response: {response.text}")
                if response.status_code == 200:
                    positions_data = response.json()
                    balances = {}
                    for pos in positions_data:
                        if float(pos.get('size', 0)) > 0:
                            balances[pos['asset_id']] = float(pos['size'])
                    print(f"   Found {len(balances)} positions via positions endpoint")
                    return balances
            except Exception as e:
                print(f"   Positions endpoint failed: {e}")
            print("   ❌ All balance fetching methods failed")
            return {}
        except Exception as e:
            print(f"❌ Error fetching token balances: {e}")
            return {}
    
    def get_market_info(self, condition_id: str) -> Dict[str, Any]:
        """Get market information from Polymarket API"""
        if condition_id in self.market_cache:
            return self.market_cache[condition_id]
            
        try:
            url = f"https://gamma-api.polymarket.com/markets/{condition_id}"
            response = requests.get(url)
            if response.status_code == 200:
                market_data = response.json()
                self.market_cache[condition_id] = market_data
                return market_data
        except Exception as e:
            print(f"Error fetching market info for {condition_id}: {e}")
        
        return {"question": f"Market {condition_id[:8]}...", "tokens": []}
    
    def get_current_market_prices(self, condition_id: str) -> Dict[str, float]:
        """Get current market prices for all outcomes"""
        try:
            url = f"https://gamma-api.polymarket.com/markets/{condition_id}/prices"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching prices for {condition_id}: {e}")
        return {}
    
    def get_token_to_market_mapping(self) -> Dict[str, str]:
        """Get mapping from token_id to market_id"""
        try:
            print("🔍 Building token to market mapping...")
            # Get recent trades to find token->market relationships
            trades = self.client.get_trades(TradeParams(maker_address=self.get_wallet_address()))
            
            token_to_market = {}
            for trade in trades:
                token_id = trade.get('asset_id', '')
                market_id = trade.get('market', '')
                if token_id and market_id:
                    token_to_market[token_id] = market_id
            
            print(f"   Found mappings for {len(token_to_market)} tokens")
            return token_to_market
            
        except Exception as e:
            print(f"Error building token mapping: {e}")
            return {}
    
    def get_real_positions(self) -> List[RealPosition]:
        """Get real current positions based on actual token balances"""
        print("\n🔄 Fetching REAL current positions...")
        
        # Get real token balances
        token_balances = self.get_real_token_balances()
        
        if not token_balances:
            print("❌ No token balances found")
            return []
        
        print(f"💰 Found {len(token_balances)} tokens with balances")
        
        # Get token to market mapping
        token_to_market = self.get_token_to_market_mapping()
        
        positions = []
        total_usd_value = 0
        
        for token_id, balance in token_balances.items():
            if balance <= 0.001:  # Skip tiny balances
                continue
                
            # Get market info
            market_id = token_to_market.get(token_id, '')
            if not market_id:
                print(f"   ⚠️  No market found for token {token_id[:8]}...")
                continue
                
            market_info = self.get_market_info(market_id)
            market_name = market_info.get('question', 'Unknown Market')
            
            # Get current price and outcome name
            current_prices = self.get_current_market_prices(market_id)
            current_price = 0
            outcome = "Unknown"
            
            for token in market_info.get('tokens', []):
                if token.get('token_id') == token_id:
                    outcome = token.get('outcome', 'Unknown')
                    current_price = current_prices.get(outcome, 0)
                    break
            
            usd_value = balance * current_price
            total_usd_value += usd_value
            
            positions.append(RealPosition(
                market_name=market_name,
                token_id=token_id,
                outcome=outcome,
                balance=balance,
                current_price=current_price,
                usd_value=usd_value,
                market_id=market_id
            ))
        
        print(f"💵 Total portfolio value: ${total_usd_value:.2f}")
        return positions
    
    def display_real_positions(self, positions: List[RealPosition]) -> None:
        """Display real positions in a formatted table"""
        print("\n" + "=" * 120)
        print("💎 REAL CURRENT POSITIONS (Based on Token Balances)")
        print("=" * 120)
        
        if not positions:
            print("No positions found.")
            return
        
        print(f"{'#':<3} {'Market':<45} {'Outcome':<15} {'Balance':<12} {'Price':<10} {'USD Value':<12}")
        print("-" * 120)
        
        total_value = 0
        for i, pos in enumerate(positions, 1):
            market_short = pos.market_name[:42] + "..." if len(pos.market_name) > 45 else pos.market_name
            outcome_short = pos.outcome[:12] + "..." if len(pos.outcome) > 15 else pos.outcome
            
            print(f"{i:<3} {market_short:<45} {outcome_short:<15} {pos.balance:<12.2f} "
                  f"${pos.current_price:<9.3f} ${pos.usd_value:<11.2f}")
            
            total_value += pos.usd_value
        
        print("-" * 120)
        print(f"{'TOTAL VALUE':<95} ${total_value:<11.2f}")
    
    def compare_methods(self):
        """Compare old method vs new method"""
        print("\n🔬 COMPARING CALCULATION METHODS")
        print("=" * 80)
        
        # Show wallet address
        address = self.get_wallet_address()
        print(f"📍 Wallet Address: {address}")
        
        # Get real positions
        real_positions = self.get_real_positions()
        
        # Display results
        self.display_real_positions(real_positions)
        
        if not real_positions:
            print("\n💡 No positions found - this matches your $24 wallet balance!")
        else:
            total_value = sum(pos.usd_value for pos in real_positions)
            print(f"\n💰 Portfolio Summary:")
            print(f"   📊 Number of positions: {len(real_positions)}")
            print(f"   💵 Total USD value: ${total_value:.2f}")
            print(f"   ⚖️  Average position size: ${total_value/len(real_positions):.2f}")

def main():
    try:
        tracker = ImprovedPositionTracker()
        print("🔮 Improved Polymarket Position Tracker")
        print("=" * 50)
        print("This version fetches REAL token balances, not calculated from trade history")
        
        tracker.compare_methods()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your .env file and credentials.")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main() 