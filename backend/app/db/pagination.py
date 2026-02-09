"""Typed wrapper around fastapi-pagination for backend query helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, TypeVar, cast

from fastapi_pagination.ext.sqlalchemy import paginate as _paginate

from app.schemas.pagination import DefaultLimitOffsetPage

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession
    from sqlmodel.sql.expression import Select, SelectOfScalar

T = TypeVar("T")

Transformer = Callable[[Sequence[Any]], Sequence[Any] | Awaitable[Sequence[Any]]]


async def paginate(
    session: AsyncSession,
    statement: Select[Any] | SelectOfScalar[Any],
    *,
    transformer: Transformer | None = None,
) -> DefaultLimitOffsetPage[T]:
    """Execute a paginated query and cast to the project page type alias."""
    # fastapi-pagination is not fully typed (it returns Any), but response_model
    # validation ensures runtime correctness. Centralize casts here to keep strict
    # mypy clean.
    return cast(
        DefaultLimitOffsetPage[T],
        await _paginate(session, statement, transformer=transformer),
    )
