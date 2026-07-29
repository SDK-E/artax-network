export interface ArtaxEvent {
  event_id: string;
  type: string;
  timestamp: number;
  source: string;
  payload: Record<string, unknown>;
}

export interface ConnectionState {
  connected: boolean;
  connecting: boolean;
  error: string | null;
}

export interface DashboardSnapshot {
  events: ArtaxEvent[];
  driverCount: number;
  memoryKeys: number;
  uptime: number;
}
