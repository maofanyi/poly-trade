"""Backtest: simulate copy-trading a wallet from historical Data API trades."""
import json
import time
import urllib.request
from datetime import datetime
from config import INITIAL_CAPITAL

DATA_API = "https://data-api.polymarket.com"


def _fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def run_backtest(address: str, days: int = 30) -> dict:
    """Fetch wallet's recent trades and simulate copy-trading P&L."""
    trades = []
    try:
        for offset in [0, 100]:
            batch = _fetch(f"{DATA_API}/trades?user={address}&limit=100&offset={offset}")
            if not batch:
                break
            trades.extend(batch)
            if len(batch) < 100:
                break
            time.sleep(0.5)
    except Exception as e:
        return {"error": str(e), "trades_analyzed": 0}

    if not trades:
        return {"error": "No trades found", "trades_analyzed": 0}

    cutoff = int(time.time()) - days * 86400
    recent = [t for t in trades if int(t.get('timestamp', 0)) >= cutoff]

    if not recent:
        return {"trades_analyzed": 0, "message": f"No trades in last {days} days", "total_trades_found": len(trades)}

    capital = INITIAL_CAPITAL
    cash = capital
    positions = {}
    trade_log = []
    total_pnl = 0.0

    for t in reversed(recent):
        side = t.get('side', 'BUY').upper()
        slug = t.get('slug', '')
        outcome = t.get('outcome', 'Yes')
        price = float(t.get('price', 0))
        size = float(t.get('size', 0))
        ts = t.get('timestamp', '')

        whale_notional = size * price
        sim_usd = round(min(max(whale_notional * 0.02, 1.0), capital * 0.05), 2)
        sim_usd = min(sim_usd, cash)

        if sim_usd < 1.0:
            continue

        pos_key = f"{slug}|{outcome}"

        if side == 'BUY':
            shares = sim_usd / price if price > 0 else 0
            cash -= sim_usd
            if pos_key in positions:
                old = positions[pos_key]
                total_shares = old['shares'] + shares
                avg_cost = (old['cost_basis'] * old['shares'] + price * shares) / total_shares if total_shares > 0 else price
                positions[pos_key] = {'shares': total_shares, 'cost_basis': avg_cost}
            else:
                positions[pos_key] = {'shares': shares, 'cost_basis': price}
            trade_log.append({
                'side': 'BUY', 'price': price, 'sim_usd': round(sim_usd, 2),
                'shares': round(shares, 2), 'slug': slug[:50], 'timestamp': ts
            })
        elif side == 'SELL' and pos_key in positions:
            pos = positions[pos_key]
            sell_value = pos['shares'] * price
            pnl = round((price - pos['cost_basis']) * pos['shares'], 2)
            cash += sell_value
            total_pnl += pnl
            trade_log.append({
                'side': 'SELL', 'price': price, 'pnl': pnl,
                'shares': round(pos['shares'], 2), 'slug': slug[:50], 'timestamp': ts
            })
            del positions[pos_key]

    unrealized = sum(pos['shares'] * pos['cost_basis'] for pos in positions.values())
    total_value = round(cash + unrealized, 2)
    final_pnl = round(total_value - capital, 2)

    return {
        "trades_analyzed": len(trade_log),
        "total_trades_found": len(trades),
        "days": days,
        "initial_capital": capital,
        "final_value": total_value,
        "pnl": final_pnl,
        "pnl_pct": round(final_pnl / capital * 100, 2),
        "open_positions": len(positions),
        "trade_log": trade_log[-50:]
    }
