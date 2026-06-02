"""pm-trader CLI wrapper for paper trading operations."""
import subprocess
import json
from config import PM_TRADER, INITIAL_CAPITAL


def pm(cmd: str) -> dict | None:
    """Execute a pm-trader command, return parsed JSON or None."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout.strip())
    except Exception:
        return None


def ensure_account(acct: str) -> dict:
    """Ensure account exists with INITIAL_CAPITAL, return balance dict."""
    bal = pm(f"{PM_TRADER} --account {acct} balance")
    if not bal or not bal.get('ok'):
        pm(f"{PM_TRADER} --account {acct} init --balance {INITIAL_CAPITAL}")
        return {"cash": INITIAL_CAPITAL, "total_value": INITIAL_CAPITAL, "pnl": 0}
    data = bal.get('data', {})
    return {
        "cash": data.get('cash', 0),
        "total_value": data.get('total_value', 0),
        "pnl": data.get('pnl', 0)
    }


def get_midpoint(slug: str) -> dict | None:
    """Get YES/NO prices for a market slug."""
    r = pm(f'{PM_TRADER} price "{slug}"')
    if r and r.get('ok') and r.get('data'):
        prices = r['data']
        return {
            'YES': prices.get('YES', prices.get('yes')),
            'NO': prices.get('NO', prices.get('no'))
        }
    return None


def place_market_order(acct: str, slug: str, outcome: str, side: str, amount_usd: float) -> dict | None:
    """Place a market order (buy or sell). Returns result or None."""
    if side.upper() == 'BUY':
        cmd = f'{PM_TRADER} --account {acct} buy "{slug}" "{outcome}" {amount_usd}'
    else:
        cmd = f'{PM_TRADER} --account {acct} sell "{slug}" "{outcome}" {amount_usd}'
    return pm(cmd)


def close_position(acct: str, slug: str, outcome: str, shares: float) -> dict | None:
    """Close a position by selling all shares."""
    cmd = f'{PM_TRADER} --account {acct} sell "{slug}" "{outcome}" {shares}'
    return pm(cmd)


def get_portfolio(acct: str) -> list[dict]:
    """Get all open positions for an account. Returns list of {slug, outcome, shares}."""
    r = pm(f"{PM_TRADER} --account {acct} portfolio")
    if not r or not r.get('ok') or not r.get('data'):
        return []
    positions = []
    for pos in r['data']:
        positions.append({
            'slug': pos.get('market_slug', ''),
            'outcome': pos.get('outcome', ''),
            'shares': pos.get('shares', 0),
        })
    return positions


def has_position(acct: str, slug: str, outcome: str) -> bool:
    """Check if account already holds a position in this market+outcome."""
    portfolio = get_portfolio(acct)
    for pos in portfolio:
        if pos['slug'] == slug and pos['outcome'].lower() == outcome.lower():
            return True
    return False
