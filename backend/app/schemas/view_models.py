"""Composite read models assembled for board and board-group views."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from uuid import UUID  # noqa: TCH003

from sqlmodel import Field, SQLModel

from app.schemas.agents import AgentRead  # noqa: TCH001
from app.schemas.approvals import ApprovalRead  # noqa: TCH001
from app.schemas.board_groups import BoardGroupRead  # noqa: TCH001
from app.schemas.board_memory import BoardMemoryRead  # noqa: TCH001
from app.schemas.boards import BoardRead  # noqa: TCH001
from app.schemas.tasks import TaskRead


class TaskCardRead(TaskRead):
    """Task read model enriched with assignee and approval counters."""

    assignee: str | None = None
    approvals_count: int = 0
    approvals_pending_count: int = 0


class BoardSnapshot(SQLModel):
    """Aggregated board payload used by board snapshot endpoints."""

    board: BoardRead
    tasks: list[TaskCardRead]
    agents: list[AgentRead]
    approvals: list[ApprovalRead]
    chat_messages: list[BoardMemoryRead]
    pending_approvals_count: int = 0


class BoardGroupTaskSummary(SQLModel):
    """Task summary row used inside board-group snapshot responses."""

    id: UUID
    board_id: UUID
    board_name: str
    title: str
    status: str
    priority: str
    assigned_agent_id: UUID | None = None
    assignee: str | None = None
    due_at: datetime | None = None
    in_progress_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BoardGroupBoardSnapshot(SQLModel):
    """Board-level rollup embedded within a board-group snapshot."""

    board: BoardRead
    task_counts: dict[str, int] = Field(default_factory=dict)
    tasks: list[BoardGroupTaskSummary] = Field(default_factory=list)


class BoardGroupSnapshot(SQLModel):
    """Top-level board-group snapshot response payload."""

    group: BoardGroupRead | None = None
    boards: list[BoardGroupBoardSnapshot] = Field(default_factory=list)
