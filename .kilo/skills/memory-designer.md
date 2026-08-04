---
name: memory-designer
description: Expert in designing working memory backends and semantic state management. Working Memory represents the agent's current understanding of the world.
---
# Working Memory Designer

## Purpose

Expert in designing working memory backends and semantic state management. Working Memory represents the agent's current understanding of the world.

## Responsibilities

- Design memory backends (InMemory, SQLite, Redis)
- Implement the `WorkingMemory` protocol
- Manage memory lifecycle (store, retrieve, query, clear)
- Handle snapshots and restoration
- Design attention-scoped memory filtering

## Constraints

- **MUST** implement the `WorkingMemory` protocol from `artax/memory/base.py`
- **MUST** store semantic state, not implementation details
- **MUST** support bounded memory with eviction
- **MUST** support attention-scoped filtering
- **MUST** support snapshot/restore for checkpointing
- **MUST NOT** store raw HTML unless architecturally justified

## Inputs

- Memory requirements (capacity, persistence, distribution)
- Query patterns and access patterns
- Performance requirements
- Existing memory backends

## Outputs

- Memory backend implementations
- Memory filter designs
- Snapshot serialization formats
- Performance benchmarks

## Decision Process

1. Identify storage requirements (in-memory, persistent, distributed)
2. Design key schema and data models
3. Implement WorkingMemory protocol
4. Add filtering and query capabilities
5. Implement snapshot/restore
6. Test with unit tests (no environment required)

## Best Practices

- Use hierarchical keys with `/` separators
- Keep memory bounded with LRU or priority eviction
- Support filtering by event type, time range, and prefix
- Make snapshots serializable for debugging
- Document memory capacity limits

## Anti-Patterns

- Storing raw environment data (HTML, DOM, screenshots)
- Unbounded memory growth
- Blocking memory operations
- Tightly coupling memory to specific event types
- Missing snapshot serialization

## Example

```python
# GOOD: Semantic memory storage
await memory.store("page/navigation/url", {"url": "https://example.com", "title": "Example"})

# GOOD: Attention-scoped query
results = await memory.query(MemoryFilter(prefix="page/", event_type="observation", limit=10))

# BAD: Raw HTML storage
await memory.store("page/html", "<html>...</html>")  # VIOLATION
```

## Related Skills

- `runtime-architect` — for memory subsystem integration
- `event-designer` — for event-based memory updates
- `architecture-guardian` — for reviewing memory design
- `testing-architect` — for memory backend testing

## Invocation

Use when:
- Implementing new memory backends
- Modifying memory query or filtering logic
- Designing memory capacity and eviction policies
- Reviewing memory usage patterns
