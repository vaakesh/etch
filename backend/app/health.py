import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.deps import UoWFactory, get_uow_factory
from app.redis.deps import get_redis

router = APIRouter(include_in_schema=True)
READINESS_TIMEOUT_SECONDS = 3


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _postgres_ready(uow_factory: UoWFactory) -> bool:
    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            async with uow_factory() as uow:
                await uow.session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _redis_ready(redis: Redis) -> bool:
    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            return bool(await redis.ping())
    except Exception:
        return False


@router.get("/ready")
async def ready(
    uow_factory: UoWFactory = Depends(get_uow_factory),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    postgres_ready, redis_ready = await asyncio.gather(
        _postgres_ready(uow_factory),
        _redis_ready(redis),
    )
    is_ready = postgres_ready and redis_ready
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "not_ready"},
    )
