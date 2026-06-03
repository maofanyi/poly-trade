"""E2E tests for dashboard page load and tab switching."""


def test_dashboard_loads(page):
    """Page loads successfully — Vue mounts and renders content."""
    # Body should be visible
    assert page.locator("body").is_visible()

    # Title should be set
    title = page.title()
    assert len(title) > 0
    assert "Polymarket" in title or "跟单" in title

    # The Vue app container should exist and contain rendered content
    app = page.locator("#app")
    assert app.is_visible()

    # At least one tab button should be visible (Vue rendered them)
    tabs = page.locator(".tab")
    assert tabs.count() >= 2


def test_tab_switching(page):
    """Click wallet management tab and verify content changes."""
    page.wait_for_timeout(1000)

    # Verify monitor tab is active by default
    monitor_tab = page.locator(".tab.active")
    assert monitor_tab.count() >= 1
    assert "监控面板" in (monitor_tab.first.text_content() or "")

    # Click the wallet management tab
    wallets_tab = page.locator("button.tab").filter(has_text="钱包管理")
    if wallets_tab.count() > 0:
        wallets_tab.first.click()
        page.wait_for_timeout(800)

        # The wallets tab should now be active
        active_tab = page.locator(".tab.active")
        assert active_tab.count() >= 1
        active_text = active_tab.first.text_content() or ""
        assert "钱包管理" in active_text

    # Page should still be visible after navigation
    assert page.locator("body").is_visible()
