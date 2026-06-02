"""Force initialize accounts and P&L snapshot"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copy_trader import *

print("Initializing 10 wallet accounts with $500 each...")
pnl = get_all_pnl()

print("\nWallet P&L:")
for name, p in sorted(pnl.items(), key=lambda x: x[1]['pnl_pct'], reverse=True):
    sign = '+' if p['pnl'] >= 0 else ''
    print(f"  {name:<18} ${p['total_value']:>8.2f} | {sign}{p['pnl_pct']:.2f}% | {p['category']}")

state = load_state()
state['wallet_pnl'] = pnl
state['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
save_state(state)
print("\nState updated. Dashboard: http://localhost:8766/copy_dashboard.html")
