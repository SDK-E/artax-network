"use client";

import { useDashboard } from "@/hooks/useDashboard";
import { useMemo } from "react";

export function DriverStatus() {
  const { connection, snapshot } = useDashboard();
  const drivers = snapshot.driverCount;
  const unhealthy = snapshot.unhealthyDrivers;

  const allDrivers = useMemo(() => {
    const connected = snapshot.connectedDrivers;
    const unhealthies = unhealthy.filter((d) => !connected.includes(d));
    return [...connected, ...unhealthies];
  }, [snapshot.connectedDrivers, unhealthy]);

  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <h2 className="mb-3 text-sm font-medium text-gray-400">Driver Status</h2>
      <div className="rounded bg-artax-navy p-3">
        {!connection.connected ? (
          <p className="font-mono text-xs text-gray-500">
            Waiting for connection...
          </p>
        ) : drivers > 0 ? (
          <div className="flex flex-col gap-1">
            <p className="font-mono text-xs text-artax-green">
              {drivers} driver{drivers !== 1 ? "s" : ""} connected
            </p>
            <div className="flex flex-wrap gap-1.5">
              {allDrivers.map((name) => (
                <span
                  key={name}
                  className="inline-block rounded bg-artax-blue-glow/10 px-2 py-0.5 font-mono text-xs text-artax-blue-glow"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        ) : unhealthy.length > 0 ? (
          <div className="flex flex-col gap-1">
            <p className="font-mono text-xs text-red-500">
              {unhealthy.length} driver{unhealthy.length !== 1 ? "s" : ""} unhealthy
            </p>
            <div className="flex flex-wrap gap-1.5">
              {unhealthy.map((name) => (
                <span
                  key={name}
                  className="inline-block rounded bg-red-500/10 px-2 py-0.5 font-mono text-xs text-red-500"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <p className="font-mono text-xs text-yellow-500">
            No drivers connected
          </p>
        )}
      </div>
    </div>
  );
}
