"""Dashboard metrics schemas for KPI and time-series API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlmodel import Field, SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)
DashboardRangeKey = Literal["24h", "3d", "7d", "14d", "1m", "3m", "6m", "1y"]
DashboardBucketKey = Literal["hour", "day", "week", "month"]


class DashboardSeriesPoint(SQLModel):
    """Single numeric time-series point."""

    period: datetime
    value: float


class DashboardWipPoint(SQLModel):
    """Work-in-progress point split by task status buckets."""

    period: datetime
    inbox: int
    in_progress: int
    review: int
    done: int


class DashboardRangeSeries(SQLModel):
    """Series payload for a single range/bucket combination."""

    range: DashboardRangeKey
    bucket: DashboardBucketKey
    points: list[DashboardSeriesPoint]


class DashboardWipRangeSeries(SQLModel):
    """WIP series payload for a single range/bucket combination."""

    range: DashboardRangeKey
    bucket: DashboardBucketKey
    points: list[DashboardWipPoint]


class DashboardSeriesSet(SQLModel):
    """Primary vs comparison pair for generic series metrics."""

    primary: DashboardRangeSeries
    comparison: DashboardRangeSeries


class DashboardWipSeriesSet(SQLModel):
    """Primary vs comparison pair for WIP status series metrics."""

    primary: DashboardWipRangeSeries
    comparison: DashboardWipRangeSeries


class DashboardKpis(SQLModel):
    """Topline dashboard KPI summary values."""

    active_agents: int
    tasks_in_progress: int
    inbox_tasks: int
    in_progress_tasks: int
    review_tasks: int
    done_tasks: int
    error_rate_pct: float
    median_cycle_time_hours_7d: float | None


class DashboardPendingApproval(SQLModel):
    """Single pending approval item for cross-board dashboard listing."""

    approval_id: UUID
    board_id: UUID
    board_name: str
    action_type: str
    confidence: float
    created_at: datetime
    task_title: str | None = None


class DashboardPendingApprovals(SQLModel):
    """Pending approval snapshot used on the dashboard."""

    total: int
    items: list[DashboardPendingApproval]


class DashboardMetrics(SQLModel):
    """Complete dashboard metrics response payload."""

    range: DashboardRangeKey
    generated_at: datetime
    kpis: DashboardKpis
    throughput: DashboardSeriesSet
    cycle_time: DashboardSeriesSet
    error_rate: DashboardSeriesSet
    wip: DashboardWipSeriesSet
    pending_approvals: DashboardPendingApprovals


class AgentWorkloadTaskCounts(SQLModel):
    """Task bucket totals for a single agent."""

    inbox: int
    in_progress: int
    review: int
    done: int


class AgentWorkloadAgent(SQLModel):
    """Agent-level workload snapshot entry."""

    agent_id: UUID
    board_id: UUID | None
    board_name: str | None
    name: str
    status: str
    last_seen_at: datetime | None
    task_counts: AgentWorkloadTaskCounts


class AgentWorkloadSummary(SQLModel):
    """Topline workload totals across accessible agents."""

    total_agents: int
    online_agents: int
    assigned_tasks: int
    inbox_tasks: int
    in_progress_tasks: int
    review_tasks: int
    done_tasks: int


class AgentWorkloadSnapshot(SQLModel):
    """Full agent workload payload for the dashboard."""

    generated_at: datetime
    summary: AgentWorkloadSummary
    agents: list[AgentWorkloadAgent]


class CalendarEvent(SQLModel):
    """Scheduled automation event backed by gateway cron data."""

    id: str
    name: str | None
    description: str | None
    board_id: UUID | None
    board_name: str | None
    schedule: str | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    enabled: bool | None
    gateway_id: UUID | None
    gateway_name: str | None


class CalendarWarning(SQLModel):
    """Advisories emitted while parsing or filtering cron data."""

    message: str
    gateway_id: UUID | None = None
    board_id: UUID | None = None


class CalendarOverview(SQLModel):
    """Calendar overview payload surfaced on Mission Control."""

    generated_at: datetime
    events: list[CalendarEvent]
    warnings: list[CalendarWarning] = Field(default_factory=list)
