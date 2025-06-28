import os
import time
from improved_positions import ImprovedPositionTracker

if __name__ == "__main__":
    tracker = ImprovedPositionTracker()
    print("Live Polymarket Portfolio Value (USD)")
    print("Press Ctrl+C to exit.\n")
    while True:
        try:
            print("\n--- DEBUG ---")
            positions = tracker.get_real_positions()
            print(f"Found {len(positions)} open positions.")
            for pos in positions:
                print(f"Market: {pos.market_name[:40]}... | Outcome: {pos.outcome} | Balance: {pos.balance} | Price: {pos.current_price} | USD Value: {pos.usd_value}")
            total_value = sum(pos.usd_value for pos in positions)
            print("--- END DEBUG ---\n")
            time.sleep(10)  # Leave debug output visible for 10 seconds
            # Clear the terminal (works on Windows and Unix)
            os.system('cls' if os.name == 'nt' else 'clear')
            print("Live Polymarket Portfolio Value (USD)")
            print("Press Ctrl+C to exit.\n")
            print(f"Total Value in Open Positions: ${total_value:,.2f}")
            time.sleep(10)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10) 