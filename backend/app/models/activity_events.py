"""Activity event model persisted for audit and feed use-cases."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel


class ActivityEvent(QueryModel, table=True):
    """Discrete activity event tied to tasks and agents."""

    __tablename__ = "activity_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_type: str = Field(index=True)
    message: str | None = None
    agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)
    task_id: UUID | None = Field(default=None, foreign_key="tasks.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
