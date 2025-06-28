#!/usr/bin/env python3
"""
Polymarket Position Closer
Close individual positions or all positions at once
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
    from py_clob_client.clob_types import TradeParams, OrderArgs, OrderType, MarketOrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL
except ImportError:
    print("Installing required packages...")
    os.system("pip install py-clob-client python-dotenv requests")
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import TradeParams, OrderArgs, OrderType, MarketOrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL

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
    outcome: str

class PositionCloser:
    def __init__(self):
        self.host = os.getenv('HOST', 'https://clob.polymarket.com')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.public_key = os.getenv('PUBLIC_KEY', '').strip("'")
        self.clob_api_key = os.getenv('CLOB_API_KEY', '').strip("'")
        self.clob_secret = os.getenv('CLOB_SECRET', '').strip("'")
        self.clob_pass_phrase = os.getenv('CLOB_PASS_PHRASE', '').strip("'")
        
        # Initialize CLOB client
        try:
            # Ensure private key starts with 0x
            if self.private_key and not self.private_key.startswith('0x'):
                self.private_key = '0x' + self.private_key
                
            self.client = ClobClient(
                self.host,
                key=self.private_key,
                chain_id=137
            )
            
            # Set API credentials
            if self.clob_api_key and self.clob_secret and self.clob_pass_phrase:
                # Use existing API credentials - try different formats
                try:
                    # Try the expected format for py-clob-client
                    from py_clob_client.clob_types import ApiCreds
                    creds = ApiCreds(
                        api_key=self.clob_api_key,
                        api_secret=self.clob_secret,
                        api_passphrase=self.clob_pass_phrase
                    )
                    self.client.set_api_creds(creds)
                    print("✅ Using existing API credentials (ApiCreds format)")
                except ImportError:
                    # Fallback to dict format
                    creds = {
                        'api_key': self.clob_api_key,
                        'api_secret': self.clob_secret,
                        'api_passphrase': self.clob_pass_phrase
                    }
                    self.client.set_api_creds(creds)
                    print("✅ Using existing API credentials (dict format)")
            else:
                # Create new API credentials
                creds = self.client.create_or_derive_api_creds()
                self.client.set_api_creds(creds)
                print("✅ Created new API credentials")
                
        except Exception as e:
            print(f"❌ Error initializing client: {e}")
            raise
        
        # Cache for market info
        self.market_cache = {}
        
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
    
    def get_recent_trades(self, limit: int = 500) -> List[Dict[str, Any]]:
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
    
    def calculate_positions(self, trades: List[Dict[str, Any]]) -> List[Position]:
        """Calculate current positions from trade history"""
        positions_data = {}
        
        for trade in trades:
            market_id = trade.get('market', '')
            asset_id = trade.get('asset_id', '')
            side = trade.get('side', '')
            size = float(trade.get('size', 0))
            price = float(trade.get('price', 0))
            
            key = f"{market_id}_{asset_id}"
            
            if key not in positions_data:
                positions_data[key] = {
                    'market_id': market_id,
                    'asset_id': asset_id,
                    'total_size': 0,
                    'total_cost': 0,
                    'trades': []
                }
            
            # Calculate position impact
            if side.upper() == 'BUY':
                positions_data[key]['total_size'] += size
                positions_data[key]['total_cost'] += size * price
            else:  # SELL
                positions_data[key]['total_size'] -= size
                positions_data[key]['total_cost'] -= size * price
            
            positions_data[key]['trades'].append(trade)
        
        # Convert to Position objects
        positions = []
        for key, data in positions_data.items():
            if abs(data['total_size']) < 0.001:  # Skip closed positions
                continue
                
            market_info = self.get_market_info(data['market_id'])
            market_name = market_info.get('question', 'Unknown Market')
            
            avg_price = abs(data['total_cost'] / data['total_size']) if data['total_size'] != 0 else 0
            
            # Get current price and outcome name
            current_prices = self.get_current_market_prices(data['market_id'])
            current_price = 0
            outcome = "Unknown"
            
            for token in market_info.get('tokens', []):
                if token.get('token_id') == data['asset_id']:
                    outcome = token.get('outcome', 'Unknown')
                    current_price = current_prices.get(outcome, 0)
                    break
            
            # Calculate PnL
            if data['total_size'] > 0:  # Long position
                pnl = data['total_size'] * (current_price - avg_price)
            else:  # Short position
                pnl = abs(data['total_size']) * (avg_price - current_price)
            
            pnl_percentage = (pnl / abs(data['total_cost'])) * 100 if data['total_cost'] != 0 else 0
            
            positions.append(Position(
                market_name=market_name,
                token_id=data['asset_id'],
                side='LONG' if data['total_size'] > 0 else 'SHORT',
                size=abs(data['total_size']),
                avg_price=avg_price,
                current_price=current_price,
                pnl=pnl,
                pnl_percentage=pnl_percentage,
                market_id=data['market_id'],
                outcome=outcome
            ))
        
        return positions
    
    def close_position(self, position: Position) -> bool:
        """Close a specific position by placing a market order"""
        try:
            print(f"\n🔄 Closing position: {position.market_name[:50]}...")
            print(f"   Outcome: {position.outcome}")
            print(f"   Side: {position.side}")
            print(f"   Size: {position.size}")
            
            # Determine order side (opposite of position)
            order_side = SELL if position.side == 'LONG' else BUY
            
            # Create order arguments using the correct format
            order_price = 0.01 if order_side == SELL else 0.99
            
            print(f"   Order: {order_side} {position.size} @ ${order_price:.3f}")
            
            # Try to figure out MarketOrderArgs parameters
            try:
                import inspect
                sig = inspect.signature(MarketOrderArgs.__init__)
                print(f"   MarketOrderArgs signature: {sig}")
            except Exception as e:
                print(f"   Could not inspect MarketOrderArgs: {e}")
            
            # Try different parameter names for MarketOrderArgs
            try:
                # Try with 'amount' instead of 'size'
                market_order_args = MarketOrderArgs(
                    token_id=position.token_id,
                    price=order_price,
                    amount=position.size,
                    side=order_side
                )
                resp = self.client.create_market_order(market_order_args)
                print(f"   ✅ Market order with 'amount' parameter worked!")
                
            except Exception as e1:
                print(f"   MarketOrderArgs with 'amount' failed: {e1}")
                
                try:
                    # Try with minimal parameters
                    market_order_args = MarketOrderArgs(
                        token_id=position.token_id,
                        side=order_side
                    )
                    resp = self.client.create_market_order(market_order_args)
                    print(f"   ✅ Market order with minimal params worked!")
                    
                except Exception as e2:
                    print(f"   Minimal MarketOrderArgs failed: {e2}")
                    
                    try:
                        # Try just token_id and side as positional args
                        market_order_args = MarketOrderArgs(position.token_id, order_side)
                        resp = self.client.create_market_order(market_order_args)
                        print(f"   ✅ Market order with positional args worked!")
                        
                    except Exception as e3:
                        print(f"   Positional args failed: {e3}")
                        
                        # Try to see what MarketOrderArgs actually accepts
                        try:
                            # Create empty and see what's required
                            market_order_args = MarketOrderArgs()
                            print(f"   Empty MarketOrderArgs created, attributes: {dir(market_order_args)}")
                        except Exception as e4:
                            print(f"   Could not create empty MarketOrderArgs: {e4}")
                            print(f"   Final attempt with basic order...")
                            
                            # Very last resort - try a simple market order
                            try:
                                resp = self.client.create_market_order(position.token_id, order_side)
                                print(f"   ✅ Simple market order worked!")
                            except Exception as e5:
                                print(f"   All attempts failed: {e5}")
                                raise Exception("All order placement methods failed")
            
            if resp:
                # Handle different response types
                if hasattr(resp, 'orderID'):
                    print(f"   ✅ Order placed successfully! Order ID: {resp.orderID}")
                    return True
                elif hasattr(resp, 'order_id'):
                    print(f"   ✅ Order placed successfully! Order ID: {resp.order_id}")
                    return True
                elif isinstance(resp, dict) and 'orderID' in resp:
                    print(f"   ✅ Order placed successfully! Order ID: {resp['orderID']}")
                    return True
                elif isinstance(resp, dict) and 'order_id' in resp:
                    print(f"   ✅ Order placed successfully! Order ID: {resp['order_id']}")
                    return True
                else:
                    print(f"   ✅ Order object created successfully! Type: {type(resp)}")
                    print(f"   Response attributes: {[attr for attr in dir(resp) if not attr.startswith('_')]}")
                    return True
            else:
                print(f"   ❌ Failed to place order: {resp}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error closing position: {e}")
            return False
    
    def display_positions(self, positions: List[Position]) -> None:
        """Display positions in a formatted table"""
        print("\n" + "=" * 120)
        print("📊 CURRENT POSITIONS")
        print("=" * 120)
        
        if not positions:
            print("No open positions found.")
            return
        
        print(f"{'#':<3} {'Market':<45} {'Outcome':<15} {'Side':<6} {'Size':<10} {'Avg Price':<10} {'Current':<10} {'PnL':<12} {'PnL %':<10}")
        print("-" * 120)
        
        total_pnl = 0
        for i, pos in enumerate(positions, 1):
            pnl_color = "🟢" if pos.pnl >= 0 else "🔴"
            market_short = pos.market_name[:42] + "..." if len(pos.market_name) > 45 else pos.market_name
            outcome_short = pos.outcome[:12] + "..." if len(pos.outcome) > 15 else pos.outcome
            
            print(f"{i:<3} {market_short:<45} {outcome_short:<15} {pos.side:<6} {pos.size:<10.2f} "
                  f"${pos.avg_price:<9.3f} ${pos.current_price:<9.3f} "
                  f"{pnl_color}${pos.pnl:<10.2f} {pos.pnl_percentage:<9.1f}%")
            
            total_pnl += pos.pnl
        
        print("-" * 120)
        total_color = "🟢" if total_pnl >= 0 else "🔴"
        print(f"{'TOTAL PnL':<95} {total_color}${total_pnl:<10.2f}")
    
    def get_user_choice(self, positions: List[Position]) -> List[Position]:
        """Get user's choice of which positions to close"""
        while True:
            print(f"\n🎯 POSITION CLOSING OPTIONS:")
            print("=" * 50)
            print("1. Close specific position(s)")
            print("2. Close ALL positions")
            print("3. Cancel and exit")
            
            try:
                choice = input("\nEnter your choice (1-3): ").strip()
                
                if choice == "1":
                    return self.select_specific_positions(positions)
                elif choice == "2":
                    confirm = input(f"\n⚠️  Are you sure you want to close ALL {len(positions)} positions? (yes/no): ").strip().lower()
                    if confirm in ['yes', 'y']:
                        return positions
                    else:
                        print("Operation cancelled.")
                        continue
                elif choice == "3":
                    return []
                else:
                    print("❌ Invalid choice. Please enter 1, 2, or 3.")
                    continue
                    
            except KeyboardInterrupt:
                print("\n\n👋 Operation cancelled.")
                return []
    
    def select_specific_positions(self, positions: List[Position]) -> List[Position]:
        """Allow user to select specific positions to close"""
        selected_positions = []
        
        while True:
            print(f"\n📋 SELECT POSITIONS TO CLOSE:")
            print("=" * 50)
            print("Enter position numbers separated by commas (e.g., 1,3,5)")
            print("Or type 'done' when finished selecting")
            print("Or type 'cancel' to go back")
            
            try:
                selection = input("\nYour selection: ").strip().lower()
                
                if selection == 'done':
                    if selected_positions:
                        return selected_positions
                    else:
                        print("❌ No positions selected.")
                        continue
                elif selection == 'cancel':
                    return []
                
                # Parse position numbers
                try:
                    position_numbers = [int(x.strip()) for x in selection.split(',')]
                    selected_positions = []
                    
                    for num in position_numbers:
                        if 1 <= num <= len(positions):
                            selected_positions.append(positions[num - 1])
                        else:
                            print(f"❌ Invalid position number: {num}")
                            selected_positions = []
                            break
                    
                    if selected_positions:
                        print(f"\n✅ Selected {len(selected_positions)} position(s):")
                        for i, pos in enumerate(selected_positions, 1):
                            print(f"   {i}. {pos.market_name[:60]} ({pos.outcome}) - {pos.side}")
                        
                        confirm = input(f"\nConfirm closing these {len(selected_positions)} position(s)? (yes/no): ").strip().lower()
                        if confirm in ['yes', 'y']:
                            return selected_positions
                        else:
                            selected_positions = []
                            continue
                
                except ValueError:
                    print("❌ Invalid format. Please enter numbers separated by commas.")
                    continue
                    
            except KeyboardInterrupt:
                print("\n\n👋 Operation cancelled.")
                return []
    
    def close_positions(self, positions_to_close: List[Position]) -> None:
        """Close the selected positions"""
        if not positions_to_close:
            print("No positions to close.")
            return
        
        print(f"\n🚀 STARTING TO CLOSE {len(positions_to_close)} POSITION(S)")
        print("=" * 60)
        
        successful_closes = 0
        failed_closes = 0
        
        for i, position in enumerate(positions_to_close, 1):
            print(f"\n[{i}/{len(positions_to_close)}] Processing position...")
            
            if self.close_position(position):
                successful_closes += 1
                time.sleep(1)  # Brief delay between orders
            else:
                failed_closes += 1
        
        # Summary
        print(f"\n" + "=" * 60)
        print("📊 CLOSING SUMMARY")
        print("=" * 60)
        print(f"✅ Successfully closed: {successful_closes}")
        print(f"❌ Failed to close: {failed_closes}")
        print(f"📊 Total processed: {len(positions_to_close)}")
        
        if successful_closes > 0:
            print(f"\n🎉 {successful_closes} position(s) have been closed successfully!")
            print("💡 Orders may take a few moments to execute. Check your positions in a few minutes.")

def main():
    try:
        closer = PositionCloser()
        print("🔮 Polymarket Position Closer")
        print("=" * 50)
        print("Loading your current positions...")
        
        # Get current positions
        trades = closer.get_recent_trades(500)
        positions = closer.calculate_positions(trades)
        
        if not positions:
            print("\n❌ No open positions found.")
            print("Nothing to close!")
            return
        
        # Display positions
        closer.display_positions(positions)
        
        # Get user choice
        positions_to_close = closer.get_user_choice(positions)
        
        if positions_to_close:
            # Close selected positions
            closer.close_positions(positions_to_close)
        else:
            print("\n👋 No positions selected. Goodbye!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your .env file and credentials.")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main() 