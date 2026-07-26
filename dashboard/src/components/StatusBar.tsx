interface StatusBarProps {
  status: "connected" | "disconnected" | "error";
}

export function StatusBar({ status }: StatusBarProps) {
  const statusColors = {
    connected: "bg-artax-green",
    disconnected: "bg-yellow-500",
    error: "bg-red-500",
  };

  const statusLabels = {
    connected: "Connected",
    disconnected: "Disconnected",
    error: "Error",
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-artax-border bg-artax-surface px-4 py-2">
      <div className={`h-2.5 w-2.5 rounded-full ${statusColors[status]}`} />
      <span className="text-sm text-gray-300">
        {statusLabels[status]}
      </span>
    </div>
  );
}
