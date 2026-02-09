"""User API schemas for create, update, and read operations."""

from __future__ import annotations

from uuid import UUID  # noqa: TCH003

from sqlmodel import SQLModel


class UserBase(SQLModel):
    """Common user profile fields shared across user payload schemas."""

    clerk_user_id: str
    email: str | None = None
    name: str | None = None
    preferred_name: str | None = None
    pronouns: str | None = None
    timezone: str | None = None
    notes: str | None = None
    context: str | None = None


class UserCreate(UserBase):
    """Payload used to create a user record."""


class UserUpdate(SQLModel):
    """Payload for partial user profile updates."""

    name: str | None = None
    preferred_name: str | None = None
    pronouns: str | None = None
    timezone: str | None = None
    notes: str | None = None
    context: str | None = None


class UserRead(UserBase):
    """Full user payload returned by API responses."""

    id: UUID
    is_super_admin: bool
