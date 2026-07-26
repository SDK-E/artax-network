export function DriverStatus() {
  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <h2 className="mb-3 text-sm font-medium text-gray-400">Driver Status</h2>
      <div className="rounded bg-artax-navy p-3">
        <p className="font-mono text-xs text-gray-500">
          No driver data available. Waiting for connection...
        </p>
      </div>
    </div>
  );
}
