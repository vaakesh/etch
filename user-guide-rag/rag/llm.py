from typing import Protocol

from rag.types import ChatMessage


class LLM(Protocol):
    def generate(self, messages: list[ChatMessage]) -> str:
        """Generate answer text from provider-independent chat messages."""
        ...
