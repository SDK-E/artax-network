from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    """A command to be executed by a driver.

    Attributes:
        action_id: Unique identifier for this action instance (hex string).
        name: Action name — free-form string, not restricted to an enum.
        target: Optional selector or identifier for the action target.
        parameters: Arbitrary parameters required by the action.
        timestamp: Monotonic timestamp when the action was created.

    """

    name: str
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    target: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


@dataclass(frozen=True)
class ActionResult:
    """Outcome of an action execution.

    Attributes:
        action_id: The identifier of the action that produced this result.
        success: Whether the action completed without error.
        data: Arbitrary output data from the action.
        error: Human-readable error message if the action failed.
        duration_ms: Wall-clock time taken to execute the action in milliseconds.

    """

    action_id: str
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass(frozen=True)
class Intent:
    """A high-level goal composed of a sequence of actions.

    Attributes:
        description: Natural language description of the intent.
        actions: Ordered list of actions to execute.
        priority: Scheduling priority for the intent.

    """

    description: str
    actions: list[Action] = field(default_factory=list)
    priority: str = "medium"
