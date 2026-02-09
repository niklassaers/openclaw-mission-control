"""Structured error payload schemas used by API responses."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class BlockedTaskDetail(SQLModel):
    """Error detail payload listing blocking dependency task identifiers."""

    message: str
    blocked_by_task_ids: list[str] = Field(default_factory=list)


class BlockedTaskError(SQLModel):
    """Top-level blocked-task error response envelope."""

    detail: BlockedTaskDetail
