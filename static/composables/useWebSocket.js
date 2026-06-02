export function useWebSocket({ onMessage, onOpen, onClose }) {
  let ws = null;
  let pingTimer = null;

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws`;

    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('WS connected');
      pingTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) ws.send('pong');
      }, 25000);
      if (onOpen) onOpen();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (onMessage) onMessage(msg);
      } catch (e) { console.error('WS parse:', e); }
    };

    ws.onclose = () => {
      console.log('WS disconnected');
      if (pingTimer) clearInterval(pingTimer);
      if (onClose) onClose();
    };

    ws.onerror = (e) => { console.error('WS error:', e); };
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }

  return { connect, send };
}
