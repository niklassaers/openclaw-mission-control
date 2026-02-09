"""User self-service API endpoints for profile retrieval and updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthContext, get_auth_context
from app.db.session import get_session
from app.schemas.users import UserRead, UserUpdate

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.users import User

router = APIRouter(prefix="/users", tags=["users"])
AUTH_CONTEXT_DEP = Depends(get_auth_context)
SESSION_DEP = Depends(get_session)


@router.get("/me", response_model=UserRead)
async def get_me(auth: AuthContext = AUTH_CONTEXT_DEP) -> UserRead:
    """Return the authenticated user's current profile payload."""
    if auth.actor_type != "user" or auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return UserRead.model_validate(auth.user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_CONTEXT_DEP,
) -> UserRead:
    """Apply partial profile updates for the authenticated user."""
    if auth.actor_type != "user" or auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    updates = payload.model_dump(exclude_unset=True)
    user: User = auth.user
    for key, value in updates.items():
        setattr(user, key, value)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)
