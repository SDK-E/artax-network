# PRD: Dashboard

**Subsystem:** `artax.dashboard`
**Version:** 0.1
**Status:** Draft

---

## 1. Problem Statement

Developers building embodied AI agents need real-time visibility into what the runtime is doing. Without a dashboard, debugging requires reading log files, running scripts to query memory, and manually inspecting event flow. This slows development and makes it difficult to understand the agent's behavior in real-time.

The dashboard solves this by providing a web-based UI that connects to the runtime via WebSocket and displays events, memory state, driver status, and scheduler queue in real-time. It is a developer tool — a window into the runtime's internals that updates live as events flow through the system.

The dashboard is read-only. It observes the runtime but never modifies it. This constraint keeps the dashboard simple and prevents debugging tools from accidentally changing the system under test.

---

## 2. Goals

1. **Event visualization.** Display a live feed of events flowing through the EventBus. Show event type, source, timestamp, and payload. Support filtering by type and source. Highlight high-priority and error events.

2. **Memory inspector.** Display the current contents of Working Memory. Show keys, values, namespaces, and TTLs. Support search by key prefix or namespace. Allow expanding nested values.

3. **Driver status.** Display the state of each registered driver: connected, unhealthy, error. Show driver health metrics (latency, error count, last event time). Highlight unhealthy drivers.

4. **Scheduler view.** Display the scheduler queue: pending events by priority, total scheduled/delivered/cancelled counts. Show the tick rate and whether the scheduler is paused.

5. **Real-time updates.** All views update in real-time via WebSocket. No manual refresh required. Events appear within 100ms of being published.

6. **Responsive layout.** Dashboard works on desktop browsers (Chrome, Firefox, Safari). Mobile support is not required in v0.1.

7. **Self-contained.** Dashboard is a Next.js application that runs independently of the runtime. It connects to the runtime via WebSocket URL (configurable). It can be developed and tested without a running runtime.

---

## 3. Non-Goals

1. **User authentication.** Dashboard has no login, no user accounts, no access control. It connects to a local runtime and trusts all data.

2. **Deployment dashboard.** Dashboard is not a deployment monitoring tool. It does not show infrastructure metrics (CPU, memory, network) or deployment status.

3. **Metrics collection.** Dashboard does not collect, store, or export metrics. It displays what the runtime provides in real-time. Historical metrics are a v0.2 concern.

4. **Configuration editing.** Dashboard cannot modify runtime configuration. It is read-only. Config editing is a v0.2 concern.

5. **Log viewer.** Dashboard does not display application logs. Logs are viewed via terminal or log files. Log integration is a v0.2 concern.

6. **Mobile support.** Dashboard is designed for desktop browsers. Mobile layout is a future concern.

7. **Multi-runtime.** Dashboard connects to one runtime instance at a time. Multi-runtime view is a future concern.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Dashboard (Next.js)                  │
│                                                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐      │
│  │  EventFeed │  │  Memory   │  │  Driver   │      │
│  │  (live)    │  │  Inspector│  │  Status   │      │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘      │
│        │              │              │              │
│  ┌─────┴──────────────┴──────────────┴─────┐       │
│  │           WebSocket Client              │       │
│  └─────────────────┬───────────────────────┘       │
│                    │                                │
│  ┌─────────────────┴───────────────────────┐       │
│  │           React State (Zustand)          │       │
│  └─────────────────────────────────────────┘       │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket (ws://localhost:8765)
                       ▼
┌─────────────────────────────────────────────────────┐
│                    Runtime                          │
│  ┌───────────────────────────────────────────────┐ │
│  │      WebSocket Server (read-only)             │ │
│  │  - broadcasts events to connected clients     │ │
│  │  - responds to state queries                  │ │
│  │  - rejects state-modifying commands           │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### WebSocket Protocol

The dashboard connects to the runtime via WebSocket. Messages are JSON.

**Server → Client (broadcast):**

```json
{
  "type": "event",
  "data": {
    "event_id": "abc123",
    "type": "dom_changed",
    "source": "chromium",
    "timestamp": 1700000000.0,
    "payload": {"selector": "#main", "change": "text_updated"}
  }
}
```

```json
{
  "type": "state",
  "data": {
    "section": "memory",
    "entries": {
      "chromium.dom.title": "Example Page",
      "scheduler.active_intent": {"goal": "submit_form"}
    }
  }
}
```

```json
{
  "type": "driver_status",
  "data": {
    "drivers": {
      "chromium": {"state": "connected", "latency_ms": 12.5, "error_count": 0},
      "terminal": {"state": "unhealthy", "latency_ms": null, "error_count": 3}
    }
  }
}
```

```json
{
  "type": "scheduler_status",
  "data": {
    "paused": false,
    "pending_urgent": 0,
    "pending_high": 2,
    "pending_medium": 5,
    "pending_low": 1,
    "total_delivered": 1234
  }
}
```

**Client → Server (query):**

```json
{
  "type": "query_memory",
  "data": {"namespace": "chromium", "key_prefix": "dom"}
}
```

```json
{
  "type": "query_events",
  "data": {"type": "dom_changed", "limit": 50}
}
```

**Server → Client (response):**

```json
{
  "type": "query_result",
  "data": {
    "query_id": "q123",
    "results": {...}
  }
}
```

### React Components

| Component | Description |
|---|---|
| `EventFeed` | Scrolling list of events. New events appear at top. Filter by type/source. |
| `EventDetail` | Expanded view of a single event. Shows full payload as JSON. |
| `MemoryInspector` | Table of memory entries. Columns: key, value, namespace, TTL, updated_at. |
| `MemorySearch` | Search bar for filtering memory entries by key prefix or namespace. |
| `DriverStatusCard` | Card per driver. Shows state, latency, error count, last event time. |
| `SchedulerView` | Queue depth per priority. Tick count. Pause/resume toggle (read-only display). |
| `ConnectionStatus` | WebSocket connection status indicator (connected/disconnected/reconnecting). |

### State Management

Dashboard uses Zustand for client-side state:

```typescript
interface DashboardState {
  events: SemanticEvent[];
  memory: Record<string, any>;
  drivers: Record<string, DriverStatus>;
  scheduler: SchedulerStatus;
  connected: boolean;
  eventFilter: { type?: string; source?: string };
  memoryFilter: { namespace?: string; keyPrefix?: string };
}
```

---

## 5. Interfaces

### WebSocket Server (Runtime Side)

```python
class DashboardServer:
    def __init__(self, port: int, event_bus: EventBus, memory: WorkingMemory,
                 scheduler: Scheduler, drivers: dict[str, Driver]) -> None: ...

    async def start(self) -> None:
        """Start the WebSocket server and begin broadcasting."""

    async def stop(self) -> None:
        """Stop the WebSocket server and close all connections."""
```

### WebSocket Client (Dashboard Side)

```typescript
interface ArtaxClient {
  connect(url: string): void;
  disconnect(): void;
  onEvent(callback: (event: SemanticEvent) => void): void;
  onState(callback: (state: StateUpdate) => void): void;
  onDriverStatus(callback: (status: DriverStatusUpdate) => void): void;
  onSchedulerStatus(callback: (status: SchedulerStatus) => void): void;
  queryMemory(filter: MemoryFilter): Promise<QueryResult>;
  queryEvents(filter: EventFilter): Promise<QueryResult>;
}
```

### DashboardConfig

```python
@dataclass
class DashboardConfig:
    enabled: bool = True
    port: int = 8765
    host: str = "127.0.0.1"
    broadcast_interval_ms: int = 100
    event_buffer_size: int = 100
    state_broadcast_interval_ms: int = 1000
```

---

## 6. Acceptance Criteria

1. Dashboard connects to the runtime via WebSocket and displays a "Connected" status.
2. Events published to the EventBus appear in the EventFeed within 100ms.
3. EventFeed filters by event type — selecting "dom_changed" hides all other events.
4. EventFeed filters by source — selecting "chromium" shows only chromium events.
5. MemoryInspector displays all current memory entries with key, value, namespace, and TTL.
6. MemoryInspector search filters entries by key prefix in real-time.
7. DriverStatusCard shows each driver's state, latency, and error count.
8. DriverStatusCard highlights unhealthy drivers with a visual indicator.
9. SchedulerView shows pending event counts per priority level.
10. Dashboard updates without manual refresh — all views are live.
11. Dashboard handles WebSocket disconnection gracefully (shows "Reconnecting" status).
12. Dashboard reconnects automatically when the runtime comes back online.
13. Dashboard runs independently — can be developed and tested without a running runtime (with mock data).
14. Dashboard works in Chrome, Firefox, and Safari on desktop.
15. WebSocket server rejects any message that attempts to modify runtime state.
16. Dashboard contains no driver-specific, memory-specific, or scheduler-specific business logic — it only displays data.

---

## 7. Future Extensions

1. **Historical event view.** Browse events from the past hour/day/week. Requires event persistence.

2. **Metrics dashboard.** Display event throughput, memory usage, scheduler latency over time. Requires metrics collection.

3. **Configuration editor.** Edit runtime configuration from the dashboard. Requires write-back support.

4. **Log viewer.** Stream application logs to the dashboard. Requires structured logging integration.

5. **Multi-runtime view.** Connect to multiple runtime instances and compare their state side by side.

6. **Event flow diagram.** Visualize event propagation through the runtime as a graph. Show which subsystems produce and consume each event type.

7. **Memory diff view.** Compare two snapshots of memory to see what changed between them.

8. **Driver action log.** Show a history of actions sent to each driver and their results.

9. **Mobile responsive.** Adapt the layout for tablet and mobile browsers.

10. **Dark mode.** Support light and dark themes.

11. **Export.** Export event history, memory state, or driver status as JSON or CSV.

12. **Keyboard shortcuts.** Navigate between views, filter events, and search memory using keyboard shortcuts.

---

## 8. Open Questions

1. Should the WebSocket server use a library like `websockets` or `fastapi` with WebSocket support?

2. Should the dashboard be bundled with the Python package or served as a separate static build?

3. Should the dashboard have a health endpoint (`/health`) for monitoring?

4. Should the WebSocket server support multiple concurrent clients, or is one client sufficient for v0.1?

5. Should the dashboard auto-scroll the event feed, or let the user control scrolling?

6. Should the dashboard show the full event payload as JSON, or attempt to render known payload structures?

7. Should the WebSocket server compress messages (permessage-deflate) to reduce bandwidth?

8. Should the dashboard have a "pause events" button that temporarily stops the UI from updating (but events continue in the runtime)?

---

*Document created: 2026-07-26*
*Last updated: 2026-07-26*
