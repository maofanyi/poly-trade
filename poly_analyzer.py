"""
Poly_data integration: Analyze wallet performance from historical trades.
Ranks wallets by copy-trading suitability and exports to monitoring config.

Usage:
  python poly_analyzer.py                    # Analyze all wallets in trades.csv
  python poly_analyzer.py --wallet 0xABCD... # Analyze specific wallet
  python poly_analyzer.py --top 20           # Export top 20 to wallets_active.json
"""
import sys, os, json
from collections import defaultdict
from datetime import datetime, timezone

POLY_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poly_data")
TRADES_CSV = os.path.join(POLY_DATA_DIR, "processed", "trades.csv")
MARKETS_CSV = os.path.join(POLY_DATA_DIR, "data", "markets.csv")
WALLETS_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallets_active.json")

def analyze_trades(trades_csv):
    """Parse trades.csv and compute per-wallet metrics."""
    if not os.path.exists(trades_csv):
        print(f"ERROR: {trades_csv} not found. Run poly_data pipeline first:")
        print(f"  cd {POLY_DATA_DIR} && uv run python update.py")
        return {}

    import csv
    wallets = defaultdict(lambda: {
        "buys": 0, "sells": 0, "buy_volume": 0.0, "sell_volume": 0.0,
        "trades": [], "markets": set(), "first_seen": None, "last_seen": None,
        "total_pnl": 0.0, "win_count": 0, "loss_count": 0
    })

    print(f"Reading {trades_csv}...")
    with open(trades_csv, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i % 500000 == 0 and i > 0:
                print(f"  {i:,} rows... ({len(wallets):,} wallets)")

            maker = row.get('maker', '')
            direction = row.get('maker_direction', '')
            price = float(row.get('price', 0))
            usd = float(row.get('usd_amount', 0))
            ts_str = row.get('timestamp', '')
            market_id = row.get('market_id', '')

            w = wallets[maker]
            if direction == 'BUY':
                w['buys'] += 1
                w['buy_volume'] += usd
            else:
                w['sells'] += 1
                w['sell_volume'] += usd

            w['trades'].append({"direction": direction, "price": price, "usd": usd, "time": ts_str})
            if market_id: w['markets'].add(market_id)
            if not w['first_seen']: w['first_seen'] = ts_str
            w['last_seen'] = ts_str

    print(f"  Done. {i+1:,} trades, {len(wallets):,} unique wallets")

    # Compute derived metrics
    results = {}
    for addr, w in wallets.items():
        total_trades = w['buys'] + w['sells']
        if total_trades < 10: continue  # skip noise

        total_vol = w['buy_volume'] + w['sell_volume']
        buy_ratio = w['buys'] / total_trades if total_trades > 0 else 0
        markets_count = len(w['markets'])
        avg_trade_size = total_vol / total_trades if total_trades > 0 else 0

        # Score: high volume + diverse markets + moderate frequency = better to copy
        # High frequency bots (market makers) get lower scores
        freq_penalty = min(1.0, 100 / total_trades) if total_trades > 100 else 1.0
        diversity_bonus = min(markets_count / 10, 2.0)
        size_score = min(avg_trade_size / 100, 5.0)

        copy_score = (total_vol * 0.0001 + diversity_bonus * 50 + size_score * 10) * freq_penalty

        results[addr] = {
            "address": addr,
            "total_trades": total_trades,
            "total_volume": round(total_vol, 2),
            "markets_traded": markets_count,
            "avg_trade_size": round(avg_trade_size, 2),
            "buy_ratio": round(buy_ratio, 3),
            "first_seen": w['first_seen'],
            "last_seen": w['last_seen'],
            "copy_score": round(copy_score, 2),
        }

    # Sort by copy_score descending
    return dict(sorted(results.items(), key=lambda x: x[1]['copy_score'], reverse=True))

def get_market_categories(markets_csv):
    """Map market IDs to categories (sports, politics, crypto, etc)."""
    if not os.path.exists(markets_csv):
        return {}
    import csv
    categories = {}
    with open(markets_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Try to extract category from nested JSON
            mid = row.get('id', '')
            # Category is embedded in events JSON or tags
            categories[mid] = "unknown"
    return categories

def export_top(wallets, top_n=20):
    """Export top N wallets to monitoring config format."""
    config = []
    for i, (addr, data) in enumerate(list(wallets.items())[:top_n]):
        # Generate a readable name from address
        short_name = f"Poly{i+1:02d}"
        config.append({
            "addr": addr,
            "name": short_name,
            "cat": "PolyData",
            "note": f"T={data['total_trades']} V=${data['total_volume']:.0f} Score={data['copy_score']}"
        })

    with open(WALLETS_OUT, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"\nExported top {top_n} wallets to {WALLETS_OUT}")
    for w in config[:10]:
        print(f"  {w['name']}: {w['addr'][:10]}... {w['note']}")
    return config

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Poly_data wallet analyzer")
    ap.add_argument("--wallet", help="Analyze specific wallet address")
    ap.add_argument("--top", type=int, default=0, help="Export top N wallets to monitoring config")
    ap.add_argument("--min-trades", type=int, default=10, help="Minimum trades for inclusion")
    args = ap.parse_args()

    wallets = analyze_trades(TRADES_CSV)
    if not wallets:
        return

    print(f"\n{'='*70}")
    print(f"  Wallet Rankings (by copy-trading suitability)")
    print(f"{'='*70}")
    print(f"  {'Rank':<5} {'Address':<20} {'Trades':<8} {'Volume':<12} {'Markets':<8} {'Score':<8}")
    print(f"  {'-'*5} {'-'*20} {'-'*8} {'-'*12} {'-'*8} {'-'*8}")

    for i, (addr, data) in enumerate(list(wallets.items())[:50]):
        if data['total_trades'] < args.min_trades: continue
        addr_short = addr[:8] + ".." + addr[-6:]
        print(f"  {i+1:<5} {addr_short:<20} {data['total_trades']:<8} ${data['total_volume']:<11,.0f} {data['markets_traded']:<8} {data['copy_score']:<8.1f}")

    if args.wallet:
        w = wallets.get(args.wallet)
        if w:
            print(f"\n  Detailed analysis for {args.wallet}:")
            for k, v in w.items():
                print(f"    {k}: {v}")
        else:
            print(f"\n  Wallet {args.wallet} not found in data")

    if args.top > 0:
        export_top(wallets, args.top)

if __name__ == '__main__':
    main()
