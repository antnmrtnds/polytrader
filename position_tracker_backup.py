#!/usr/bin/env python3
"""
Polymarket Copied Trades Tracker CLI
Tracks only successful copied trades from place_order.py
Shows positions, PnL, and open orders for copied trades only
Refreshes every 3 seconds
"""

import os
import time
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import TradeParams, BookParams
except ImportError:
    print("Installing required packages...")
    os.system("pip install py-clob-client python-dotenv requests")
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import TradeParams, BookParams

@dataclass
class Position:
    market_name: str
    token_id: str
    side: str
    size: float
    avg_price: float
    current_price: float
    pnl: float
    pnl_percentage: float
    market_id: str

@dataclass
class OpenOrder:
    order_id: str
    market_name: str
    side: str
    size: float
    price: float
    filled_size: float
    remaining_size: float
    status: str

class PolymarketTracker:
    def __init__(self):
        self.host = os.getenv('HOST', 'https://clob.polymarket.com')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.public_key = os.getenv('PUBLIC_KEY', '').strip("'")
        self.clob_api_key = os.getenv('CLOB_API_KEY', '').strip("'")
        self.clob_secret = os.getenv('CLOB_SECRET', '').strip("'")
        self.clob_pass_phrase = os.getenv('CLOB_PASS_PHRASE', '').strip("'")
        
        # Initialize CLOB client
        self.client = ClobClient(
            self.host,
            key=self.private_key,
            chain_id=137
        )
        
        # Set API credentials
        try:
            self.client.set_api_creds(self.client.create_or_derive_api_creds())
        except Exception as e:
            print(f"Warning: Could not set API credentials: {e}")
        
        # Cache for market info
        self.market_cache = {}
        
        # File to track successful copied trades
        self.successful_trades_file = "successful_trades.json"
        
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
    
    def get_current_market_prices(self, condition_id: str, token_id: str = None) -> Dict[str, float]:
        """Get current market prices using CLOB get_prices endpoint (best bid/ask midpoint)"""
        try:
            if token_id:
                try:
                    # Get both BUY (bid) and SELL (ask) prices for the token
                    params = [
                        BookParams(token_id=token_id, side="BUY"),
                        BookParams(token_id=token_id, side="SELL"),
                    ]
                    resp = self.client.get_prices(params=params)
                    if token_id in resp:
                        prices = resp[token_id]
                        best_bid = float(prices.get("BUY", 0))
                        best_ask = float(prices.get("SELL", 0))
                        if best_bid and best_ask:
                            midpoint = (best_bid + best_ask) / 2
                        else:
                            midpoint = best_bid or best_ask
                        return {"midpoint": midpoint, "bid": best_bid, "ask": best_ask}
                except Exception:
                    pass
            return {}
        except Exception:
            return {}
    
    def get_successful_copied_trades(self) -> List[Dict[str, Any]]:
        """Get the list of successful copied trades"""
        try:
            if os.path.exists(self.successful_trades_file):
                with open(self.successful_trades_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading successful trades: {e}")
            return []
    
    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades for the user"""
        try:
            trades = self.client.get_trades(
                TradeParams(
                    maker_address=self.client.get_address(),
                )
            )
            return trades[:limit] if trades else []
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []
    
    def get_open_orders(self) -> List[OpenOrder]:
        """Get current open orders"""
        try:
            # Make direct API call to get orders
            headers = self._get_headers()
            url = f"{self.host}/data/orders"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                orders_data = response.json()
                open_orders = []
                
                for order in orders_data:
                    market_info = self.get_market_info(order.get('market', ''))
                    market_name = market_info.get('question', 'Unknown Market')
                    
                    open_orders.append(OpenOrder(
                        order_id=order.get('id', ''),
                        market_name=market_name,
                        side=order.get('side', ''),
                        size=float(order.get('original_size', 0)),
                        price=float(order.get('price', 0)),
                        filled_size=float(order.get('size_matched', 0)),
                        remaining_size=float(order.get('size', 0)),
                        status=order.get('status', '')
                    ))
                
                return open_orders
        except Exception as e:
            print(f"Error fetching open orders: {e}")
        
        return []
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Add authentication headers if available
        if hasattr(self.client, 'get_auth_headers'):
            try:
                auth_headers = self.client.get_auth_headers()
                headers.update(auth_headers)
            except:
                pass
        
        return headers
    
    def calculate_positions(self, copied_trades: List[Dict[str, Any]]) -> List[Position]:
        """Calculate current positions from successful copied trades only"""
        positions_data = {}
        for copied_trade in copied_trades:
            condition_id = copied_trade.get('conditionId', '')
            token_id = copied_trade.get('tokenId', '')
            side = copied_trade.get('side', '')
            size = float(copied_trade.get('size', 0))
            price = float(copied_trade.get('price', 0))
            title = copied_trade.get('title', 'Unknown Market')
            key = f"{condition_id}_{token_id}"
            if key not in positions_data:
                positions_data[key] = {
                    'condition_id': condition_id,
                    'token_id': token_id,
                    'title': title,
                    'total_size': 0,
                    'total_cost': 0,
                    'trades': []
                }
            if side.upper() == 'BUY':
                positions_data[key]['total_size'] += size
                positions_data[key]['total_cost'] += size * price
            else:
                positions_data[key]['total_size'] -= size
                positions_data[key]['total_cost'] -= size * price
            positions_data[key]['trades'].append(copied_trade)
        positions = []
        for key, data in positions_data.items():
            if abs(data['total_size']) < 0.001:
                continue
            # Check if the market is unresolved
            market_info = self.get_market_info(data['condition_id'])
            if market_info.get('resolved', False):
                continue  # Skip resolved markets
            market_name = data['title']
            avg_price = abs(data['total_cost'] / data['total_size']) if data['total_size'] != 0 else 0
            current_prices = self.get_current_market_prices(data['condition_id'], data['token_id'])
            current_price = current_prices.get('midpoint', avg_price)
            pnl = data['total_size'] * (current_price - avg_price) if data['total_size'] > 0 else abs(data['total_size']) * (avg_price - current_price)
            pnl_percentage = (pnl / abs(data['total_cost'])) * 100 if data['total_cost'] != 0 else 0
            positions.append(Position(
                market_name=market_name,
                token_id=data['token_id'],
                side='LONG' if data['total_size'] > 0 else 'SHORT',
                size=abs(data['total_size']),
                avg_price=avg_price,
                current_price=current_price,
                pnl=pnl,
                pnl_percentage=pnl_percentage,
                market_id=data['condition_id']
            ))
        return positions
    
    def display_dashboard(self):
        """Display the trading dashboard"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 100)
        print(f"🔮 POLYMARKET COPIED TRADES TRACKER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📍 Address: {self.public_key}")
        print("=" * 100)
        copied_trades = self.get_successful_copied_trades()
        positions = self.calculate_positions(copied_trades)
        open_orders = self.get_open_orders()
        print("\n📊 CURRENT POSITIONS")
        print("-" * 120)
        if positions:
            print(f"{'#':<3} {'Market':<70} {'Side':<6} {'Size':<10} {'Avg Price':<10} {'Current':<10} {'PnL':<12} {'PnL %':<10}")
            print("-" * 120)
            total_pnl = 0
            for i, pos in enumerate(positions, 1):
                pnl_color = "🟢" if pos.pnl >= 0 else "🔴"
                market_full = pos.market_name
                print(f"{i:<3} {market_full:<70} {pos.side:<6} {pos.size:<10.2f} "
                      f"${pos.avg_price:<9.3f} ${pos.current_price:<9.3f} "
                      f"{pnl_color}${pos.pnl:<10.2f} {pos.pnl_percentage:<9.1f}%")
                total_pnl += pos.pnl
            print("-" * 120)
            total_color = "🟢" if total_pnl >= 0 else "🔴"
            print(f"{'TOTAL PnL':<110} {total_color}${total_pnl:<10.2f}")
        else:
            print("No open positions found.")
        print(f"\n📋 OPEN ORDERS ({len(open_orders)})")
        print("-" * 100)
        if open_orders:
            print(f"{'Market':<40} {'Side':<6} {'Size':<10} {'Price':<10} {'Filled':<10} {'Status':<10}")
            print("-" * 100)
            for order in open_orders:
                market_short = order.market_name[:37] + "..." if len(order.market_name) > 40 else order.market_name
                print(f"{market_short:<40} {order.side:<6} {order.size:<10.2f} "
                      f"${order.price:<9.3f} {order.filled_size:<10.2f} {order.status:<10}")
        else:
            print("No open orders found.")
        print(f"\n📈 COPIED TRADES ({len(copied_trades)} total)")
        print("-" * 100)
        if copied_trades:
            print(f"{'Placed At':<12} {'Market':<25} {'Side':<6} {'Size':<10} {'Price':<10} {'USD Size':<10}")
            print("-" * 100)
            for trade in copied_trades[-10:]:
                placed_time = trade.get('placed_at', 'Unknown')[:10] if trade.get('placed_at') else 'Unknown'
                market_short = trade.get('title', 'Unknown')[:22] + "..." if len(trade.get('title', '')) > 25 else trade.get('title', 'Unknown')
                print(f"{placed_time:<12} {market_short:<25} {trade.get('side', ''):<6} "
                      f"{float(trade.get('size', 0)):<10.2f} ${float(trade.get('price', 0)):<9.3f} "
                      f"${float(trade.get('usdcSize', 0)):<9.2f}")
        else:
            print("No copied trades found.")
        print(f"\n🔄 Refreshing in 10 seconds... (Press Ctrl+C to exit)")

def main():
    try:
        tracker = PolymarketTracker()
        print("Initializing Polymarket Copied Trades Tracker...")
        print("This will track only trades successfully copied by place_order.py")
        
        while True:
            try:
                tracker.display_dashboard()
                time.sleep(60)
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Retrying in 60 seconds...")
                time.sleep(60)
                
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        print("Please check your .env file and credentials.")

if __name__ == "__main__":
    main() 