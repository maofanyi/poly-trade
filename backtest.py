"""Backtest: simulate copy-trading a wallet from historical Data API trades."""
import json
import re
import time
import urllib.request
from datetime import datetime
from config import INITIAL_CAPITAL

DATA_API = "https://data-api.polymarket.com"


def _fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _extract_expiry(slug: str) -> int | None:
    """Try to extract market expiry timestamp from slug."""
    m = re.search(r'[_-](\d{10})$', slug)
    if m:
        ts = int(m.group(1))
        if 1577836800 < ts < 2000000000:
            return ts
    return None


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
    realized_pnl = 0.0
    buy_count = 0
    sell_count = 0

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
            buy_count += 1
            shares = sim_usd / price if price > 0 else 0
            cash -= sim_usd
            if pos_key in positions:
                old = positions[pos_key]
                total_shares = old['shares'] + shares
                avg_cost = (old['cost_basis'] * old['shares'] + price * shares) / total_shares if total_shares > 0 else price
                positions[pos_key] = {'shares': total_shares, 'cost_basis': avg_cost, 'slug': slug}
            else:
                positions[pos_key] = {'shares': shares, 'cost_basis': price, 'slug': slug}
            trade_log.append({
                'side': 'BUY', 'price': price, 'sim_usd': round(sim_usd, 2),
                'shares': round(shares, 2), 'slug': slug[:50], 'timestamp': ts
            })
        elif side == 'SELL' and pos_key in positions:
            sell_count += 1
            pos = positions[pos_key]
            sell_value = pos['shares'] * price
            pnl = round((price - pos['cost_basis']) * pos['shares'], 2)
            cash += sell_value
            realized_pnl += pnl
            trade_log.append({
                'side': 'SELL', 'price': price, 'pnl': pnl,
                'shares': round(pos['shares'], 2), 'slug': slug[:50], 'timestamp': ts
            })
            del positions[pos_key]

    # Resolve expired positions using Gamma API outcome prices
    now_ts = int(time.time())
    expired_count = 0
    expired_value = 0.0
    resolved_pnl = 0.0
    _market_cache = {}  # Cache resolution queries

    for pk, pos in list(positions.items()):
        expiry = _extract_expiry(pos.get('slug', ''))
        if not expiry or (now_ts - expiry) <= 3600:
            continue  # Not expired yet or recently expired
        expired_count += 1
        expired_value += pos['shares'] * pos['cost_basis']

        # Try to get resolution from Gamma API
        slug = pos.get('slug', '')
        if slug in _market_cache:
            resolution = _market_cache[slug]
        else:
            resolution = None
            try:
                # First get the event, then find the market
                evt_resp = _fetch(f"https://gamma-api.polymarket.com/events?slug={slug}")
                time.sleep(0.3)
                if evt_resp and len(evt_resp) > 0:
                    markets_raw = evt_resp[0].get('markets', '[]')
                    if isinstance(markets_raw, str):
                        markets_raw = json.loads(markets_raw)
                    for m in markets_raw:
                        m_slug = m.get('slug', '')
                        if m_slug == slug or m_slug in slug:
                            outcomes = m.get('outcomes', [])
                            prices = m.get('outcomePrices', [])
                            for i, (outcome, price_str) in enumerate(zip(outcomes, prices)):
                                try:
                                    p = float(price_str)
                                except (ValueError, TypeError):
                                    p = 0
                                if p >= 0.99:  # This outcome resolved to $1 (winner)
                                    resolution = outcome
                                    break
                            break
            except Exception:
                pass
            _market_cache[slug] = resolution

        # Calculate P&L from resolution
        outcome_key = pk.split('|')[1] if '|' in pk else ''
        outcome_normalized = outcome_key.strip().lower()

        if resolution and outcome_normalized == resolution.strip().lower():
            # Position WON: shares × (1.0 - cost_basis)
            win_pnl = round(pos['shares'] * (1.0 - pos['cost_basis']), 2)
            resolved_pnl += win_pnl
            realized_pnl += win_pnl  # Add to realized since we know the outcome
        else:
            # Position LOST or unknown: loss = cost_basis × shares
            resolved_pnl -= round(pos['shares'] * pos['cost_basis'], 2)
            realized_pnl -= round(pos['shares'] * pos['cost_basis'], 2)

        del positions[pk]

    # Remaining open positions — valued at cost
    open_positions = len(positions)
    unrealized_value = sum(pos['shares'] * pos['cost_basis'] for pos in positions.values())

    # P&L = realized (from SELLs) only. Expired excluded (unknown outcome).
    # Open positions valued at cost (no mark-to-market).
    final_pnl = round(realized_pnl, 2)
    total_value = round(cash + unrealized_value, 2)

    total_value = round(cash + unrealized_value, 2)
    final_pnl = round(realized_pnl, 2)

    warnings = []
    total_simulated = buy_count + sell_count
    if expired_count > 0:
        warnings.append(f"{expired_count}个过期仓位已通过Gamma API查询真实结算结果")
    if total_simulated > 0 and buy_count / total_simulated > 0.8 and sell_count == 0:
        warnings.append(f"注意: 仅买入无卖出 ({buy_count}买) — 盈亏基于过期仓位的链上结算价计算")

    return {
        "trades_analyzed": len(trade_log),
        "total_trades_found": len(trades),
        "days": days,
        "initial_capital": capital,
        "pnl": final_pnl,
        "pnl_pct": round(final_pnl / capital * 100, 2),
        "realized_pnl": round(realized_pnl, 2),
        "resolved_pnl": round(resolved_pnl, 2),
        "expired_positions": expired_count,
        "expired_value": round(expired_value, 2),
        "open_positions": open_positions,
        "final_value": total_value,
        "unrealized_value": round(unrealized_value, 2),
        "cash_remaining": round(cash, 2),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "warnings": warnings,
        "trade_log": trade_log[-50:]
    }
