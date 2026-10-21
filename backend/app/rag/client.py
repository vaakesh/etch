import asyncio

import httpx
from pydantic import ValidationError

from app.rag.errors import (
    RagBadResponseError,
    RagTimeoutError,
    RagUnavailableError,
)
from app.rag.schemas import AskMessageResponse, AskResponse
from app.tracing import traced


class RagClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        request_timeout: float,
    ):
        self._http = http
        self._request_timeout = request_timeout

    @traced("rag.client.ask")
    async def ask(self, message: str) -> AskMessageResponse:
        try:
            async with asyncio.timeout(self._request_timeout):
                response = await self._http.post(
                    url="ask",
                    json={"message": message},
                )
        except httpx.PoolTimeout as exc:
            raise RagUnavailableError() from exc
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise RagTimeoutError() from exc
        except httpx.RequestError as exc:
            raise RagUnavailableError() from exc

        if response.status_code in (429, 503):
            raise RagUnavailableError()

        if response.status_code != 200:
            raise RagBadResponseError()

        try:
            answer = AskResponse.model_validate_json(response.content)
        except ValidationError as exc:
            raise RagBadResponseError() from exc

        return AskMessageResponse(text=answer.text)
