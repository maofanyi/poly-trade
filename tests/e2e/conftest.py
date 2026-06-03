"""E2E test fixtures — starts a live FastAPI server for Playwright."""
import os
import subprocess
import time
import sys
import tempfile
import pytest


@pytest.fixture(scope="session")
def live_server():
    """Start uvicorn on a fixed port, yield base URL, then kill."""
    port = 18766

    # Use a temp-file DB so every worker thread sees the same data.
    # :memory: would give each thread its own isolated in-memory DB.
    db_path = os.path.join(tempfile.gettempdir(), f"test_e2e_{os.getpid()}.db")
    os.environ["DB_PATH"] = db_path
    os.environ["SCAN_ENABLED"] = "0"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"

    # Wait for server to be ready
    import urllib.request
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{base_url}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        proc.wait()
        raise RuntimeError("Server did not start in time")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    # Clean up temp db
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def page(live_server, browser):
    """A fresh page pointing at the live server."""
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(10000)
    page.goto(live_server)
    # Wait for Vue to mount — the app div should be populated
    page.wait_for_selector("#app", state="attached", timeout=10000)
    page.wait_for_timeout(500)
    yield page
    context.close()
