/**
 * WebSocket client with automatic reconnection.
 *
 * This replaces the legacy WebSocket handling in agentchattr's frontend.
 * Differences from legacy behavior:
 * - No inbound commands (typing indicators, channel switches).
 * - No authentication on connect.
 * - Reconnects on close after 2 seconds (legacy used exponential backoff).
 *
 * @param {string} url - WebSocket URL (e.g. "ws://localhost:8000/ws")
 * @param {(event: object) => void} onEvent - called with parsed JSON for each server event
 * @param {(connected: boolean) => void} [onStatusChange] - called when connection status changes
 * @returns {{ close: () => void }}
 */
export function createWsClient(url, onEvent, onStatusChange) {
  let ws = null;
  let reconnectTimer = null;
  let closed = false;

  function connect() {
    if (closed) return;

    ws = new WebSocket(url);

    ws.onopen = () => {
      onStatusChange?.(true);
    };

    ws.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      onStatusChange?.(false);
      if (!closed) {
        reconnectTimer = setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror, triggering reconnect
    };
  }

  connect();

  return {
    close() {
      closed = true;
      clearTimeout(reconnectTimer);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    },
  };
}
