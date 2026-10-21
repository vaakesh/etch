from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.config import get_settings
from app.deps import get_resources
from app.rag.client import RagClient


@lru_cache(maxsize=1)
def get_rag_client() -> RagClient:
    settings = get_settings()
    http = httpx.AsyncClient(
        base_url=str(settings.rag_base_url).rstrip("/") + "/",
        timeout=httpx.Timeout(
            settings.rag_request_timeout,
            connect=3.0,
            write=10.0,
            pool=3.0,
        ),
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        ),
    )
    get_resources().push_async_callback(http.aclose)
    return RagClient(http, request_timeout=settings.rag_request_timeout)


type RagClientDeps = Annotated[RagClient, Depends(get_rag_client)]
