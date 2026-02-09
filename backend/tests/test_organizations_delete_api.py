# ruff: noqa: INP001, S101
"""Tests for organization deletion API behavior and authorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.api import organizations

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass
class _FakeSession:
    executed: list[object] = field(default_factory=list)
    committed: int = 0

    async def exec(self, statement: object) -> None:
        self.executed.append(statement)

    async def execute(self, statement: object) -> None:
        self.executed.append(statement)

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_delete_my_org_cleans_dependents_before_organization_delete() -> None:
    """Delete flow should remove dependent rows before the organization row."""
    session = _FakeSession()
    org_id = uuid4()
    ctx = SimpleNamespace(
        organization=SimpleNamespace(id=org_id),
        member=SimpleNamespace(role="owner"),
    )

    await organizations.delete_my_org(
        session=cast("AsyncSession", session),
        ctx=ctx,
    )

    executed_tables = [statement.table.name for statement in session.executed]
    assert executed_tables == [
        "activity_events",
        "activity_events",
        "task_dependencies",
        "task_fingerprints",
        "approvals",
        "board_memory",
        "board_onboarding_sessions",
        "organization_board_access",
        "organization_invite_board_access",
        "organization_board_access",
        "organization_invite_board_access",
        "tasks",
        "agents",
        "boards",
        "board_group_memory",
        "board_groups",
        "gateways",
        "organization_invites",
        "organization_members",
        "users",
        "organizations",
    ]
    assert session.committed == 1


@pytest.mark.asyncio
async def test_delete_my_org_requires_owner_role() -> None:
    """Delete flow should reject non-owner members with HTTP 403."""
    session = _FakeSession()
    ctx = SimpleNamespace(
        organization=SimpleNamespace(id=uuid4()),
        member=SimpleNamespace(role="admin"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await organizations.delete_my_org(
            session=cast("AsyncSession", session),
            ctx=ctx,
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert session.executed == []
    assert session.committed == 0
