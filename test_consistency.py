"""1-minute consistency test: check dashboard doesn't flip wallet states."""
import time, json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8766/copy_dashboard.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(BASE, wait_until="networkidle", timeout=15000)

    print("Starting 60s consistency test...")
    print(f"Time: {time.strftime('%H:%M:%S')}")
    print()

    prev_active = set()
    prev_inactive = set()
    flips = []
    errors = 0
    samples = 0

    for i in range(12):  # 12 samples × 5s = 60s
        time.sleep(5)
        samples += 1

        # Check for JS errors
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(err))

        # Read P&L card names (active wallets in leaderboard)
        pnl_names = page.locator("#pnlGrid .pnl-name").all_text_contents()
        active_now = set(n.strip() for n in pnl_names if n.strip())

        # Read inactive section
        inactive_visible = page.locator("#inactiveTitle").is_visible()
        inactive_names = set()
        if inactive_visible:
            inactive_names = set(n.strip() for n in page.locator("#inactiveGrid .pnl-name").all_text_contents())

        # Read trade card names - extract just the wallet name (before first space)
        trade_raw = page.locator("#tradeGrid .trade-card-name").all_text_contents()
        trade_names = set(n.strip().split(' ')[0] for n in trade_raw if n.strip())

        # Counts should match (names may have extra text)
        if len(active_now) != len(trade_names) and inactive_visible:
            errors += 1
            print(f"  [ERROR] Mismatch: leaderboard={sorted(active_now)}, tradeCards={sorted(trade_names)}")

        # Detect flips
        if prev_active and active_now != prev_active:
            added = active_now - prev_active
            removed = prev_active - active_now
            flips.append((added, removed))
            if added: print(f"  [FLIP] +{added}")
            if removed: print(f"  [FLIP] -{removed}")

        # Print snapshot
        ts = time.strftime('%H:%M:%S')
        print(f"  [{ts}] active={len(active_now)} inactive={len(inactive_names)} PnL_cards={len(active_now)} trade_cards={len(trade_names)}")

        prev_active = active_now
        prev_inactive = inactive_names

    print()
    print(f"{'='*50}")
    print(f"Samples: {samples} | Errors: {errors} | Flips: {len(flips)}")
    if flips:
        print("FLIPS DETECTED:")
        for added, removed in flips:
            print(f"  +{added} -{removed}")
    else:
        print("PASS: No wallet flips in 60 seconds")
    print(f"{'='*50}")

    # Final check: read state directly
    import urllib.request
    raw = urllib.request.urlopen("http://localhost:8766/copy_trader_state.json").read().decode('utf-8')
    state = json.loads(raw)
    filled_wallets = set()
    for t in state.get('sim_trades', []):
        if t.get('status') == 'FILLED':
            filled_wallets.add(t['wallet'])
    print(f"\nServer FILLED wallets: {sorted(filled_wallets)}")
    print(f"Browser active wallets: {sorted(active_now)}")
    match = filled_wallets == active_now
    print(f"Match: {'PASS' if match else 'MISMATCH!'}")

    browser.close()
