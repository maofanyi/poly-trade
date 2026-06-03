"""Tests for websocket.py WSManager."""
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock


class TestWSManager:
    def test_connect_adds_to_connections(self):
        from websocket import WSManager
        mgr = WSManager()
        ws = MagicMock()
        ws.accept = AsyncMock()

        asyncio.run(mgr.connect(ws))
        assert len(mgr.connections) == 1

    def test_disconnect_removes(self):
        from websocket import WSManager
        mgr = WSManager()
        ws = MagicMock()
        ws.accept = AsyncMock()

        asyncio.run(mgr.connect(ws))
        mgr.disconnect(ws)
        assert len(mgr.connections) == 0

    def test_disconnect_idempotent(self):
        from websocket import WSManager
        mgr = WSManager()
        ws = MagicMock()
        mgr.disconnect(ws)  # should not raise
        assert len(mgr.connections) == 0

    def test_broadcast_sends_to_all(self):
        from websocket import WSManager
        mgr = WSManager()
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()

        asyncio.run(mgr.connect(ws1))
        asyncio.run(mgr.connect(ws2))

        msg = {"type": "pnl_update", "wallets": []}
        asyncio.run(mgr.broadcast(msg))

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    def test_broadcast_removes_dead_connections(self):
        from websocket import WSManager
        mgr = WSManager()
        ws_good = MagicMock()
        ws_good.accept = AsyncMock()
        ws_good.send_text = AsyncMock()
        ws_bad = MagicMock()
        ws_bad.accept = AsyncMock()
        ws_bad.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        asyncio.run(mgr.connect(ws_good))
        asyncio.run(mgr.connect(ws_bad))
        asyncio.run(mgr.broadcast({"type": "ping"}))

        assert len(mgr.connections) == 1
        assert ws_bad not in mgr.connections
