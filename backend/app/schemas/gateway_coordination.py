"""Schemas for gateway-main and lead-agent coordination endpoints."""

from __future__ import annotations

from typing import Literal
from uuid import UUID  # noqa: TCH003

from sqlmodel import Field, SQLModel

from app.schemas.common import NonEmptyStr  # noqa: TCH001


def _lead_reply_tags() -> list[str]:
    return ["gateway_main", "lead_reply"]


def _user_reply_tags() -> list[str]:
    return ["gateway_main", "user_reply"]


class GatewayLeadMessageRequest(SQLModel):
    """Request payload for sending a message to a board lead agent."""

    kind: Literal["question", "handoff"] = "question"
    correlation_id: str | None = None
    content: NonEmptyStr

    # How the lead should reply (defaults are interpreted by templates).
    reply_tags: list[str] = Field(default_factory=_lead_reply_tags)
    reply_source: str | None = "lead_to_gateway_main"


class GatewayLeadMessageResponse(SQLModel):
    """Response payload for a lead-message dispatch attempt."""

    ok: bool = True
    board_id: UUID
    lead_agent_id: UUID | None = None
    lead_agent_name: str | None = None
    lead_created: bool = False


class GatewayLeadBroadcastRequest(SQLModel):
    """Request payload for broadcasting a message to multiple board leads."""

    kind: Literal["question", "handoff"] = "question"
    correlation_id: str | None = None
    content: NonEmptyStr
    board_ids: list[UUID] | None = None
    reply_tags: list[str] = Field(default_factory=_lead_reply_tags)
    reply_source: str | None = "lead_to_gateway_main"


class GatewayLeadBroadcastBoardResult(SQLModel):
    """Per-board result entry for a lead broadcast operation."""

    board_id: UUID
    lead_agent_id: UUID | None = None
    lead_agent_name: str | None = None
    ok: bool = False
    error: str | None = None


class GatewayLeadBroadcastResponse(SQLModel):
    """Aggregate response for a lead broadcast operation."""

    ok: bool = True
    sent: int = 0
    failed: int = 0
    results: list[GatewayLeadBroadcastBoardResult] = Field(default_factory=list)


class GatewayMainAskUserRequest(SQLModel):
    """Request payload for asking the end user via a main gateway agent."""

    correlation_id: str | None = None
    content: NonEmptyStr
    preferred_channel: str | None = None

    # How the main agent should reply back into Mission Control
    # (defaults interpreted by templates).
    reply_tags: list[str] = Field(default_factory=_user_reply_tags)
    reply_source: str | None = "user_via_gateway_main"


class GatewayMainAskUserResponse(SQLModel):
    """Response payload for user-question dispatch via gateway main agent."""

    ok: bool = True
    board_id: UUID
    main_agent_id: UUID | None = None
    main_agent_name: str | None = None
