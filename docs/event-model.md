# Event System Deep Dive

The event system is the backbone of Artax. Every interaction within the runtime — observations, actions, state changes, errors — flows through the event bus. There are no exceptions.

## Event Lifecycle

An event passes through four stages:

```
1. Creation     → Event object instantiated with type, topic, data
2. Publishing   → Event submitted to the EventBus
3. Delivery     → EventBus routes event to subscribers
4. Processing   → Subscribers handle the event (store, react, display)
```

After processing, the event may be:

- **Stored** in working memory for the agent to reason over.
- **Logged** to disk for debugging and replay.
- **Displayed** on the dashboard for human observation.
- **Discarded** if no subscriber cares about it.

Events are not deleted after processing. They persist in memory until evicted by the memory subsystem's capacity policy.

## Event Types and When to Use Them

Artax defines several event types, each serving a specific role in the runtime:

### SemanticEvent

The primary event type. A `SemanticEvent` carries structured, parsed meaning extracted from raw environment data.

```python
@dataclass(frozen=True)
class SemanticEvent:
    topic: str  # e.g., "chromium.dom.click"
    data: dict[str, Any]  # structured payload
    source: str  # driver ID that emitted this event
    timestamp: float  # time.time() when created
    event_id: str  # unique identifier
    priority: int  # 0 = lowest, 9 = highest
```

**When to use:** Every observation from a driver that has been parsed into structured meaning. A button click. A terminal output line. A sensor reading with units. This is the event type the agent reasons over.

### ActionEvent

An event representing an action the runtime wants a driver to execute.

```python
@dataclass(frozen=True)
class ActionEvent:
    target: str  # driver ID to execute this action
    action_type: str  # e.g., "click", "type", "navigate"
    parameters: dict[str, Any]  # action-specific data
    timestamp: float
    event_id: str
    priority: int
```

**When to use:** When the agent produces an action that should be executed in an environment. Action events flow through the bus to the target driver.

### SystemEvent

Internal runtime events — lifecycle signals, errors, status changes.

```python
@dataclass(frozen=True)
class SystemEvent:
    event_type: str  # "driver.connected", "driver.error", "runtime.tick"
    data: dict[str, Any]
    timestamp: float
    event_id: str
```

**When to use:** For runtime-internal communication. Driver connection/disconnection. Runtime start/stop. Error conditions. System events are not stored in working memory — they are operational signals.

### HeartbeatEvent

Periodic signals indicating subsystem health.

```python
@dataclass(frozen=True)
class HeartbeatEvent:
    source: str  # subsystem identifier
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: float
    metadata: dict[str, Any]
```

**When to use:** Drivers and subsystems emit heartbeats at configured intervals. The dashboard uses heartbeats to display health status. The scheduler can use heartbeats to detect stalled drivers.

## Semantic Events vs Raw Events

### Raw Events

Raw events are unprocessed observations directly from the environment. A raw event from the Chromium driver might be:

```json
{"type": "dom_mutation", "target": "button#submit", "mutation_type": "attribute_change", "attribute": "disabled", "old_value": "true", "new_value": "false"}
```

Raw events carry low-level details. They are useful for debugging but not for agent reasoning.

### Semantic Events

Semantic events are parsed, structured representations of what the observation means. The same observation as a semantic event:

```json
{"topic": "chromium.dom.element.enabled", "data": {"selector": "button#submit", "label": "Submit", "enabled": true}, "source": "chromium", "priority": 5}
```

The driver is responsible for converting raw observations into semantic events. The runtime never interprets raw data. The agent reasons over semantic events.

### Why the Distinction

- **Raw events** are environment-specific. A DOM mutation looks different from a terminal output. A sensor reading looks different from a game state.
- **Semantic events** are environment-agnostic. An "element enabled" event carries the same meaning regardless of whether it came from Chromium, a terminal, or a robot.
- The driver bridges the gap. It understands the raw format and produces semantic events the runtime can route generically.

## Event Filtering

Subscribers do not receive every event on the bus. Events are routed by topic.

### Topic Structure

Topics follow a hierarchical dot-notation:

```
<driver>.<subsystem>.<event>
```

Examples:

| Topic | Meaning |
|---|---|
| `chromium.dom.click` | User clicked an element in Chromium |
| `chromium.dom.mutation` | DOM structure changed |
| `chromium.navigation` | Page navigation occurred |
| `terminal.output` | Terminal produced output |
| `terminal.exit` | Terminal process exited |
| `scheduler.tick` | Scheduler completed a tick |
| `runtime.start` | Runtime started |
| `runtime.stop` | Runtime stopped |

### Subscription Patterns

Subscribers can subscribe to specific topics or topic prefixes:

```python
# Exact topic
bus.subscribe("chromium.dom.click", handler)

# Prefix (all chromium DOM events)
bus.subscribe("chromium.dom.*", handler)

# All events from chromium
bus.subscribe("chromium.*", handler)

# All events
bus.subscribe("*", handler)
```

### Filtering in Practice

The working memory subscribes to specific event types based on the agent's current attention scope. The dashboard subscribes to everything for display. The logger subscribes to error events.

## Event Bus Patterns

### Publish-Subscribe

The primary pattern. A producer publishes an event. Zero or more consumers receive it asynchronously.

```python
await bus.publish(
    SemanticEvent(
        topic="chromium.dom.click",
        data={"selector": "button#submit"},
        source="chromium",
        timestamp=time.time(),
        event_id=str(uuid4()),
        priority=5,
    )
)
```

### Request-Response (via Events)

Not a native pattern, but achievable. Publisher emits an event with a correlation ID. Subscriber emits a response event with the same correlation ID. The publisher waits for the response event.

This is discouraged for most use cases. Use direct method calls (through protocols) for synchronous operations. Reserve event-based request-response for cases where the response may arrive after a long delay.

### Event Sourcing

Every event is logged. The event log is the source of truth. State can be reconstructed by replaying events from the log.

This is a future capability. The v0.1 runtime logs events to disk. Future versions will support replay from the log for debugging and state reconstruction.

### Fan-Out

One event, many subscribers. The bus delivers the same event to all matching subscribers independently. Subscribers do not see each other's handling.

```python
# These all receive the same event independently
bus.subscribe("chromium.dom.click", memory_handler)
bus.subscribe("chromium.dom.click", dashboard_handler)
bus.subscribe("chromium.dom.click", logger_handler)
```

## Publishing Events

### From Drivers

Drivers publish events when they observe something in their environment:

```python
class ChromiumDriver:
    async def _on_dom_mutation(self, mutation: DOMMutation) -> None:
        event = SemanticEvent(
            topic="chromium.dom.mutation",
            data={
                "selector": mutation.selector,
                "type": mutation.type,
                "details": mutation.details,
            },
            source=self.driver_id,
            timestamp=time.time(),
            event_id=str(uuid4()),
            priority=self._priority_for(mutation),
        )
        await self._bus.publish(event)
```

### From the Runtime

The runtime publishes system events:

```python
await bus.publish(
    SystemEvent(
        event_type="runtime.tick",
        data={"tick_number": self._tick_count},
        timestamp=time.time(),
        event_id=str(uuid4()),
    )
)
```

### From the Agent

The agent's actions are published as ActionEvents:

```python
action = ActionEvent(
    target="chromium",
    action_type="click",
    parameters={"selector": "button#submit"},
    timestamp=time.time(),
    event_id=str(uuid4()),
    priority=7,
)
await bus.publish(action)
```

## Subscribing to Events

### Synchronous Handlers

Most handlers are async functions:

```python
async def handle_click(event: SemanticEvent) -> None:
    print(f"Button clicked: {event.data['selector']}")


bus.subscribe("chromium.dom.click", handle_click)
```

### Filtering Subscribers

Subscribers can provide a filter function for fine-grained control:

```python
async def handle_submit(event: SemanticEvent) -> None:
    if event.data.get("selector") == "button#submit":
        # process submit click
        pass


bus.subscribe("chromium.dom.click", handle_submit)
```

### Unsubscribing

```python
bus.unsubscribe("chromium.dom.click", handle_click)
```

## Future: Persistent Event Log

The v0.1 runtime logs events to disk as JSON lines. Future versions will add:

- **Log rotation** — automatic log file management.
- **Replay** — reconstruct runtime state from the event log.
- **Query** — search the event log by topic, time range, or data content.
- **Streaming** — export the event log to external systems (Kafka, RabbitMQ).
- **Compression** — compress old logs to save disk space.

The event log is append-only. Events are never modified or deleted from the log. This makes the log a reliable source of truth for debugging and auditing.
