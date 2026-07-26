# Dashboard

The Artax dashboard is a web-based developer interface for observing and debugging the runtime in real time. It connects to the runtime over WebSocket and displays the live state of events, memory, drivers, and the scheduler.

## What the Dashboard Provides

The dashboard is a diagnostic tool, not a control panel. It shows you what is happening inside the runtime. It does not let you manipulate the runtime directly (that comes later).

### Real-Time Event Visualization

See events as they flow through the bus. Each event displays:

- **Topic** — the event's topic string (e.g., `chromium.dom.click`)
- **Source** — which driver or subsystem produced it
- **Priority** — importance level (0-9)
- **Timestamp** — when the event was created
- **Data** — the event's payload (expandable)

Events are displayed in a scrolling feed, newest first. You can filter by topic, source, and priority.

### Memory Inspector

View the contents of working memory. The inspector shows:

- **Event count** — how many events are in memory
- **Capacity** — maximum memory size
- **Eviction stats** — how many events have been evicted
- **Event details** — click any event to see its full data

The memory inspector updates in real time as events are stored and evicted.

### Driver Status

A panel showing all registered drivers and their current state:

| Field | Description |
|---|---|
| Driver ID | Unique identifier |
| Driver Type | Kind of driver (chromium, terminal, etc.) |
| Status | Connected, Observing, Disconnected |
| Health | Healthy, Degraded, Unhealthy |
| Events Emitted | Total events produced |
| Actions Executed | Total actions completed |
| Last Event | Time since last event |

Driver status updates in real time as the runtime operates.

### Scheduler State

View the scheduler's current state:

- **Queue depth** — events waiting to be processed
- **Tick count** — total ticks processed
- **Current priority** — priority of the event being processed
- **Pause state** — whether the scheduler is paused
- **Action rate** — actions per second

## Architecture

The dashboard is a separate process from the runtime. It communicates exclusively through WebSocket.

```
┌──────────────┐     WebSocket     ┌──────────────┐
│   Dashboard  │ ←──────────────→ │    Runtime    │
│  (Next.js)   │                   │  (Python)     │
└──────────────┘                   └──────────────┘
```

The dashboard never imports runtime code. It never shares memory with the runtime. It is a pure client that subscribes to events over WebSocket.

### WebSocket Protocol

The dashboard connects to the runtime's WebSocket server (default port 8081).

**Subscribe to events:**
```json
{"type": "subscribe", "topics": ["*"]}
```

**Event received:**
```json
{
  "type": "event",
  "topic": "chromium.dom.click",
  "source": "chromium",
  "data": {"selector": "button#submit"},
  "priority": 7,
  "timestamp": 1700000000.0,
  "event_id": "evt-abc-123"
}
```

**Memory snapshot request:**
```json
{"type": "memory.snapshot"}
```

**Memory snapshot response:**
```json
{
  "type": "memory.snapshot",
  "events": [...],
  "capacity": 1000,
  "size": 42
}
```

**Driver status request:**
```json
{"type": "drivers.status"}
```

**Driver status response:**
```json
{
  "type": "drivers.status",
  "drivers": [
    {
      "driver_id": "chromium",
      "driver_type": "chromium",
      "status": "observing",
      "health": "healthy",
      "events_emitted": 1234,
      "actions_executed": 56
    }
  ]
}
```

## Configuration

The dashboard is configured through environment variables:

| Variable | Default | Description |
|---|---|---|
| `ARTAX_DASHBOARD_PORT` | `3000` | Dashboard dev server port |
| `ARTAX_WS_PORT` | `8081` | WebSocket port for runtime connection |

### Development Mode

In development mode, the dashboard runs with hot reload:

```bash
make dashboard
```

This starts the Next.js development server at `http://localhost:3000`.

### Production Build

For production, build and serve the static files:

```bash
make dashboard-install
make dashboard-build
```

The built files are in `dashboard/out/`. Serve them with any static file server or reverse proxy.

## Features

### Event Feed

The main view shows a live feed of events. Events appear in real time as they flow through the bus.

- **Auto-scroll:** The feed scrolls to the newest event automatically. Pause auto-scroll by scrolling up manually.
- **Filter by topic:** Type a topic pattern to filter events. Use `*` as a wildcard.
- **Filter by source:** Select a driver or subsystem to see only its events.
- **Filter by priority:** Set a minimum priority to hide low-priority events.
- **Expand/collapse:** Click an event to see its full data payload.

### Memory View

The memory view shows the current contents of working memory.

- **Event list:** All events currently in memory, sorted by timestamp.
- **Event detail:** Click an event to see its full data, metadata, and evicton score.
- **Capacity bar:** Visual indicator of memory usage.
- **Clear button:** Clear all events from memory (for debugging).

### Driver Panel

The driver panel shows all registered drivers and their real-time status.

- **Health indicators:** Green (healthy), yellow (degraded), red (unhealthy).
- **Event counter:** Total events emitted by each driver.
- **Action counter:** Total actions executed by each driver.
- **Last activity:** Time since the driver's last event.

### Scheduler Panel

The scheduler panel shows timing and queue information.

- **Queue depth:** Number of events waiting to be processed.
- **Tick counter:** Total ticks processed since startup.
- **Action rate:** Actions per second over the last minute.
- **Pause indicator:** Whether the scheduler is currently paused.

### Log Viewer

A filtered view of runtime log messages. Useful for debugging alongside the event feed.

- **Log level filter:** Show only errors, warnings, or all messages.
- **Search:** Full-text search across log messages.
- **Timestamp:** Each log entry includes its timestamp.

## Limitations (v0.1)

The v0.1 dashboard is an alpha release. Current limitations:

- No authentication (development tool only).
- No persistent event history (live feed only).
- No action execution from the dashboard (view-only).
- No configuration editing.
- No user accounts or multi-user support.

These will be addressed in future releases.
