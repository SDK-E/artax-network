export function MemoryInspector() {
  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <h2 className="mb-3 text-sm font-medium text-gray-400">Memory Inspector</h2>
      <div className="h-64 overflow-y-auto rounded bg-artax-navy p-3">
        <p className="font-mono text-xs text-gray-500">
          No memory data available. Waiting for connection...
        </p>
      </div>
    </div>
  );
}
