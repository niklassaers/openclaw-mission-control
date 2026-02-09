"""Schemas for board create/update/read API operations."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from typing import Self
from uuid import UUID  # noqa: TCH003

from pydantic import model_validator
from sqlmodel import SQLModel

_ERR_GOAL_FIELDS_REQUIRED = (
    "Confirmed goal boards require objective and success_metrics"
)
_ERR_GATEWAY_REQUIRED = "gateway_id is required"


class BoardBase(SQLModel):
    """Shared board fields used across create and read payloads."""

    name: str
    slug: str
    gateway_id: UUID | None = None
    board_group_id: UUID | None = None
    board_type: str = "goal"
    objective: str | None = None
    success_metrics: dict[str, object] | None = None
    target_date: datetime | None = None
    goal_confirmed: bool = False
    goal_source: str | None = None


class BoardCreate(BoardBase):
    """Payload for creating a board."""

    gateway_id: UUID

    @model_validator(mode="after")
    def validate_goal_fields(self) -> Self:
        """Require goal details when creating a confirmed goal board."""
        if (
            self.board_type == "goal"
            and self.goal_confirmed
            and (not self.objective or not self.success_metrics)
        ):
            raise ValueError(_ERR_GOAL_FIELDS_REQUIRED)
        return self


class BoardUpdate(SQLModel):
    """Payload for partial board updates."""

    name: str | None = None
    slug: str | None = None
    gateway_id: UUID | None = None
    board_group_id: UUID | None = None
    board_type: str | None = None
    objective: str | None = None
    success_metrics: dict[str, object] | None = None
    target_date: datetime | None = None
    goal_confirmed: bool | None = None
    goal_source: str | None = None

    @model_validator(mode="after")
    def validate_gateway_id(self) -> Self:
        """Reject explicit null gateway IDs in patch payloads."""
        # Treat explicit null like "unset" is invalid for patch updates.
        if "gateway_id" in self.model_fields_set and self.gateway_id is None:
            raise ValueError(_ERR_GATEWAY_REQUIRED)
        return self


class BoardRead(BoardBase):
    """Board payload returned from read endpoints."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime
