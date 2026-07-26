"""Action type definitions for the Artax runtime.

Actions represent commands issued to drivers. Each action has a type, optional
target, payload, and timeout. Results carry success status, output data, and
error information.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from ..scheduler.core import Priority


class ActionType(enum.Enum):
    """Enumeration of all supported action types.

    Drivers may support a subset of these types. Custom action types can be
    added by extending this enum in downstream projects.
    """

    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    EXECUTE_SCRIPT = "execute_script"
    WAIT = "wait"
    CUSTOM = "custom"


@dataclass(frozen=True)
class Action:
    """A command to be executed by a driver.

    Attributes:
        id: Unique identifier for this action instance.
        type: The kind of action to perform.
        target: Optional selector or identifier for the action target.
        payload: Arbitrary data required by the action type.
        timeout: Maximum duration to wait for action completion.

    """

    id: uuid.UUID
    type: ActionType
    target: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))


@dataclass(frozen=True)
class ActionResult:
    """Outcome of an action execution.

    Attributes:
        action_id: The identifier of the action that produced this result.
        success: Whether the action completed without error.
        data: Arbitrary output data from the action.
        error: Human-readable error message if the action failed.
        duration: Wall-clock time taken to execute the action.

    """

    action_id: uuid.UUID
    success: bool
    data: Any = None
    error: str | None = None
    duration: timedelta = field(default_factory=timedelta)


@dataclass(frozen=True)
class Intent:
    """A high-level goal composed of a sequence of actions.

    Intents represent user or agent intentions that require multiple
    atomic actions to fulfill.

    Attributes:
        description: Natural language description of the intent.
        actions: Ordered list of actions to execute.
        priority: Scheduling priority for the intent.

    """

    description: str
    actions: list[Action] = field(default_factory=list)
    priority: Priority = Priority.NORMAL
