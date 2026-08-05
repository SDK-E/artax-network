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
    connectedDrivers: [],
    unhealthyDrivers: [],
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

          if (msg.type === "state") {
            setSnapshot((prev) => ({
              ...prev,
              uptime: typeof msg.uptime === "number" ? msg.uptime : prev.uptime,
              driverCount:
                typeof msg.drivers_connected === "number"
                  ? msg.drivers_connected
                  : prev.driverCount,
              connectedDrivers: Array.isArray(msg.connected_drivers)
                ? msg.connected_drivers
                : prev.connectedDrivers,
              unhealthyDrivers: Array.isArray(msg.unhealthy_drivers)
                ? msg.unhealthy_drivers
                : prev.unhealthyDrivers,
              memoryKeys:
                typeof msg.memory_keys === "number"
                  ? msg.memory_keys
                  : prev.memoryKeys,
            }));
            return;
          }

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

            // Always recompute driver count and driver list from history.
            // The backend sends "state" first, then "history" — but an await
            // between them lets the EventBus consumer process events in
            // between, so "state" may report 0 while "history" contains
            // driver_connected events. History is the source of truth here.
            const driverSet = new Set<string>();
            const unhealthySet = new Set<string>();
            let memoryKeys = 0;
            for (const e of historyEvents) {
              if (e.type === "driver_connected") {
                driverSet.add(String(e.payload?.driver ?? "unknown"));
                unhealthySet.delete(String(e.payload?.driver ?? "unknown"));
              } else if (e.type === "driver_disconnected") {
                driverSet.delete(String(e.payload?.driver ?? "unknown"));
              } else if (e.type === "driver_unhealthy") {
                unhealthySet.add(String(e.payload?.driver ?? "unknown"));
              }
              if (e.type === "memory_updated" && e.payload?.key) memoryKeys += 1;
            }
            setSnapshot((prev) => ({
              ...prev,
              driverCount: driverSet.size,
              connectedDrivers: Array.from(driverSet),
              unhealthyDrivers: Array.from(unhealthySet),
              memoryKeys,
            }));
            return;
          }

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
              let driverCount = prev.driverCount;
              let connectedDrivers = [...prev.connectedDrivers];
              let unhealthyDrivers = [...prev.unhealthyDrivers];
              if (msg.type === "driver_connected") {
                driverCount += 1;
                const name = String(msg.payload?.driver ?? "unknown");
                if (!connectedDrivers.includes(name)) connectedDrivers.push(name);
                unhealthyDrivers = unhealthyDrivers.filter((d) => d !== name);
              } else if (msg.type === "driver_disconnected") {
                driverCount = Math.max(0, driverCount - 1);
                const name = String(msg.payload?.driver ?? "unknown");
                connectedDrivers = connectedDrivers.filter((d) => d !== name);
              } else if (msg.type === "driver_unhealthy") {
                const name = String(msg.payload?.driver ?? "unknown");
                if (!unhealthyDrivers.includes(name)) unhealthyDrivers.push(name);
              }
              const memoryKeys =
                msg.type === "memory_updated" && msg.payload?.key
                  ? prev.memoryKeys + 1
                  : prev.memoryKeys;
              return {
                ...prev,
                driverCount,
                connectedDrivers,
                unhealthyDrivers,
                memoryKeys,
              };
            });
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
