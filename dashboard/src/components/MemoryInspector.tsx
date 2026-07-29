"use client";

import { useDashboard } from "@/hooks/useDashboard";

export function MemoryInspector() {
  const { connection, events } = useDashboard();
  const memoryEvents = events.filter(
    (e) => e.type === "memory_updated" || e.payload?.ns === "memory",
  );
  const latestMemory = memoryEvents
    .slice(-10)
    .reverse()
    .map((e) => `${e.payload?.key ?? "?"}: ${JSON.stringify(e.payload?.value ?? "")}`);

  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <h2 className="mb-3 text-sm font-medium text-gray-400">Memory Inspector</h2>
      <div className="h-64 overflow-y-auto rounded bg-artax-navy p-3 font-mono text-xs">
        {!connection.connected ? (
          <p className="text-gray-500">Waiting for connection...</p>
        ) : latestMemory.length === 0 ? (
          <p className="text-gray-500">No memory data available.</p>
        ) : (
          latestMemory.map((line, i) => (
            <div key={i} className="mb-1 last:mb-0">
              <span className="text-artax-blue-glow">▶</span>{" "}
              <span className="text-gray-300">{line}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
