"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { ArtaxEvent, ConnectionState, DashboardSnapshot } from "@/types";

interface UseDashboardOptions {
  url?: string;
}

export function useDashboard({ url: urlProp }: UseDashboardOptions = {}) {
  const defaultUrl = "ws://localhost:8081";
  const url = urlProp ?? defaultUrl;
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 20;
  const reconnectInterval = 3000;

  const [connection, setConnection] = useState<ConnectionState>({
    connected: false,
    connecting: true,
    error: null,
  });
  const [events, setEvents] = useState<ArtaxEvent[]>([]);
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>({
    events: [],
    driverCount: 0,
    memoryKeys: 0,
    uptime: 0,
  });

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setConnection({ connected: false, connecting: true, error: null });

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnection({ connected: true, connecting: false, error: null });
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "history") {
            const historyEvents: ArtaxEvent[] = (msg.events ?? []).map(
              (e: Record<string, unknown>) => ({
                event_id: String(e.event_id ?? ""),
                type: String(e.type ?? ""),
                timestamp: Number(e.timestamp ?? 0),
                source: String(e.source ?? ""),
                payload: (e.payload as Record<string, unknown>) ?? {},
              }),
            );
            setEvents(historyEvents);
          } else {
            const artaxEvent: ArtaxEvent = {
              event_id: String(msg.event_id ?? ""),
              type: String(msg.type ?? ""),
              timestamp: Number(msg.timestamp ?? 0),
              source: String(msg.source ?? ""),
              payload: (msg.payload as Record<string, unknown>) ?? {},
            };
            setEvents((prev) => {
              const next = [...prev, artaxEvent];
              return next.slice(-200);
            });

            if (msg.source === "runtime" || msg.source === "chromium") {
              setSnapshot((prev) => {
                const driverCount =
                  msg.type === "driver_connected"
                    ? prev.driverCount + 1
                    : msg.type === "driver_disconnected"
                      ? Math.max(0, prev.driverCount - 1)
                      : prev.driverCount;
                const memoryKeys =
                  msg.type === "memory_updated" && msg.payload?.key
                    ? prev.memoryKeys + 1
                    : prev.memoryKeys;
                return { ...prev, driverCount, memoryKeys };
              });
            }
          }
        } catch {
          // ignore unparseable messages
        }
      };

      ws.onerror = () => {
        setConnection({ connected: false, connecting: false, error: "WebSocket error" });
      };

      ws.onclose = () => {
        setConnection({ connected: false, connecting: false, error: null });
        wsRef.current = null;

        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          setConnection({ connected: false, connecting: true, error: null });
          reconnectTimeout.current = setTimeout(() => { connect(); }, reconnectInterval);
        }
      };
    } catch (err) {
      setConnection({
        connected: false,
        connecting: false,
        error: err instanceof Error ? err.message : "Connection failed",
      });
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return {
    connection,
    events,
    snapshot,
    clearEvents,
  };
}
