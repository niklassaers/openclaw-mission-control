# ruff: noqa: INP001, S101
"""Regression tests for board deletion cleanup behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from app.api import boards
from app.models.boards import Board

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

_NO_EXEC_RESULTS_ERROR = "No more exec_results left for session.exec"


@dataclass
class _FakeSession:
    exec_results: list[object]
    executed: list[object] = field(default_factory=list)
    deleted: list[object] = field(default_factory=list)
    committed: int = 0

    async def exec(self, statement: object) -> object | None:
        is_dml = statement.__class__.__name__ in {"Delete", "Update", "Insert"}
        if is_dml:
            self.executed.append(statement)
            return None
        if not self.exec_results:
            raise AssertionError(_NO_EXEC_RESULTS_ERROR)
        return self.exec_results.pop(0)

    async def execute(self, statement: object) -> None:
        self.executed.append(statement)

    async def delete(self, value: object) -> None:
        self.deleted.append(value)

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_delete_board_cleans_org_board_access_rows() -> None:
    """Deleting a board should clear org-board access rows before commit."""
    session = _FakeSession(exec_results=[[], []])
    board = Board(
        id=uuid4(),
        organization_id=uuid4(),
        name="Demo Board",
        slug="demo-board",
        gateway_id=None,
    )

    await boards.delete_board(
        session=cast("AsyncSession", session),
        board=board,
    )

    deleted_table_names = [statement.table.name for statement in session.executed]
    assert "organization_board_access" in deleted_table_names
    assert "organization_invite_board_access" in deleted_table_names
    assert board in session.deleted
    assert session.committed == 1
