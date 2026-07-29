"use client";

import { useDashboard } from "@/hooks/useDashboard";

export function DriverStatus() {
  const { connection, snapshot } = useDashboard();
  const drivers = snapshot.driverCount;

  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <h2 className="mb-3 text-sm font-medium text-gray-400">Driver Status</h2>
      <div className="rounded bg-artax-navy p-3">
        {!connection.connected ? (
          <p className="font-mono text-xs text-gray-500">
            Waiting for connection...
          </p>
        ) : drivers > 0 ? (
          <p className="font-mono text-xs text-artax-green">
            {drivers} driver{drivers !== 1 ? "s" : ""} connected
          </p>
        ) : (
          <p className="font-mono text-xs text-yellow-500">
            No drivers connected
          </p>
        )}
      </div>
    </div>
  );
}
