import type { ArtaxEvent } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8081";

export function getApiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export async function fetchEvents(limit = 50): Promise<ArtaxEvent[]> {
  const res = await fetch(getApiUrl(`/api/events?limit=${limit}`));
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<Record<string, unknown>> {
  const res = await fetch(getApiUrl("/health"));
  if (!res.ok) throw new Error(`Failed to fetch health: ${res.status}`);
  return res.json();
}
