"""Playwright E2E tests for copy trading dashboard."""
import sys, time, json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8766/copy_dashboard.html"
PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")

def run_tests():
    global PASS, FAIL
    PASS = FAIL = 0
    print("=" * 60)
    print("  Dashboard E2E Tests (Playwright)")
    print("=" * 60)

    # Check monitor is running
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:8766/copy_trader_state.json", timeout=3)
    except:
        print("  [SKIP] Monitor not running on :8766")
        print("=" * 60)
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # --- Test 1: Page loads ---
        print("\n--- Page Load ---")
        try:
            page.goto(BASE, wait_until="networkidle", timeout=15000)
            check("page loads without error", True)
        except Exception as e:
            check("page loads", False, str(e)[:60])
            browser.close()
            return False

        # --- Test 2: Title and header ---
        print("\n--- UI Elements ---")
        title = page.title()
        check("title contains Polymarket", "Polymarket" in title, f"got: {title}")

        h1 = page.locator("h1").text_content()
        check("h1 visible", len(h1) > 0, h1[:30])

        # Tabs
        tabs = page.locator(".tab")
        tab_count = tabs.count()
        check("two tabs exist", tab_count >= 2, f"found {tab_count}")

        # --- Test 3: Monitor tab active by default ---
        print("\n--- Monitor Tab ---")
        monitor_tab = page.locator("#tab-monitor")
        check("monitor tab visible", monitor_tab.is_visible())

        # Summary bar values
        summary_values = page.locator("#tab-monitor .summary-value")
        check("summary values present", summary_values.count() >= 4, f"found {summary_values.count()}")

        # P&L cards
        pnl_cards = page.locator("#pnlGrid .pnl-card")
        pnl_count = pnl_cards.count()
        check("P&L cards rendered", pnl_count >= 1, f"found {pnl_count}")

        # --- Test 4: Switch to Discover tab ---
        print("\n--- Discover Tab ---")
        discover_tab = page.locator(".tab").nth(1)
        discover_tab.click()
        page.wait_for_timeout(500)

        discover_content = page.locator("#tab-discover")
        check("discover tab visible", discover_content.is_visible())

        # Wallet table
        rows = page.locator("#discoverBody tr")
        row_count = rows.count()
        check("wallet table has rows", row_count >= 10, f"found {row_count} rows")

        # --- Test 5: Add wallet ---
        print("\n--- Add Wallet ---")
        # Find first "+ 添加跟单" button (not monitoring/remove buttons)
        add_btns = page.locator("#discoverBody .btn-xs").filter(has_text="添加")
        add_count = add_btns.count()
        check("add buttons exist", add_count > 0, f"found {add_count}")

        if add_count > 0:
            wallet_name = page.locator("#discoverBody tr .name-cell").first.text_content()
            add_btns.first.click()
            page.wait_for_timeout(1000)
            toast = page.locator("#toast")
            check("toast notification shown", toast.is_visible())

            # Switch back to monitor tab
            page.locator(".tab").first.click()
            page.wait_for_timeout(1000)

            # That wallet should now be visible in P&L cards
            pnl_names = page.locator("#pnlGrid .pnl-name").all_text_contents()
            check("added wallet in P&L cards", wallet_name in ' '.join(pnl_names),
                  f"looking for {wallet_name} in {pnl_names[:3]}...")

        # --- Test 6: Remove wallet ---
        print("\n--- Remove Wallet ---")
        remove_btns = page.locator("#tab-monitor .btn-xs.remove")
        if remove_btns.count() > 0:
            before_count = page.locator("#pnlGrid .pnl-card").count()
            # Scroll into view then click
            remove_btns.first.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            remove_btns.first.click(force=True)
            page.wait_for_timeout(1500)
            after_count = page.locator("#pnlGrid .pnl-card").count()
            check("wallet removed from view", after_count < before_count,
                  f"{before_count} -> {after_count}")
        else:
            check("remove button visible", False, "no remove buttons found")

        # --- Test 7: Time filters ---
        print("\n--- Time Filters ---")
        filter_btns = page.locator("#tab-monitor .filter-btn")
        if filter_btns.count() >= 4:
            # Click "今日"
            filter_btns.nth(1).click()
            page.wait_for_timeout(500)
            active_filter = page.locator("#tab-monitor .filter-btn.active").text_content()
            check("today filter active", "今日" in (active_filter or ""))

            # Click "全部"
            filter_btns.first.click()
            page.wait_for_timeout(500)
            active_filter2 = page.locator("#tab-monitor .filter-btn.active").text_content()
            check("all filter active", "全部" in (active_filter2 or ""))

        # --- Test 8: Trade cards ---
        print("\n--- Trade Cards ---")
        trade_cards = page.locator("#tab-monitor .trade-card")
        tc_count = trade_cards.count()
        check("trade cards exist", tc_count >= 1, f"found {tc_count}")

        # Check for FILLED trades if any
        filled_labels = page.locator(".status-placed").all_text_contents()
        if filled_labels:
            check("FILLED trades visible", any("成交" in l for l in filled_labels),
                  f"labels: {filled_labels[:3]}")

        # --- Screenshot ---
        page.screenshot(path="G:/trade/test_screenshot.png", full_page=True)
        print("\n  Screenshot saved: test_screenshot.png")

        browser.close()

    print(f"\n{'='*60}")
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print(f"{'='*60}")
    return FAIL == 0

if __name__ == '__main__':
    ok = run_tests()
    sys.exit(0 if ok else 1)
