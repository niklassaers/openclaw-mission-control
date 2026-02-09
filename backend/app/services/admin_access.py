"""Access control helpers for admin-only operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from app.core.auth import AuthContext


def require_admin(auth: AuthContext) -> None:
    """Raise HTTP 403 unless the authenticated actor is a user admin."""
    if auth.actor_type != "user" or auth.user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
