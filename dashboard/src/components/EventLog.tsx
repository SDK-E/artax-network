"use client";

import { useDashboard } from "@/hooks/useDashboard";
import { useRef, useEffect } from "react";

export function EventLog() {
  const { connection, events, clearEvents } = useDashboard();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-400">Event Log</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{events.length} events</span>
          {events.length > 0 && (
            <button
              onClick={clearEvents}
              className="rounded px-2 py-0.5 text-xs text-gray-400 hover:bg-artax-navy hover:text-gray-200"
            >
              Clear
            </button>
          )}
        </div>
      </div>
      <div
        ref={scrollRef}
        className="h-64 overflow-y-auto rounded bg-artax-navy p-3 font-mono text-xs"
      >
        {!connection.connected && !connection.connecting && (
          <p className="text-gray-500">Disconnected. Waiting...</p>
        )}
        {connection.connecting && (
          <p className="text-gray-500">Connecting...</p>
        )}
        {events.length === 0 && connection.connected && (
          <p className="text-gray-500">Connected. No events yet.</p>
        )}
        {events.map((ev, i) => (
          <div key={ev.event_id || i} className="mb-1 last:mb-0">
            <span className="text-artax-blue-glow">
              [{ev.type}]
            </span>{" "}
            <span className="text-gray-400">{ev.source}</span>{" "}
            <span className="text-gray-500">
              {JSON.stringify(ev.payload)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
