"""Dashboard metric aggregation endpoints."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import DateTime, case
from sqlalchemy import cast as sql_cast
from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_member
from app.core.time import utcnow
from app.db.session import get_session
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.approvals import Approval
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.tasks import Task
from app.schemas.metrics import (
    AgentWorkloadAgent,
    AgentWorkloadSnapshot,
    AgentWorkloadSummary,
    AgentWorkloadTaskCounts,
    CalendarEvent,
    CalendarOverview,
    CalendarWarning,
    DashboardBucketKey,
    DashboardKpis,
    DashboardMetrics,
    DashboardPendingApproval,
    DashboardPendingApprovals,
    DashboardRangeKey,
    DashboardRangeSeries,
    DashboardSeriesPoint,
    DashboardSeriesSet,
    DashboardWipPoint,
    DashboardWipRangeSeries,
    DashboardWipSeriesSet,
)
from app.services.openclaw.gateway_resolver import gateway_client_config
from app.services.openclaw.gateway_rpc import OpenClawGatewayError, openclaw_call
from app.services.organizations import OrganizationContext, list_accessible_board_ids

router = APIRouter(prefix="/metrics", tags=["metrics"])

ERROR_EVENT_PATTERN = "%failed"
_AGENT_WORKLOAD_STATUSES = ("inbox", "in_progress", "review", "done")
_CRON_ITEM_KEYS = ("items", "jobs", "entries", "crons", "data")
_CRON_BOARD_KEYS = (
    "board_id",
    "boardId",
    "workspace_id",
    "workspaceId",
    "project_id",
    "projectId",
    "board",
)
_CRON_SCHEDULE_KEYS = ("schedule", "cron", "expression", "pattern", "value")
_CRON_ENABLED_KEYS = ("enabled", "isEnabled", "active", "flag", "run")
_RUNTIME_TYPE_REFERENCES = (UUID, AsyncSession)
RANGE_QUERY = Query(default="24h")
BOARD_ID_QUERY = Query(default=None)
GROUP_ID_QUERY = Query(default=None)
SESSION_DEP = Depends(get_session)
ORG_MEMBER_DEP = Depends(require_org_member)


@dataclass(frozen=True)
class RangeSpec:
    """Resolved time-range specification for metric aggregation."""

    key: DashboardRangeKey
    start: datetime
    end: datetime
    bucket: DashboardBucketKey
    duration: timedelta


def _resolve_range(range_key: DashboardRangeKey) -> RangeSpec:
    now = utcnow()
    specs: dict[DashboardRangeKey, tuple[timedelta, DashboardBucketKey]] = {
        "24h": (timedelta(hours=24), "hour"),
        "3d": (timedelta(days=3), "day"),
        "7d": (timedelta(days=7), "day"),
        "14d": (timedelta(days=14), "day"),
        "1m": (timedelta(days=30), "day"),
        "3m": (timedelta(days=90), "week"),
        "6m": (timedelta(days=180), "week"),
        "1y": (timedelta(days=365), "month"),
    }
    duration, bucket = specs[range_key]
    return RangeSpec(
        key=range_key,
        start=now - duration,
        end=now,
        bucket=bucket,
        duration=duration,
    )


def _comparison_range(range_spec: RangeSpec) -> RangeSpec:
    return RangeSpec(
        key=range_spec.key,
        start=range_spec.start - range_spec.duration,
        end=range_spec.end - range_spec.duration,
        bucket=range_spec.bucket,
        duration=range_spec.duration,
    )


def _bucket_start(value: datetime, bucket: DashboardBucketKey) -> datetime:
    normalized = value.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "month":
        return normalized.replace(day=1)
    if bucket == "week":
        return normalized - timedelta(days=normalized.weekday())
    if bucket == "day":
        return normalized
    return value.replace(minute=0, second=0, microsecond=0)


def _next_bucket(cursor: datetime, bucket: DashboardBucketKey) -> datetime:
    if bucket == "hour":
        return cursor + timedelta(hours=1)
    if bucket == "day":
        return cursor + timedelta(days=1)
    if bucket == "week":
        return cursor + timedelta(days=7)
    next_month = cursor.month + 1
    next_year = cursor.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    return cursor.replace(year=next_year, month=next_month, day=1)


def _build_buckets(range_spec: RangeSpec) -> list[datetime]:
    cursor = _bucket_start(range_spec.start, range_spec.bucket)
    buckets: list[datetime] = []
    while cursor <= range_spec.end:
        buckets.append(cursor)
        cursor = _next_bucket(cursor, range_spec.bucket)
    return buckets


def _series_from_mapping(
    range_spec: RangeSpec,
    mapping: dict[datetime, float],
) -> DashboardRangeSeries:
    points = [
        DashboardSeriesPoint(period=bucket, value=float(mapping.get(bucket, 0)))
        for bucket in _build_buckets(range_spec)
    ]
    return DashboardRangeSeries(
        range=range_spec.key,
        bucket=range_spec.bucket,
        points=points,
    )


def _wip_series_from_mapping(
    range_spec: RangeSpec,
    mapping: dict[datetime, dict[str, int]],
) -> DashboardWipRangeSeries:
    points: list[DashboardWipPoint] = []
    for bucket in _build_buckets(range_spec):
        values = mapping.get(bucket, {})
        points.append(
            DashboardWipPoint(
                period=bucket,
                inbox=values.get("inbox", 0),
                in_progress=values.get("in_progress", 0),
                review=values.get("review", 0),
                done=values.get("done", 0),
            ),
        )
    return DashboardWipRangeSeries(
        range=range_spec.key,
        bucket=range_spec.bucket,
        points=points,
    )


async def _query_throughput(
    session: AsyncSession,
    range_spec: RangeSpec,
    board_ids: list[UUID],
) -> DashboardRangeSeries:
    bucket_col = func.date_trunc(range_spec.bucket, Task.updated_at).label("bucket")
    statement = (
        select(bucket_col, func.count())
        .where(col(Task.status) == "done")
        .where(col(Task.updated_at) >= range_spec.start)
        .where(col(Task.updated_at) <= range_spec.end)
    )
    if not board_ids:
        return _series_from_mapping(range_spec, {})
    statement = (
        statement.where(col(Task.board_id).in_(board_ids)).group_by(bucket_col).order_by(bucket_col)
    )
    results = (await session.exec(statement)).all()
    mapping = {row[0]: float(row[1]) for row in results}
    return _series_from_mapping(range_spec, mapping)


async def _query_cycle_time(
    session: AsyncSession,
    range_spec: RangeSpec,
    board_ids: list[UUID],
) -> DashboardRangeSeries:
    bucket_col = func.date_trunc(range_spec.bucket, Task.updated_at).label("bucket")
    in_progress = sql_cast(Task.in_progress_at, DateTime)
    duration_hours = func.extract("epoch", Task.updated_at - in_progress) / 3600.0
    statement = (
        select(bucket_col, func.avg(duration_hours))
        .where(col(Task.status) == "review")
        .where(col(Task.in_progress_at).is_not(None))
        .where(col(Task.updated_at) >= range_spec.start)
        .where(col(Task.updated_at) <= range_spec.end)
    )
    if not board_ids:
        return _series_from_mapping(range_spec, {})
    statement = (
        statement.where(col(Task.board_id).in_(board_ids)).group_by(bucket_col).order_by(bucket_col)
    )
    results = (await session.exec(statement)).all()
    mapping = {row[0]: float(row[1] or 0) for row in results}
    return _series_from_mapping(range_spec, mapping)


async def _query_error_rate(
    session: AsyncSession,
    range_spec: RangeSpec,
    board_ids: list[UUID],
) -> DashboardRangeSeries:
    bucket_col = func.date_trunc(
        range_spec.bucket,
        ActivityEvent.created_at,
    ).label("bucket")
    error_case = case(
        (
            col(ActivityEvent.event_type).like(ERROR_EVENT_PATTERN),
            1,
        ),
        else_=0,
    )
    statement = (
        select(bucket_col, func.sum(error_case), func.count())
        .join(Task, col(ActivityEvent.task_id) == col(Task.id))
        .where(col(ActivityEvent.created_at) >= range_spec.start)
        .where(col(ActivityEvent.created_at) <= range_spec.end)
    )
    if not board_ids:
        return _series_from_mapping(range_spec, {})
    statement = (
        statement.where(col(Task.board_id).in_(board_ids)).group_by(bucket_col).order_by(bucket_col)
    )
    results = (await session.exec(statement)).all()
    mapping: dict[datetime, float] = {}
    for bucket, errors, total in results:
        total_count = float(total or 0)
        error_count = float(errors or 0)
        rate = (error_count / total_count) * 100 if total_count > 0 else 0.0
        mapping[bucket] = rate
    return _series_from_mapping(range_spec, mapping)


async def _query_wip(
    session: AsyncSession,
    range_spec: RangeSpec,
    board_ids: list[UUID],
) -> DashboardWipRangeSeries:
    if not board_ids:
        return _wip_series_from_mapping(range_spec, {})

    inbox_bucket_col = func.date_trunc(range_spec.bucket, Task.created_at).label("inbox_bucket")
    inbox_statement = (
        select(inbox_bucket_col, func.count())
        .where(col(Task.status) == "inbox")
        .where(col(Task.created_at) >= range_spec.start)
        .where(col(Task.created_at) <= range_spec.end)
        .where(col(Task.board_id).in_(board_ids))
        .group_by(inbox_bucket_col)
        .order_by(inbox_bucket_col)
    )
    inbox_results = (await session.exec(inbox_statement)).all()

    status_bucket_col = func.date_trunc(range_spec.bucket, Task.updated_at).label("status_bucket")
    progress_case = case((col(Task.status) == "in_progress", 1), else_=0)
    review_case = case((col(Task.status) == "review", 1), else_=0)
    done_case = case((col(Task.status) == "done", 1), else_=0)
    status_statement = (
        select(
            status_bucket_col,
            func.sum(progress_case),
            func.sum(review_case),
            func.sum(done_case),
        )
        .where(col(Task.updated_at) >= range_spec.start)
        .where(col(Task.updated_at) <= range_spec.end)
        .where(col(Task.board_id).in_(board_ids))
        .group_by(status_bucket_col)
        .order_by(status_bucket_col)
    )
    status_results = (await session.exec(status_statement)).all()

    mapping: dict[datetime, dict[str, int]] = {}
    for bucket, inbox in inbox_results:
        values = mapping.setdefault(bucket, {})
        values["inbox"] = int(inbox or 0)
    for bucket, in_progress, review, done in status_results:
        values = mapping.setdefault(bucket, {})
        values["in_progress"] = int(in_progress or 0)
        values["review"] = int(review or 0)
        values["done"] = int(done or 0)
    return _wip_series_from_mapping(range_spec, mapping)


async def _median_cycle_time_for_range(
    session: AsyncSession,
    range_spec: RangeSpec,
    board_ids: list[UUID],
) -> float | None:
    in_progress = sql_cast(Task.in_progress_at, DateTime)
    duration_hours = func.extract("epoch", Task.updated_at - in_progress) / 3600.0
    statement = (
        select(func.percentile_cont(0.5).within_group(duration_hours))
        .where(col(Task.status) == "review")
        .where(col(Task.in_progress_at).is_not(None))
        .where(col(Task.updated_at) >= range_spec.start)
        .where(col(Task.updated_at) <= range_spec.end)
    )
    if not board_ids:
        return None
    statement = statement.where(col(Task.board_id).in_(board_ids))
    value = (await session.exec(statement)).one_or_none()
    if value is None:
        return None
    if isinstance(value, tuple):
        value = value[0]
    if value is None:
        return None
    return float(value)


async def _error_rate_kpi(
    session: AsyncSession,
    range_spec: RangeSpec,
    board_ids: list[UUID],
) -> float:
    error_case = case(
        (
            col(ActivityEvent.event_type).like(ERROR_EVENT_PATTERN),
            1,
        ),
        else_=0,
    )
    statement = (
        select(func.sum(error_case), func.count())
        .join(Task, col(ActivityEvent.task_id) == col(Task.id))
        .where(col(ActivityEvent.created_at) >= range_spec.start)
        .where(col(ActivityEvent.created_at) <= range_spec.end)
    )
    if not board_ids:
        return 0.0
    statement = statement.where(col(Task.board_id).in_(board_ids))
    result = (await session.exec(statement)).one_or_none()
    if result is None:
        return 0.0
    errors, total = result
    total_count = float(total or 0)
    error_count = float(errors or 0)
    return (error_count / total_count) * 100 if total_count > 0 else 0.0


async def _active_agents(
    session: AsyncSession,
    range_spec: RangeSpec,
    board_ids: list[UUID],
) -> int:
    statement = select(func.count()).where(
        col(Agent.last_seen_at).is_not(None),
        col(Agent.last_seen_at) >= range_spec.start,
        col(Agent.last_seen_at) <= range_spec.end,
    )
    if not board_ids:
        return 0
    statement = statement.where(col(Agent.board_id).in_(board_ids))
    result = (await session.exec(statement)).one()
    return int(result)


async def _task_status_counts(
    session: AsyncSession,
    board_ids: list[UUID],
) -> dict[str, int]:
    if not board_ids:
        return {
            "inbox": 0,
            "in_progress": 0,
            "review": 0,
            "done": 0,
        }
    statement = (
        select(col(Task.status), func.count())
        .where(col(Task.board_id).in_(board_ids))
        .group_by(col(Task.status))
    )
    results = (await session.exec(statement)).all()
    counts = {
        "inbox": 0,
        "in_progress": 0,
        "review": 0,
        "done": 0,
    }
    for status_value, total in results:
        key = str(status_value)
        if key in counts:
            counts[key] = int(total or 0)
    return counts


async def _pending_approvals_snapshot(
    session: AsyncSession,
    board_ids: list[UUID],
    *,
    limit: int = 10,
) -> DashboardPendingApprovals:
    if not board_ids:
        return DashboardPendingApprovals(total=0, items=[])

    total_statement = (
        select(func.count(col(Approval.id)))
        .where(col(Approval.board_id).in_(board_ids))
        .where(col(Approval.status) == "pending")
    )
    total = int((await session.exec(total_statement)).one() or 0)
    if total == 0:
        return DashboardPendingApprovals(total=0, items=[])

    rows = (
        await session.exec(
            select(Approval, Board, Task)
            .join(Board, col(Board.id) == col(Approval.board_id))
            .outerjoin(Task, col(Task.id) == col(Approval.task_id))
            .where(col(Approval.board_id).in_(board_ids))
            .where(col(Approval.status) == "pending")
            .order_by(col(Approval.created_at).desc())
            .limit(limit)
        )
    ).all()

    items = [
        DashboardPendingApproval(
            approval_id=approval.id,
            board_id=approval.board_id,
            board_name=board.name,
            action_type=approval.action_type,
            confidence=float(approval.confidence),
            created_at=approval.created_at,
            task_title=task.title if task is not None else None,
        )
        for approval, board, task in rows
    ]
    return DashboardPendingApprovals(total=total, items=items)


async def _resolve_dashboard_board_ids(
    session: AsyncSession,
    *,
    ctx: OrganizationContext,
    board_id: UUID | None,
    group_id: UUID | None,
) -> list[UUID]:
    board_ids = await list_accessible_board_ids(session, member=ctx.member, write=False)
    if not board_ids:
        return []
    allowed = set(board_ids)

    if board_id is not None and board_id not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if group_id is None:
        return [board_id] if board_id is not None else board_ids

    group_board_ids = list(
        await session.exec(
            select(Board.id)
            .where(col(Board.organization_id) == ctx.member.organization_id)
            .where(col(Board.board_group_id) == group_id)
            .where(col(Board.id).in_(board_ids)),
        ),
    )
    if board_id is not None:
        return [board_id] if board_id in set(group_board_ids) else []
    return group_board_ids


def _initial_workload_counts() -> dict[str, int]:
    return {status_key: 0 for status_key in _AGENT_WORKLOAD_STATUSES}


async def _agent_task_counts(
    session: AsyncSession,
    board_ids: list[UUID],
) -> dict[UUID, dict[str, int]]:
    if not board_ids:
        return {}
    statement = (
        select(
            col(Task.assigned_agent_id),
            col(Task.status),
            func.count(),
        )
        .where(col(Task.assigned_agent_id).is_not(None))
        .where(col(Task.board_id).in_(board_ids))
        .group_by(col(Task.assigned_agent_id), col(Task.status))
    )
    rows = (await session.exec(statement)).all()
    counts: dict[UUID, dict[str, int]] = {}
    for agent_id, task_status, total in rows:
        if agent_id is None:
            continue
        normalized_status = str(task_status or "").lower()
        if normalized_status not in _AGENT_WORKLOAD_STATUSES:
            continue
        bucket = counts.setdefault(agent_id, _initial_workload_counts())
        bucket[normalized_status] = int(total or 0)
    return counts


def _agent_workload_agents(
    agent_rows: Sequence[tuple[Agent, Board | None]],
    counts: dict[UUID, dict[str, int]],
) -> list[AgentWorkloadAgent]:
    result: list[AgentWorkloadAgent] = []
    for agent, board in agent_rows:
        agent_counts = counts.setdefault(agent.id, _initial_workload_counts())
        result.append(
            AgentWorkloadAgent(
                agent_id=agent.id,
                board_id=agent.board_id,
                board_name=board.name if board is not None else None,
                name=agent.name,
                status=agent.status or "",
                last_seen_at=agent.last_seen_at,
                task_counts=AgentWorkloadTaskCounts(
                    inbox=agent_counts.get("inbox", 0),
                    in_progress=agent_counts.get("in_progress", 0),
                    review=agent_counts.get("review", 0),
                    done=agent_counts.get("done", 0),
                ),
            ),
        )
    return sorted(result, key=lambda entry: entry.name.lower())


def _agent_workload_summary_from_agents(
    agents: list[AgentWorkloadAgent],
) -> AgentWorkloadSummary:
    inbox = sum(entry.task_counts.inbox for entry in agents)
    in_progress = sum(entry.task_counts.in_progress for entry in agents)
    review = sum(entry.task_counts.review for entry in agents)
    done = sum(entry.task_counts.done for entry in agents)
    assigned = inbox + in_progress + review + done
    online = sum(1 for entry in agents if (entry.status or "").lower() == "online")
    return AgentWorkloadSummary(
        total_agents=len(agents),
        online_agents=online,
        assigned_tasks=assigned,
        inbox_tasks=inbox,
        in_progress_tasks=in_progress,
        review_tasks=review,
        done_tasks=done,
    )


def _cron_items(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, Mapping)]
    if isinstance(payload, Mapping):
        for key in _CRON_ITEM_KEYS:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [entry for entry in candidate if isinstance(entry, Mapping)]
    return []


def _coerce_string_value(value: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    if isinstance(value, Mapping):
        return _extract_string_value(value, keys)
    return None


def _extract_string_value(
    entry: Mapping[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    if not isinstance(entry, Mapping):
        return None
    for key in keys:
        if key not in entry:
            continue
        result = _coerce_string_value(entry[key], keys)
        if result:
            return result
    metadata = entry.get("metadata")
    if isinstance(metadata, Mapping):
        return _extract_string_value(metadata, keys)
    return None


def _cron_schedule_label(entry: Mapping[str, Any]) -> str | None:
    label = _extract_string_value(entry, _CRON_SCHEDULE_KEYS)
    if label:
        return label
    schedule = entry.get("schedule")
    if isinstance(schedule, Mapping):
        nested_keys = _CRON_SCHEDULE_KEYS + ("expression", "pattern", "value")
        nested_label = _extract_string_value(schedule, nested_keys)
        if nested_label:
            return nested_label
        try:
            return json.dumps(schedule, separators=(",", ":"))
        except (TypeError, ValueError):
            return None
    if isinstance(schedule, str):
        trimmed = schedule.strip()
        return trimmed or None
    return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "enabled", "active"}:
            return True
        if normalized in {"0", "false", "no", "disabled", "inactive"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _cron_enabled_flag(entry: Mapping[str, Any]) -> bool | None:
    if not isinstance(entry, Mapping):
        return None
    for key in _CRON_ENABLED_KEYS:
        flag = _coerce_bool(entry.get(key))
        if flag is not None:
            return flag
    return _coerce_bool(entry.get("status"))


def _datetime_from_epoch(value: float) -> datetime:
    if value >= 1_000_000_000_000:
        value /= 1000.0
    return datetime.utcfromtimestamp(value)


def _normalize_cron_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return _datetime_from_epoch(float(value))
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        try:
            return datetime.fromisoformat(trimmed)
        except ValueError:
            pass
        try:
            numeric = float(trimmed)
        except ValueError:
            return None
        return _datetime_from_epoch(numeric)
    return None


def _build_calendar_event(
    entry: Mapping[str, Any],
    board_lookup: dict[str, Board],
    gateway: Gateway,
) -> CalendarEvent | None:
    board_key = _extract_string_value(entry, _CRON_BOARD_KEYS)
    if not board_key:
        return None
    board = board_lookup.get(board_key)
    if board is None:
        return None
    event_id = _extract_string_value(entry, ("id", "cronId", "key", "name"))
    if not event_id:
        return None
    return CalendarEvent(
        id=event_id,
        name=_extract_string_value(entry, ("name", "label", "title")),
        description=_extract_string_value(entry, ("description", "summary", "details")),
        board_id=board.id,
        board_name=board.name,
        schedule=_cron_schedule_label(entry),
        next_run_at=_normalize_cron_datetime(
            entry.get("next_run_at")
            or entry.get("nextRunAt")
            or entry.get("next_run")
            or entry.get("nextRun")
        ),
        last_run_at=_normalize_cron_datetime(
            entry.get("last_run_at")
            or entry.get("lastRunAt")
            or entry.get("last_run")
            or entry.get("lastRun")
        ),
        enabled=_cron_enabled_flag(entry),
        gateway_id=gateway.id,
        gateway_name=gateway.name,
    )


async def _collect_calendar_events(
    session: AsyncSession,
    board_ids: list[UUID],
) -> tuple[list[CalendarEvent], list[CalendarWarning]]:
    """Gather cron events for accessible boards via the associated gateways.

    Entries are filtered to boards that specify a gateway, and any gateway or
    parsing problems are surfaced in the returned warnings so callers understand
    what data may be missing.
    """
    warnings: list[CalendarWarning] = []
    if not board_ids:
        return [], warnings
    boards = (await session.exec(select(Board).where(col(Board.id).in_(board_ids)))).all()
    if not boards:
        return [], warnings
    boards_by_gateway: dict[UUID, list[Board]] = {}
    gateway_ids: set[UUID] = set()
    for board in boards:
        if not board.gateway_id:
            warnings.append(
                CalendarWarning(
                    board_id=board.id,
                    message=f"Board {board.name} has no gateway configured; scheduled events are unavailable.",
                )
            )
            continue
        gateway_ids.add(board.gateway_id)
        boards_by_gateway.setdefault(board.gateway_id, []).append(board)
    if not gateway_ids:
        return [], warnings
    gateway_rows = (
        await session.exec(select(Gateway).where(col(Gateway.id).in_(gateway_ids)))
    ).all()
    gateways_by_id = {gateway.id: gateway for gateway in gateway_rows}
    missing_gateways = gateway_ids - set(gateways_by_id)
    for missing in missing_gateways:
        for board in boards:
            if board.gateway_id == missing:
                warnings.append(
                    CalendarWarning(
                        board_id=board.id,
                        message="Board references an unknown gateway configuration.",
                    )
                )
    events: list[CalendarEvent] = []
    seen_ids: set[str] = set()
    for gateway_id, gateway in gateways_by_id.items():
        try:
            config = gateway_client_config(gateway)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Gateway configuration invalid."
            warnings.append(
                CalendarWarning(
                    gateway_id=gateway_id,
                    message=detail,
                )
            )
            continue
        gateway_boards = boards_by_gateway.get(gateway_id, [])
        if not gateway_boards:
            continue
        board_lookup = {str(board.id): board for board in gateway_boards}
        try:
            payload = await openclaw_call("cron.list", config=config)
        except OpenClawGatewayError as exc:
            warnings.append(
                CalendarWarning(
                    gateway_id=gateway_id,
                    message=str(exc),
                )
            )
            continue
        for entry in _cron_items(payload):
            event = _build_calendar_event(entry, board_lookup, gateway)
            if event is None or event.id in seen_ids:
                continue
            seen_ids.add(event.id)
            events.append(event)
    events.sort(
        key=lambda item: item.next_run_at or item.last_run_at or datetime.max,
    )
    return events, warnings


@router.get("/dashboard/agent-workload", response_model=AgentWorkloadSnapshot)
async def dashboard_agent_workload(
    board_id: UUID | None = BOARD_ID_QUERY,
    group_id: UUID | None = GROUP_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> AgentWorkloadSnapshot:
    """Return board-scoped agent workload totals."""
    board_ids = await _resolve_dashboard_board_ids(
        session,
        ctx=ctx,
        board_id=board_id,
        group_id=group_id,
    )
    agents: list[AgentWorkloadAgent] = []
    summary = _agent_workload_summary_from_agents([])
    if board_ids:
        agent_rows = (
            await session.exec(
                select(Agent, Board)
                .join(Board, col(Board.id) == col(Agent.board_id))
                .where(col(Agent.board_id).in_(board_ids))
            )
        ).all()
        counts = await _agent_task_counts(session, board_ids)
        agents = _agent_workload_agents(agent_rows, counts)
        summary = _agent_workload_summary_from_agents(agents)
    return AgentWorkloadSnapshot(
        generated_at=utcnow(),
        summary=summary,
        agents=agents,
    )


@router.get("/dashboard/calendar", response_model=CalendarOverview)
async def dashboard_calendar_overview(
    board_id: UUID | None = BOARD_ID_QUERY,
    group_id: UUID | None = GROUP_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> CalendarOverview:
    """Return a schedule overview sourced from gateway cron data for accessible boards."""
    board_ids = await _resolve_dashboard_board_ids(
        session,
        ctx=ctx,
        board_id=board_id,
        group_id=group_id,
    )
    events, warnings = await _collect_calendar_events(session, board_ids)
    return CalendarOverview(
        generated_at=utcnow(),
        events=events,
        warnings=warnings,
    )


@router.get("/dashboard", response_model=DashboardMetrics)
async def dashboard_metrics(
    range_key: DashboardRangeKey = RANGE_QUERY,
    board_id: UUID | None = BOARD_ID_QUERY,
    group_id: UUID | None = GROUP_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> DashboardMetrics:
    """Return dashboard KPIs and time-series data for accessible boards."""
    primary = _resolve_range(range_key)
    comparison = _comparison_range(primary)
    board_ids = await _resolve_dashboard_board_ids(
        session,
        ctx=ctx,
        board_id=board_id,
        group_id=group_id,
    )

    throughput_primary = await _query_throughput(session, primary, board_ids)
    throughput_comparison = await _query_throughput(session, comparison, board_ids)
    throughput = DashboardSeriesSet(
        primary=throughput_primary,
        comparison=throughput_comparison,
    )
    cycle_time_primary = await _query_cycle_time(session, primary, board_ids)
    cycle_time_comparison = await _query_cycle_time(session, comparison, board_ids)
    cycle_time = DashboardSeriesSet(
        primary=cycle_time_primary,
        comparison=cycle_time_comparison,
    )
    error_rate_primary = await _query_error_rate(session, primary, board_ids)
    error_rate_comparison = await _query_error_rate(session, comparison, board_ids)
    error_rate = DashboardSeriesSet(
        primary=error_rate_primary,
        comparison=error_rate_comparison,
    )
    wip_primary = await _query_wip(session, primary, board_ids)
    wip_comparison = await _query_wip(session, comparison, board_ids)
    wip = DashboardWipSeriesSet(
        primary=wip_primary,
        comparison=wip_comparison,
    )
    task_status_counts = await _task_status_counts(session, board_ids)
    pending_approvals = await _pending_approvals_snapshot(session, board_ids, limit=10)

    kpis = DashboardKpis(
        active_agents=await _active_agents(session, primary, board_ids),
        tasks_in_progress=task_status_counts["in_progress"],
        inbox_tasks=task_status_counts["inbox"],
        in_progress_tasks=task_status_counts["in_progress"],
        review_tasks=task_status_counts["review"],
        done_tasks=task_status_counts["done"],
        error_rate_pct=await _error_rate_kpi(session, primary, board_ids),
        median_cycle_time_hours_7d=await _median_cycle_time_for_range(
            session,
            primary,
            board_ids,
        ),
    )

    return DashboardMetrics(
        range=primary.key,
        generated_at=utcnow(),
        kpis=kpis,
        throughput=throughput,
        cycle_time=cycle_time,
        error_rate=error_rate,
        wip=wip,
        pending_approvals=pending_approvals,
    )
