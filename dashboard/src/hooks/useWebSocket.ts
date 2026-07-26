"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface UseWebSocketOptions {
  url: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

interface WebSocketState {
  connected: boolean;
  error: string | null;
  lastMessage: unknown | null;
}

export function useWebSocket({
  url,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
}: UseWebSocketOptions): WebSocketState & {
  send: (data: unknown) => void;
  disconnect: () => void;
} {
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    error: null,
    lastMessage: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setState((prev) => ({ ...prev, connected: true, error: null }));
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setState((prev) => ({ ...prev, lastMessage: data }));
        } catch {
          setState((prev) => ({ ...prev, lastMessage: event.data }));
        }
      };

      ws.onerror = () => {
        setState((prev) => ({ ...prev, error: "WebSocket error" }));
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, connected: false }));
        wsRef.current = null;

        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          reconnectTimeout.current = setTimeout(connect, reconnectInterval);
        }
      };
    } catch (err) {
      setState((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : "Connection failed",
      }));
    }
  }, [url, reconnectInterval, maxReconnectAttempts]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimeout.current);
    reconnectAttempts.current = maxReconnectAttempts;
    wsRef.current?.close();
  }, [maxReconnectAttempts]);

  return { ...state, send, disconnect };
}
