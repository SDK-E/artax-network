# Task 07: Dashboard Server — Gap Analysis

**Layer:** 4 (Dashboard)
**Subsystem:** `artax.dashboard`
**Status:** Implemented with significant gaps
**PRD Reference:** `docs/prd/prd-dashboard.md`

---

## Senior Product Manager Perspective

### What the Dashboard Is Supposed to Do

The dashboard is a developer tool that provides real-time visibility into what the runtime is doing. It connects to the runtime via WebSocket and displays events, memory state, driver status, and scheduler queue in real-time. It is a read-only observer — it never accepts commands that modify runtime state.

The dashboard must:

1. **Event visualization** — Display a live feed of events flowing through the EventBus. Show event type, source, timestamp, and payload. Support filtering by type and source. Highlight high-priority and error events.

2. **Memory inspector** — Display the current contents of Working Memory. Show keys, values, namespaces, and TTLs. Support search by key prefix or namespace. Allow expanding nested values.

3. **Driver status** — Display the state of each registered driver: connected, unhealthy, error. Show driver health metrics (latency, error count, last event time). Highlight unhealthy drivers.

4. **Scheduler view** — Display the scheduler queue: pending events by priority, total scheduled/delivered/cancelled counts. Show the tick rate and whether the scheduler is paused.

5. **Real-time updates** — All views update in real-time via WebSocket. No manual refresh required. Events appear within 100ms of being published.

6. **Responsive layout** — Dashboard works on desktop browsers (Chrome, Firefox, Safari). Mobile support is not required in v0.1.

7. **Self-contained** — Dashboard is a Next.js application that runs independently of the runtime. It connects to the runtime via WebSocket URL (configurable). It can be developed and tested without a running runtime.

### What Currently Works

The `DashboardServer` implementation provides:

- **WebSocket server** — Accepts client connections over WebSocket using the `websockets` library.
- **Event broadcasting** — Receives events from the runtime's EventBus via `receive_event()` and broadcasts them to all connected clients as JSON messages.
- **Event history** — Maintains a bounded ring buffer of recent events (configurable size). New clients receive the most recent events on connect.
- **Driver tracking** — Tracks connected and unhealthy drivers by listening to `DRIVER_CONNECTED`, `DRIVER_DISCONNECTED`, and `DRIVER_UNHEALTHY` events.
- **Runtime state snapshot** — Provides `get_runtime_state()` that returns uptime, client count, event count, driver connection status, and memory key count.
- **Health endpoint** — Provides `get_health()` that returns server health status.
- **Client connection management** — Tracks connected clients, removes them on disconnect, handles connection errors gracefully.

### What Is Missing or Different From the Plan

**Gap 1: DashboardServer constructor does not match PRD spec**

The PRD specifies:
```
DashboardServer(port, event_bus, memory, scheduler, drivers)
```

The implementation takes only `config: DashboardConfig | None = None`. It does not receive direct references to `event_bus`, `memory`, `scheduler`, or `drivers`. Instead, it receives events indirectly via `receive_event()` which is called by the runtime. This is a significant architectural difference:

- The PRD envisions the dashboard subscribing to the EventBus, querying memory, querying the scheduler, and querying drivers directly.
- The implementation relies on the runtime to push events to the dashboard via `receive_event()`.
- The dashboard cannot query memory contents, scheduler state, or driver health on demand — it only receives what the runtime pushes.

This means the dashboard is a passive observer that depends on the runtime to feed it data, rather than an active participant that can query subsystems directly.

**Gap 2: No client message handling**

The PRD specifies a WebSocket protocol where clients can send query messages:
- `query_memory` — Query memory entries by namespace and key prefix
- `query_events` — Query event history by type and limit
- `query_drivers` — Get driver status
- `control` — Pause/resume event display

The current implementation does not handle any client messages. The `_handle_client()` method just listens for the connection to close (`async for _ in ws: pass`). All client messages are silently ignored.

**Gap 3: No periodic state broadcast**

The PRD specifies that the dashboard should broadcast state updates periodically (every 100ms for events, every 1000ms for state). The current implementation only broadcasts events when they are received via `receive_event()`. There is no periodic task that sends state snapshots to clients.

**Gap 4: No HTTP server or /health endpoint**

The PRD specifies a `/health` HTTP endpoint for monitoring and CI health checks. The current implementation only has a WebSocket server — there is no HTTP server and no `/health` endpoint. The `get_health()` method exists but is not exposed via HTTP.

**Gap 5: DashboardConfig field names differ from PRD spec**

The PRD specifies `DashboardConfig` with fields: `enabled`, `port`, `host`, `broadcast_interval_ms`, `event_buffer_size`, `state_broadcast_interval_ms`.

The implementation has: `host`, `port`, `ws_port`, `event_history_size`, `broadcast_interval_ms`.

Differences:
- Missing `enabled` field
- Missing `state_broadcast_interval_ms` field
- `event_buffer_size` vs `event_history_size` — different name for the same concept
- Extra `ws_port` field not in PRD spec

**Gap 6: No read-only validation for incoming messages**

The PRD says "The WebSocket server is read-only — it never accepts commands that modify runtime state." The current implementation does not validate incoming messages at all — it simply ignores them. While ignoring messages is effectively read-only, the PRD implies the server should explicitly reject state-modifying commands with an error response.

**Gap 7: No pause/resume event display support**

The PRD specifies a pause events button as essential UX for debugging. The current implementation has no concept of pausing event delivery to clients. Events continue to be broadcast regardless of client state.

**Gap 8: No support for multiple concurrent clients with independent state**

The PRD says "Multiple concurrent clients" should be supported. The current implementation does support multiple clients (it maintains a set of connected clients and broadcasts to all). However, there is no per-client state management — all clients receive the same event stream and state snapshots. The PRD implies clients should be able to independently filter events, pause their display, and query memory.

**Gap 9: The dashboard does not implement the full WebSocket protocol defined in the PRD**

The PRD defines a specific JSON message protocol:

Server → Client:
- `event` — broadcast events
- `state` — periodic state updates
- `driver_status` — driver status changes
- `scheduler_status` — scheduler queue updates
- `query_result` — response to client queries
- `error` — error messages

Client → Server:
- `query_memory` — query memory entries
- `query_events` — query event history
- `query_drivers` — get driver status
- `control` — pause/resume

The current implementation only sends `event` and `state` messages (via `receive_event()` and `get_runtime_state()`). It does not implement the full protocol.

### Acceptance Criteria (What Needs to Pass)

1. Dashboard connects to the runtime via WebSocket and displays a "Connected" status
2. Events published to the EventBus appear in the EventFeed within 100ms
3. EventFeed filters by event type — selecting "dom_changed" hides all other events
4. EventFeed filters by source — selecting "chromium" shows only chromium events
5. MemoryInspector displays all current memory entries with key, value, namespace, and TTL
6. MemoryInspector search filters entries by key prefix in real-time
7. DriverStatusCard shows each driver's state, latency, and error count
8. DriverStatusCard highlights unhealthy drivers with a visual indicator
9. SchedulerView shows pending event counts per priority level
10. Dashboard updates without manual refresh — all views are live
11. Dashboard handles WebSocket disconnection gracefully (shows "Reconnecting" status)
12. Dashboard reconnects automatically when the runtime comes back online
13. Dashboard runs independently — can be developed and tested without a running runtime (with mock data)
14. Dashboard works in Chrome, Firefox, and Safari on desktop
15. WebSocket server rejects any message that attempts to modify runtime state (MISSING — no message handling at all)
16. Dashboard contains no driver-specific, memory-specific, or scheduler-specific business logic — it only displays data

---

## Senior Engineer Perspective

### Architecture Assessment

The dashboard server is a minimal but functional WebSocket server. It accepts connections, receives events from the runtime, maintains event history, tracks driver state, and broadcasts to clients. The architecture is simple and correct for a v0.1 implementation.

However, the server is fundamentally passive — it only reacts to events pushed by the runtime. It does not actively query subsystems, handle client requests, or manage per-client state. This is a significant architectural limitation compared to the PRD's vision.

Key design decisions that were correctly implemented:

- WebSocket server using the `websockets` library
- Event broadcasting to all connected clients
- Event history ring buffer for new client catch-up
- Driver state tracking from EventBus events
- Graceful client connection/disconnection handling
- JSON message serialization

### Critical Gaps

1. **No client message handling.** The server ignores all incoming WebSocket messages. This means:
   - Clients cannot query memory state on demand
   - Clients cannot query event history with filters
   - Clients cannot query driver status
   - Clients cannot pause/resume event display
   - The server cannot reject state-modifying commands

2. **No periodic state broadcast.** The server only sends state when events arrive. There is no periodic task that sends scheduler status, driver health, or memory state updates. This means the dashboard is event-driven only — it cannot show scheduler queue depth or driver health when no events are occurring.

3. **No HTTP server.** The PRD specifies a `/health` endpoint. The current implementation has no HTTP server at all.

4. **DashboardServer does not own its subsystem references.** The PRD envisions the dashboard directly subscribing to EventBus, querying memory, querying scheduler, and querying drivers. The current implementation has the runtime calling `dashboard.receive_event()` instead. This creates a tighter coupling between the runtime and dashboard than the PRD intends.

### Recommended Actions

1. **Implement client message handling.** Add a message parser in `_handle_client()` that routes incoming JSON messages to handlers based on message type. At minimum, support `query_memory`, `query_events`, `query_drivers`, and `control` messages.

2. **Add periodic state broadcast.** Create an asyncio task that periodically sends state snapshots (scheduler status, driver health, memory size) to all connected clients.

3. **Add HTTP server with /health endpoint.** Use a lightweight HTTP server (e.g., `aiohttp` or the `websockets` library's built-in HTTP support) to serve the `/health` endpoint.

4. **Align DashboardServer constructor with PRD.** Accept `event_bus`, `memory`, `scheduler`, and `drivers` as constructor parameters so the dashboard can query subsystems directly.

5. **Implement the full WebSocket protocol** as defined in the PRD, including all message types.

### Gap Summary

| Gap | Severity | Description |
|-----|----------|-------------|
| No client message handling | HIGH | Server ignores all incoming WebSocket messages |
| No periodic state broadcast | HIGH | Dashboard only updates on events, not on timer |
| No HTTP server or /health endpoint | MEDIUM | PRD specifies /health endpoint; not implemented |
| DashboardServer constructor mismatch | MEDIUM | PRD expects event_bus/memory/scheduler/drivers; implementation takes only config |
| DashboardConfig field names differ | LOW | Some fields renamed or missing vs PRD spec |
| No pause/resume event display | MEDIUM | PRD specifies pause button; not implemented |
| No read-only message validation | MEDIUM | PRD says reject state-modifying commands; server ignores all messages instead |
| No full WebSocket protocol implementation | MEDIUM | Only event and state messages implemented; missing driver_status, scheduler_status, query_result, error |
