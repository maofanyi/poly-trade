"""Alert engine: threshold checks and webhook delivery."""
import json
import urllib.request
from datetime import datetime, timedelta
from database import get_db

def get_config(db) -> dict:
    row = db.execute("SELECT * FROM alert_config WHERE id = 1").fetchone()
    if not row:
        db.execute("INSERT INTO alert_config (id) VALUES (1)")
        db.commit()
        return {"enabled": 1, "pnl_threshold_pct": -20.0, "single_loss_usd": 10.0, "webhook_type": None, "webhook_url": None}
    return dict(row)

def update_config(db, **kwargs):
    sets = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [1]
    db.execute(f"UPDATE alert_config SET {sets}, updated_at=datetime('now','localtime') WHERE id=?", values)
    db.commit()

def was_alerted_recently(db, alert_type: str, wallet_id: int, hours: int = 1) -> bool:
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    row = db.execute(
        "SELECT id FROM alert_log WHERE alert_type=? AND wallet_id=? AND created_at > ? LIMIT 1",
        (alert_type, wallet_id, since)
    ).fetchone()
    return row is not None

def log_alert(db, alert_type: str, wallet_id: int | None, message: str, sent_via: str = "toast"):
    db.execute(
        "INSERT INTO alert_log (alert_type, wallet_id, message, sent_via) VALUES (?,?,?,?)",
        (alert_type, wallet_id, message, sent_via)
    )
    db.commit()

def send_webhook(webhook_type: str, webhook_url: str, message: str):
    """Send alert via webhook (Bark/Telegram/WeCom)."""
    try:
        if webhook_type == 'bark':
            import urllib.parse
            url = f"{webhook_url}/{urllib.parse.quote(message)}"
            urllib.request.urlopen(url, timeout=5)
        elif webhook_type == 'telegram':
            data = json.dumps({"text": message, "parse_mode": "HTML"}).encode()
            req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
        elif webhook_type == 'wecom':
            data = json.dumps({"msgtype": "markdown", "markdown": {"content": message}}).encode()
            req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Webhook error ({webhook_type}): {e}")

async def check_alerts(ws_manager, wallet_name: str, wallet_id: int):
    """Check alert thresholds after a trade."""
    db = get_db()
    cfg = get_config(db)
    if not cfg['enabled']:
        return

    # Check single trade loss
    last_trade = db.execute(
        "SELECT pnl_realized, sim_usd FROM trade_log WHERE wallet_id=? AND status='FILLED' ORDER BY id DESC LIMIT 1",
        (wallet_id,)
    ).fetchone()
    if last_trade and last_trade['pnl_realized'] and abs(last_trade['pnl_realized']) > cfg['single_loss_usd']:
        msg = f"⚠️ {wallet_name} 单笔亏损 ${last_trade['pnl_realized']:.2f}"
        if not was_alerted_recently(db, 'single_trade_loss', wallet_id):
            log_alert(db, 'single_trade_loss', wallet_id, msg, 'toast')
            await ws_manager.broadcast({"type": "alert", "alert_type": "single_trade_loss", "wallet_name": wallet_name, "message": msg})
            if cfg.get('webhook_url'):
                send_webhook(cfg['webhook_type'], cfg['webhook_url'], msg)
                log_alert(db, 'single_trade_loss', wallet_id, msg, 'webhook')

    # Check wallet P&L threshold
    pnl = db.execute(
        "SELECT pnl_pct FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
        (wallet_id,)
    ).fetchone()
    if pnl and pnl['pnl_pct'] is not None and pnl['pnl_pct'] <= cfg['pnl_threshold_pct']:
        msg = f"🔴 {wallet_name} 亏损超过阈值: {pnl['pnl_pct']:.1f}%"
        if not was_alerted_recently(db, 'wallet_loss', wallet_id):
            log_alert(db, 'wallet_loss', wallet_id, msg, 'toast')
            await ws_manager.broadcast({"type": "alert", "alert_type": "wallet_loss", "wallet_name": wallet_name, "message": msg})
            if cfg.get('webhook_url'):
                send_webhook(cfg['webhook_type'], cfg['webhook_url'], msg)
                log_alert(db, 'wallet_loss', wallet_id, msg, 'webhook')
