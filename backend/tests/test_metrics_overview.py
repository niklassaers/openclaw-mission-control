from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.api import metrics as metrics_api
from app.models.boards import Board
from app.models.gateways import Gateway


class _ExecAllResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _SequentialSession:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self._index = 0

    async def exec(self, _statement: object) -> Any:
        response = self._responses[self._index]
        self._index += 1
        return response


class _SimpleSession:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    async def exec(self, _statement: object) -> _ExecAllResult:
        return _ExecAllResult(self._rows)


@pytest.mark.asyncio
async def test_agent_task_counts_filters_unknown_statuses() -> None:
    agent_id = uuid4()
    session = _SimpleSession(
        [
            (agent_id, "in_progress", 3),
            (agent_id, "blocked", 5),
        ],
    )

    counts = await metrics_api._agent_task_counts(session, [uuid4()])

    assert counts[agent_id]["in_progress"] == 3
    assert "blocked" not in counts[agent_id]


def test_agent_workload_summary_aggregates_counts() -> None:
    agents = [
        metrics_api.AgentWorkloadAgent(
            agent_id=uuid4(),
            board_id=uuid4(),
            board_name="ops",
            name="Recon",
            status="online",
            last_seen_at=None,
            task_counts=metrics_api.AgentWorkloadTaskCounts(
                inbox=1, in_progress=2, review=0, done=1
            ),
        ),
        metrics_api.AgentWorkloadAgent(
            agent_id=uuid4(),
            board_id=uuid4(),
            board_name="ops",
            name="Alpha",
            status="offline",
            last_seen_at=None,
            task_counts=metrics_api.AgentWorkloadTaskCounts(
                inbox=0, in_progress=1, review=1, done=0
            ),
        ),
    ]

    summary = metrics_api._agent_workload_summary_from_agents(agents)

    assert summary.total_agents == 2
    assert summary.online_agents == 1
    assert summary.assigned_tasks == 6
    assert summary.review_tasks == 1


def test_cron_items_respects_items_key() -> None:
    payload = {"items": [{"id": "primary"}], "jobs": [{"id": "secondary"}]}

    items = metrics_api._cron_items(payload)

    assert len(items) == 1
    assert items[0]["id"] == "primary"


def test_build_calendar_event_returns_event_for_matching_board() -> None:
    board_id = uuid4()
    board = Board(
        id=board_id,
        organization_id=uuid4(),
        name="Ops",
        slug="ops",
        description="",
        gateway_id=uuid4(),
    )
    gateway = Gateway(
        id=board.gateway_id,
        organization_id=board.organization_id,
        name="gw",
        url="https://gateway",
        workspace_root="/root",
    )
    entry = {
        "id": "cron-1",
        "board_id": str(board_id),
        "name": "Daily",
        "schedule": "0 0 * * *",
    }

    event = metrics_api._build_calendar_event(entry, {str(board_id): board}, gateway)

    assert event is not None
    assert event.board_name == "Ops"
    assert event.gateway_name == "gw"
    assert event.schedule == "0 0 * * *"


@pytest.mark.asyncio
async def test_collect_calendar_events_includes_warning_for_missing_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board_id = uuid4()
    gateway_id = uuid4()
    org_id = uuid4()
    board = Board(
        id=board_id,
        organization_id=org_id,
        name="Ops",
        slug="ops",
        description="",
        gateway_id=gateway_id,
    )
    gateway = Gateway(
        id=gateway_id,
        organization_id=org_id,
        name="gw",
        url="https://gateway",
        workspace_root="/root",
    )
    session = _SequentialSession(
        [
            _ExecAllResult([board]),
            _ExecAllResult([gateway]),
        ]
    )

    async def fake_openclaw_call(method: str, *, config: object | None = None) -> dict[str, Any]:
        assert method == "cron.list"
        return {"items": [{"id": "cron-1", "board_id": str(board_id)}]}

    monkeypatch.setattr(metrics_api, "openclaw_call", fake_openclaw_call)

    events, warnings = await metrics_api._collect_calendar_events(session, [board_id])

    assert any(w.board_id == board_id for w in warnings) is False
    assert len(events) == 1
    assert events[0].id == "cron-1"
