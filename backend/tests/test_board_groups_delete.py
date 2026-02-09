# ruff: noqa: INP001, S101
"""Regression test for board-group delete ordering."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from app.api import board_groups

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
async def test_delete_board_group_cleans_group_memory_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delete should remove boards, memory, then the board-group record."""
    group_id = uuid4()

    async def _fake_require_group_access(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        board_groups,
        "_require_group_access",
        _fake_require_group_access,
    )

    session = _FakeSession()
    ctx = SimpleNamespace(member=object())

    await board_groups.delete_board_group(
        group_id=group_id,
        session=cast("AsyncSession", session),
        ctx=ctx,
    )

    statement_tables = [statement.table.name for statement in session.executed]
    assert statement_tables == ["boards", "board_group_memory", "board_groups"]
    assert session.committed == 1
