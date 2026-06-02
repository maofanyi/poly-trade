"""WebSocket manager for real-time dashboard updates."""
import asyncio
import json
from fastapi import WebSocket

class WSManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, msg: dict):
        payload = json.dumps(msg, ensure_ascii=False, default=str)
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def heartbeat(self):
        """Send ping every 30s."""
        while True:
            await asyncio.sleep(30)
            await self.broadcast({"type": "ping"})

ws_manager = WSManager()
