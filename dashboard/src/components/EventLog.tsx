export function EventLog() {
  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <h2 className="mb-3 text-sm font-medium text-gray-400">Event Log</h2>
      <div className="h-64 overflow-y-auto rounded bg-artax-navy p-3 font-mono text-xs text-gray-500">
        <p>No events received. Waiting for connection...</p>
      </div>
    </div>
  );
}
