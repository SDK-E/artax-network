import { StatusBar } from "@/components/StatusBar";
import { EventLog } from "@/components/EventLog";
import { MemoryInspector } from "@/components/MemoryInspector";
import { DriverStatus } from "@/components/DriverStatus";

export default function DashboardPage() {
  return (
    <main className="min-h-screen p-6">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-artax-blue-glow">
          Artax Network Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Real-time runtime monitoring
        </p>
      </header>

      <StatusBar status="disconnected" />

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatusCard title="Runtime" status="Not connected" />
        <StatusCard title="Events" status="Not connected" />
        <StatusCard title="Memory" status="Not connected" />
        <StatusCard title="Scheduler" status="Not connected" />
        <StatusCard title="Drivers" status="Not connected" />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <EventLog />
        <MemoryInspector />
      </div>

      <div className="mt-6">
        <DriverStatus />
      </div>
    </main>
  );
}

function StatusCard({ title, status }: { title: string; status: string }) {
  return (
    <div className="rounded-lg border border-artax-border bg-artax-surface p-4">
      <h3 className="text-sm font-medium text-gray-400">{title}</h3>
      <p className="mt-1 text-lg font-semibold text-artax-green">{status}</p>
    </div>
  );
}
