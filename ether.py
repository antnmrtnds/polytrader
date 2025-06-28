import requests
import json
from typing import Dict, List, Optional

class PolymarketEtherscanAnalyzer:
    def __init__(self, etherscan_api_key: str):
        self.etherscan_api_key = "IMTRI7NK8JNTA4IXXUZX8RF3R3BHTIPFF2"
        self.etherscan_base_url = "https://api.etherscan.io/v2/api"
        self.polymarket_data_api = "https://data-api.polymarket.com"
        self.polygon_chain_id = 137  # Polygon mainnet chain ID
        
    def get_wallet_balance(self, wallet_address: str) -> Dict:
        """Get MATIC balance using Etherscan v2 API"""
        
        balance_params = {
            "chainid": self.polygon_chain_id,
            "module": "account",
            "action": "balance",
            "address": "0x80cd8310AA624521e9e1B2B53B568cAfb0eF0273",
            "tag": "latest",
            "apikey": self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_base_url, params=balance_params)
        balance_data = response.json()
        
        # Convert from wei to MATIC
        matic_balance = int(balance_data["result"]) / 10**18 if balance_data["status"] == "1" else 0
        
        return {
            "matic_balance": matic_balance,
            "wallet_address": wallet_address
        }
    
    def get_usdc_balance(self, wallet_address: str) -> float:
        """Get USDC balance using Etherscan v2 API"""
        
        # USDC contract address on Polygon
        usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        balance_params = {
            "chainid": self.polygon_chain_id,
            "module": "account", 
            "action": "tokenbalance",
            "contractaddress": usdc_contract,
            "address": wallet_address,
            "tag": "latest",
            "apikey": self.etherscan_api_key
        }
        
        response = requests.get(self.etherscan_base_url, params=balance_params)
        balance_data = response.json()
        
        # Convert from smallest unit to USDC (6 decimals)
        usdc_balance = int(balance_data["result"]) / 10**6 if balance_data["status"] == "1" else 0
        
        return usdc_balance
    
    def get_polymarket_positions(self, user_address: str, limit: int = 100) -> List[Dict]:
        """Get user positions from Polymarket API"""
        
        positions_url = f"{self.polymarket_data_api}/positions"
        params = {
            "user": user_address,
            "limit": limit,
            "sortBy": "CURRENT",
            "sortDirection": "DESC"
        }
        
        response = requests.get(positions_url, params=params)
        return response.json() if response.status_code == 200 else []
    
    def get_polymarket_trades(self, user_address: str, limit: int = 100) -> List[Dict]:
        """Get user trades from Polymarket API"""
        
        trades_url = f"{self.polymarket_data_api}/trades"
        params = {
            "user": user_address,
            "limit": limit,
            "offset": 0
        }
        
        response = requests.get(trades_url, params=params)
        return response.json() if response.status_code == 200 else []
    
    def analyze_user_portfolio(self, user_address: str) -> Dict:
        """Complete analysis combining Etherscan and Polymarket data"""
        
        # Get wallet balances
        wallet_data = self.get_wallet_balance(user_address)
        usdc_balance = self.get_usdc_balance(user_address)
        
        # Get Polymarket data
        positions = self.get_polymarket_positions(user_address)
        trades = self.get_polymarket_trades(user_address)
        
        # Calculate portfolio metrics
        total_position_value = sum(pos.get("currentValue", 0) for pos in positions)
        total_pnl = sum(pos.get("cashPnl", 0) for pos in positions)
        realized_pnl = sum(pos.get("realizedPnl", 0) for pos in positions)
        
        return {
            "wallet_address": user_address,
            "balances": {
                "matic": wallet_data["matic_balance"],
                "usdc": usdc_balance
            },
            "polymarket_portfolio": {
                "total_positions": len(positions),
                "total_position_value": total_position_value,
                "total_unrealized_pnl": total_pnl,
                "total_realized_pnl": realized_pnl,
                "total_trades": len(trades)
            },
            "positions": positions[:5],  # Top 5 positions
            "recent_trades": trades[:5]   # Recent 5 trades
        }

if __name__ == "__main__":
    analyzer = PolymarketEtherscanAnalyzer(etherscan_api_key="IMTRI7NK8JNTA4IXXUZX8RF3R3BHTIPFF2")
    user_address = "0x80cd8310AA624521e9e1B2B53B568cAfb0eF0273"  # Replace with desired address
    result = analyzer.analyze_user_portfolio(user_address)
    print(json.dumps(result, indent=2))
    with open("ether_log.json", "w") as f:
        json.dump(result, f, indent=2)