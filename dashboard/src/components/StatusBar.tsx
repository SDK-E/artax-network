"use client";

import { useDashboard } from "@/hooks/useDashboard";

export function StatusBar() {
  const { connection } = useDashboard();

  const color = connection.connected
    ? "bg-artax-green"
    : connection.connecting
      ? "bg-yellow-500"
      : "bg-red-500";

  const label = connection.connected
    ? "Connected"
    : connection.connecting
      ? "Reconnecting..."
      : "Disconnected";

  return (
    <div className="flex items-center gap-3 rounded-lg border border-artax-border bg-artax-surface px-4 py-2">
      <div className={`h-2.5 w-2.5 rounded-full ${color}`} />
      <span className="text-sm text-gray-300">{label}</span>
    </div>
  );
}
