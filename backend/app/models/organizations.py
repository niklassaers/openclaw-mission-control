"""Organization model representing top-level tenant entities."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel


class Organization(QueryModel, table=True):
    """Top-level organization tenant record."""

    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("name", name="uq_organizations_name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
