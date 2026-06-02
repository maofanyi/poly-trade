"""Close positions for copy trading wallets.
Usage:
  python close_all.py              # close ALL wallets
  python close_all.py cowcat       # close specific wallet
  python close_all.py --list       # list all positions
"""
import subprocess, json, sys

PM = "pm-trader"

def pm(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout.strip())
    except: return None

def get_wallets():
    """Get all copy-* accounts."""
    import os, glob
    # Use pm-trader accounts list
    r = pm(f"{PM} accounts list")
    if r and r.get('ok'):
        return [a for a in r.get('data', []) if a.startswith('copy-')]
    # Fallback: known wallets
    return ["copy-HondaCivic","copy-ikik111","copy-Maskache2","copy-JoeTheMeteorologist",
            "copy-BeefSlayer","copy-Varyage","copy-wokerjoesleeper","copy-cowcat",
            "copy-ewelmealt","copy-EFFICIENCYEXPERT","copy-Bonereaper","copy-XRPDips"]

def close_wallet(acct, dry_run=False):
    """Close all positions for one wallet."""
    r = pm(f"{PM} --account {acct} portfolio")
    if not r or not r.get('ok') or not r.get('data'):
        print(f"  {acct}: no positions")
        return 0, 0

    closed = 0
    total_value = 0
    for pos in r['data']:
        slug = pos.get('market_slug', '')
        outcome = pos.get('outcome', '')
        shares = pos.get('shares', 0)
        price = pos.get('live_price', 0)
        value = round(shares * price, 2)

        if dry_run:
            print(f"  {acct}: {outcome} {shares:.0f}shares @ ${price:.4f} = ${value:.2f}")
        else:
            cmd = f'{PM} --account {acct} sell "{slug}" "{outcome}" {shares}'
            result = pm(cmd)
            if result and result.get('ok'):
                print(f"  {acct}: SOLD {outcome} {shares:.0f}shares @ ~${price:.4f}")
            else:
                err = result.get('error', 'unknown') if result else 'timeout'
                print(f"  {acct}: FAILED {outcome} {shares:.0f}shares - {err[:40]}")

        closed += 1
        total_value += value

    return closed, total_value

if __name__ == '__main__':
    if '--list' in sys.argv:
        print("=== Open Positions ===")
        wallets = get_wallets()
        for w in wallets:
            close_wallet(w, dry_run=True)
        sys.exit(0)

    dry = '--dry' in sys.argv

    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        target = sys.argv[1]
        wallets = [f"copy-{target}"]
    else:
        wallets = get_wallets()

    print(f"Closing positions for {len(wallets)} wallets...")
    if dry: print("(DRY RUN - no actual orders)")

    total_closed = 0
    total_value = 0
    for w in wallets:
        c, v = close_wallet(w, dry_run=dry)
        total_closed += c
        total_value += v

    print(f"\nTotal: {total_closed} positions closed, ~${total_value:.2f} value")
    if dry: print("Run without --dry to execute.")
