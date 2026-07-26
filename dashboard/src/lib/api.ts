import type { RuntimeStatus, ArtaxEvent, MemoryEntry, Driver } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export function getWebSocketUrl(): string {
  return `${WS_BASE}/ws`;
}

export function getApiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export async function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  const res = await fetch(getApiUrl("/api/status"));
  if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`);
  return res.json();
}

export async function fetchEvents(limit = 50): Promise<ArtaxEvent[]> {
  const res = await fetch(getApiUrl(`/api/events?limit=${limit}`));
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`);
  return res.json();
}

export async function fetchMemory(): Promise<MemoryEntry[]> {
  const res = await fetch(getApiUrl("/api/memory"));
  if (!res.ok) throw new Error(`Failed to fetch memory: ${res.status}`);
  return res.json();
}

export async function fetchDrivers(): Promise<Driver[]> {
  const res = await fetch(getApiUrl("/api/drivers"));
  if (!res.ok) throw new Error(`Failed to fetch drivers: ${res.status}`);
  return res.json();
}
