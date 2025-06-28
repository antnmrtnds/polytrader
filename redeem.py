import os
import requests
from web3 import Web3
from dotenv import load_dotenv
import json

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

# --- USER CONFIGURATION ---
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL")  # e.g., from Infura or Alchemy

# --- CONTRACT CONFIGURATION ---
CONDITIONAL_TOKENS_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
# Load the ABI as a JSON string
CONDITIONAL_TOKENS_ABI = json.loads('''
[{"constant":true,"inputs":[{"name":"owner","type":"address"},{"name":"id","type":"uint256"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"collateralToken","type":"address"},{"name":"parentCollectionId","type":"bytes32"},{"name":"conditionId","type":"bytes32"},{"name":"indexSets","type":"uint256[]"}],"name":"redeemPositions","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"interfaceId","type":"bytes4"}],"name":"supportsInterface","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"","type":"bytes32"},{"name":"","type":"uint256"}],"name":"payoutNumerators","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"ids","type":"uint256[]"},{"name":"values","type":"uint256[]"},{"name":"data","type":"bytes"}],"name":"safeBatchTransferFrom","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"collateralToken","type":"address"},{"name":"collectionId","type":"bytes32"}],"name":"getPositionId","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"pure","type":"function"},{"constant":true,"inputs":[{"name":"owners","type":"address[]"},{"name":"ids","type":"uint256[]"}],"name":"balanceOfBatch","outputs":[{"name":"","type":"uint256[]"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"collateralToken","type":"address"},{"name":"parentCollectionId","type":"bytes32"},{"name":"conditionId","type":"bytes32"},{"name":"partition","type":"uint256[]"},{"name":"amount","type":"uint256"}],"name":"splitPosition","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"oracle","type":"address"},{"name":"questionId","type":"bytes32"},{"name":"outcomeSlotCount","type":"uint256"}],"name":"getConditionId","outputs":[{"name":"","type":"bytes32"}],"payable":false,"stateMutability":"pure","type":"function"},{"constant":true,"inputs":[{"name":"parentCollectionId","type":"bytes32"},{"name":"conditionId","type":"bytes32"},{"name":"indexSet","type":"uint256"}],"name":"getCollectionId","outputs":[{"name":"","type":"bytes32"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"collateralToken","type":"address"},{"name":"parentCollectionId","type":"bytes32"},{"name":"conditionId","type":"bytes32"},{"name":"partition","type":"uint256[]"},{"name":"amount","type":"uint256"}],"name":"mergePositions","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[{"name":"operator","type":"address"},{"name":"approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[{"name":"questionId","type":"bytes32"},{"name":"payouts","type":"uint256[]"}],"name":"reportPayouts","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"conditionId","type":"bytes32"}],"name":"getOutcomeSlotCount","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"oracle","type":"address"},{"name":"questionId","type":"bytes32"},{"name":"outcomeSlotCount","type":"uint256"}],"name":"prepareCondition","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"","type":"bytes32"}],"name":"payoutDenominator","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[{"name":"owner","type":"address"},{"name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"id","type":"uint256"},{"name":"value","type":"uint256"},{"name":"data","type":"bytes"}],"name":"safeTransferFrom","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"anonymous":false,"inputs":[{"indexed":true,"name":"conditionId","type":"bytes32"},{"indexed":true,"name":"oracle","type":"address"},{"indexed":true,"name":"questionId","type":"bytes32"},{"indexed":false,"name":"outcomeSlotCount","type":"uint256"}],"name":"ConditionPreparation","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"conditionId","type":"bytes32"},{"indexed":true,"name":"oracle","type":"address"},{"indexed":true,"name":"questionId","type":"bytes32"},{"indexed":false,"name":"outcomeSlotCount","type":"uint256"},{"indexed":false,"name":"payoutNumerators","type":"uint256[]"}],"name":"ConditionResolution","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"stakeholder","type":"address"},{"indexed":false,"name":"collateralToken","type":"address"},{"indexed":true,"name":"parentCollectionId","type":"bytes32"},{"indexed":true,"name":"conditionId","type":"bytes32"},{"indexed":false,"name":"partition","type":"uint256[]"},{"indexed":false,"name":"amount","type":"uint256"}],"name":"PositionSplit","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"stakeholder","type":"address"},{"indexed":false,"name":"collateralToken","type":"address"},{"indexed":true,"name":"parentCollectionId","type":"bytes32"},{"indexed":true,"name":"conditionId","type":"bytes32"},{"indexed":false,"name":"partition","type":"uint256[]"},{"indexed":false,"name":"amount","type":"uint256"}],"name":"PositionsMerge","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"redeemer","type":"address"},{"indexed":true,"name":"collateralToken","type":"address"},{"indexed":true,"name":"parentCollectionId","type":"bytes32"},{"indexed":false,"name":"conditionId","type":"bytes32"},{"indexed":false,"name":"indexSets","type":"uint256[]"},{"indexed":false,"name":"payout","type":"uint256"}],"name":"PayoutRedemption","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"operator","type":"address"},{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"id","type":"uint256"},{"indexed":false,"name":"value","type":"uint256"}],"name":"TransferSingle","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"operator","type":"address"},{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"ids","type":"uint256[]"},{"indexed":false,"name":"values","type":"uint256[]"}],"name":"TransferBatch","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"owner","type":"address"},{"indexed":true,"name":"operator","type":"address"},{"indexed":false,"name":"approved","type":"bool"}],"name":"ApprovalForAll","type":"event"},{"anonymous":false,"inputs":[{"indexed":false,"name":"value","type":"string"},{"indexed":true,"name":"id","type":"uint256"}],"name":"URI","type":"event"}]
''')

# --- SETUP ---
w3 = Web3(Web3.HTTPProvider(RPC_URL))
ct_contract = w3.eth.contract(address=CONDITIONAL_TOKENS_ADDRESS, abi=CONDITIONAL_TOKENS_ABI)

# --- 1. Get all positions ---
params = {
    "user": WALLET_ADDRESS,
    "limit": 100,
    "sortBy": "CURRENT",
    "sortDirection": "DESC"
}
positions_url = "https://data-api.polymarket.com/positions"
response = requests.get(positions_url, params=params)
print("Status code:", response.status_code)
print("Response text:", response.text)
try:
    positions = response.json() if response.status_code == 200 else []
except Exception as e:
    print("Failed to parse JSON:", e)
    positions = []

# --- Save parsed positions to a new JSON file ---
with open("positions_parsed.json", "w", encoding="utf-8") as f:
    json.dump(positions, f, indent=2)

# --- Log all cashPnls and the total PnL ---
pnls = []
for pos in positions:
    pnl = pos.get('cashPnl')
    title = pos.get('title', 'Unknown')
    print(f"PnL for '{title}': {pnl}")
    if pnl is not None:
        try:
            pnls.append(float(pnl))
        except Exception:
            pass

total_pnl = sum(pnls)
print(f"Total PnL: {total_pnl}")

# --- 2. Filter redeemable positions ---
redeemable = [
    pos for pos in positions
    if pos.get('redeemable') and float(pos.get('size', 0)) > 0
]

if not redeemable:
    print("No redeemable positions found.")
    exit(0)

# --- 3. Redeem each position ---
for pos in redeemable:
    try:
        condition_id = pos['conditionId']
        outcome_index = pos['outcomeIndex']
        parent_collection_id = "0x" + "0"*64
        index_sets = [1 << int(outcome_index)]
        print(f"Redeeming: conditionId={condition_id}, outcomeIndex={outcome_index}, indexSets={index_sets}")
        tx = ct_contract.functions.redeemPositions(
            USDC_ADDRESS,
            parent_collection_id,
            condition_id,
            index_sets
        ).build_transaction({
            'from': WALLET_ADDRESS,
            'nonce': w3.eth.get_transaction_count(WALLET_ADDRESS),
            'gas': 200000,
            'gasPrice': w3.to_wei('50', 'gwei')
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"✅ Redeemed position in market {condition_id}, tx hash: {tx_hash.hex()}")
    except Exception as e:
        print(f"❌ Error redeeming position in market {pos.get('conditionId')}: {e}")

print("All redeemable positions processed.")

# --- .env file example ---
# WALLET_ADDRESS=0x...
# PRIVATE_KEY=...
# RPC_URL=https://polygon-mainnet.infura.io/v3/your_project_id

# --- Print total PnL from redeemed positions ---
total_redeemed_pnl = 0
for pos in redeemable:
    pnl = pos.get('cashPnl', 0)
    print(f"PnL for redeemed '{pos.get('title', pos.get('conditionId'))}': {pnl}")
    total_redeemed_pnl += pnl
print(f"Total PnL from redeemed positions: {total_redeemed_pnl}")

# --- Print total cash in all unredeemable positions ---
unredeemable = [pos for pos in positions if not pos.get('redeemable')]
total_unredeemable_cash = sum(pos.get('currentValue', 0) for pos in unredeemable)
print(f"Total cash in all unredeemable positions: {total_unredeemable_cash}")