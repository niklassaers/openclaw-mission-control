"""Schemas for approval create/update/read API payloads."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from typing import Literal, Self
from uuid import UUID  # noqa: TCH003

from pydantic import model_validator
from sqlmodel import SQLModel

ApprovalStatus = Literal["pending", "approved", "rejected"]
STATUS_REQUIRED_ERROR = "status is required"


class ApprovalBase(SQLModel):
    """Shared approval fields used across create/read payloads."""

    action_type: str
    task_id: UUID | None = None
    payload: dict[str, object] | None = None
    confidence: int
    rubric_scores: dict[str, int] | None = None
    status: ApprovalStatus = "pending"


class ApprovalCreate(ApprovalBase):
    """Payload for creating a new approval request."""

    agent_id: UUID | None = None


class ApprovalUpdate(SQLModel):
    """Payload for mutating approval status."""

    status: ApprovalStatus | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        """Ensure explicitly provided `status` is not null."""
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError(STATUS_REQUIRED_ERROR)
        return self


class ApprovalRead(ApprovalBase):
    """Approval payload returned from read endpoints."""

    id: UUID
    board_id: UUID
    agent_id: UUID | None = None
    created_at: datetime
    resolved_at: datetime | None = None
