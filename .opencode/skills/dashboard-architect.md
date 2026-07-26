# Dashboard Architect

## Purpose

Expert in designing the observational dashboard for human operators. Dashboard exists for humans and must never block Runtime execution.

## Responsibilities

- Design dashboard UI components and layouts
- Implement WebSocket-based real-time updates
- Visualize runtime state, events, and working memory
- Ensure dashboard remains observational only
- Maintain separation from runtime execution

## Constraints

- **MUST** communicate via WebSocket only
- **MUST NOT** block runtime execution
- **MUST NOT** influence runtime decisions
- **MUST NOT** import runtime internals
- **MUST** be observational only
- **MUST** use Next.js and TypeScript

## Inputs

- Visualization requirements (event timeline, memory state, etc.)
- WebSocket API specifications
- UI/UX design requirements
- Performance requirements for real-time updates

## Outputs

- Dashboard components and pages
- WebSocket client implementations
- Visualization configurations
- Documentation for dashboard usage

## Decision Process

1. Identify what runtime state to visualize
2. Design WebSocket subscription patterns
3. Implement UI components
4. Ensure no runtime coupling
5. Test with mocked runtime data
6. Document dashboard capabilities

## Best Practices

- Keep dashboard as separate process
- Use WebSocket for real-time updates
- Implement efficient re-rendering
- Support multiple runtime instances
- Provide debugging views for development

## Anti-Patterns

- Importing runtime modules directly
- Blocking runtime operations
- Storing runtime state in dashboard
- Making decisions that affect runtime
- Creating tight coupling with runtime

## Example

```typescript
// GOOD: Dashboard observes via WebSocket
const useRuntimeEvents = () => {
  const [events, setEvents] = useState<Event[]>([]);
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8081');
    ws.onmessage = (msg) => {
      setEvents(prev => [...prev, JSON.parse(msg.data)]);
    };
    return () => ws.close();
  }, []);
  
  return events;
};

// BAD: Dashboard imports runtime
import { Runtime } from 'artax/runtime'; // VIOLATION
```

## Related Skills

- `runtime-architect` — for understanding runtime state
- `event-designer` — for event visualization
- `architecture-guardian` — for reviewing dashboard isolation
- `testing-architect` — for dashboard testing

## Invocation

Use when:
- Designing new dashboard components
- Adding real-time visualization features
- Implementing WebSocket subscriptions
- Reviewing dashboard-runtime boundaries
