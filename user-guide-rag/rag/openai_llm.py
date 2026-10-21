import logging

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.responses import Response
from openai.types.shared import ReasoningEffort

from rag.errors import RagError
from rag.types import ChatMessage

logger = logging.getLogger(__name__)


class OpenAILLM:
    def __init__(self, *, client: OpenAI, model: str, reasoning_effort: ReasoningEffort) -> None:
        """Configure generation with an externally owned OpenAI client."""
        self._client = client
        self._model = model
        self._reasoning_effort = reasoning_effort

    def generate(self, messages: list[ChatMessage]) -> str:
        """Generate a complete answer and translate SDK errors without exposing their bodies."""
        response: Response | None = None
        try:
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {"role": message["role"], "content": message["content"]} for message in messages
                ],
                stream=False,
                store=False,
                reasoning={"effort": self._reasoning_effort},
            )
        except APITimeoutError as exc:
            raise RagError("OpenAI request timed out. Check LLM_TIMEOUT or try again.") from exc
        except APIConnectionError as exc:
            raise RagError("Failed to connect to OpenAI. Check LLM_URL and connectivity.") from exc
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise RagError(
                "OpenAI access denied. Check LLM_API_KEY and model permissions."
            ) from exc
        except NotFoundError as exc:
            raise RagError(
                "OpenAI model or endpoint was not found. Check LLM_MODEL and LLM_URL."
            ) from exc
        except RateLimitError as exc:
            raise RagError(
                "OpenAI rate limit or quota exceeded. Check API limits or try again."
            ) from exc
        except APIStatusError as exc:
            raise RagError(
                f"OpenAI failed to generate a response (HTTP {exc.status_code})."
            ) from exc
        except APIError as exc:
            raise RagError("OpenAI failed to generate a valid response.") from exc
        finally:
            self._log_token_usage(response)

        if response.status != "completed":
            raise RagError("OpenAI did not complete the response. Try again.")
        text = response.output_text.strip()
        if not text:
            raise RagError("OpenAI returned an empty response.")
        return text

    def _log_token_usage(self, response: Response | None) -> None:
        """Record provider usage once per generation, including rejected responses."""
        if response is None:
            logger.warning(
                "LLM token usage unavailable model=%s reason=request_failed", self._model
            )
            return
        usage = response.usage
        if usage is None:
            logger.warning(
                "LLM token usage unavailable model=%s response_id=%s status=%s "
                "reason=missing_usage",
                self._model,
                response.id,
                response.status,
            )
            return

        logger.info(
            "LLM token usage model=%s response_id=%s status=%s "
            "input_tokens=%d output_tokens=%d total_tokens=%d "
            "cached_input_tokens=%s reasoning_tokens=%s",
            self._model,
            response.id,
            response.status,
            usage.input_tokens,
            usage.output_tokens,
            usage.total_tokens,
            usage.input_tokens_details.cached_tokens if usage.input_tokens_details else None,
            usage.output_tokens_details.reasoning_tokens if usage.output_tokens_details else None,
        )
