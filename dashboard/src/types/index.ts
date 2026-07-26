export interface ArtaxEvent {
  id: string;
  type: string;
  timestamp: string;
  source: string;
  data: Record<string, unknown>;
}

export interface MemoryEntry {
  key: string;
  value: unknown;
  type: "string" | "number" | "boolean" | "object" | "array" | "null";
  lastAccessed: string;
}

export interface Driver {
  id: string;
  name: string;
  type: string;
  status: "connected" | "disconnected" | "error";
  lastActivity: string;
}

export interface RuntimeStatus {
  running: boolean;
  uptime: number;
  eventCount: number;
  activeDrivers: number;
}

export type WebSocketMessage =
  | { type: "event"; payload: ArtaxEvent }
  | { type: "memory_update"; payload: MemoryEntry }
  | { type: "driver_status"; payload: Driver }
  | { type: "runtime_status"; payload: RuntimeStatus }
  | { type: "error"; payload: { message: string } };

export interface ConnectionState {
  status: "connected" | "disconnected" | "error";
  url: string;
  reconnectAttempts: number;
}
