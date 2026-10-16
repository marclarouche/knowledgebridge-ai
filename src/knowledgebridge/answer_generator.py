"""Local structured generation; no tools, history, cloud models or raw UI output."""

import json
from typing import Protocol

from knowledgebridge.answer_models import GenerationIdentity
from knowledgebridge.config import GenerationSettings, RetrievalSettings
from knowledgebridge.embedding_adapter import OllamaTransport
from knowledgebridge.retrieval_models import RetrievalError


class Generator(Protocol):
    def identity(self) -> GenerationIdentity: ...

    def complete(
        self, instruction: str, payload: dict[str, object], schema: dict[str, object]
    ) -> str: ...


class OllamaGenerator:
    def __init__(self, local: RetrievalSettings, settings: GenerationSettings):
        self.settings = settings
        self.transport = OllamaTransport(
            local.model_copy(
                update={
                    "model": settings.model,
                    "timeout_seconds": settings.timeout_seconds,
                }
            )
        )

    def identity(self) -> GenerationIdentity:
        return GenerationIdentity(model=self.settings.model, digest=self.transport._digest())

    def complete(
        self, instruction: str, payload: dict[str, object], schema: dict[str, object]
    ) -> str:
        content = json.dumps(payload, ensure_ascii=False)
        # Conservative UTF-8 byte budget: do not silently overflow the configured model context.
        if len((instruction + content + json.dumps(schema)).encode()) > (
            self.settings.num_ctx - self.settings.num_predict - 512
        ):
            raise RetrievalError(
                "Answer context exceeds the model budget. Reduce context settings or increase num_ctx."
            )
        response = self.transport._request(
            "/api/chat",
            {
                "model": self.settings.model,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": content},
                ],
                "format": schema,
                "stream": False,
                "think": False,
                "keep_alive": "5m",
                "options": {
                    "temperature": 0,
                    "seed": 0,
                    "num_ctx": self.settings.num_ctx,
                    "num_predict": self.settings.num_predict,
                },
            },
        )
        message = response.get("message")
        if (
            response.get("model") != self.settings.model
            or response.get("done") is not True
            or response.get("done_reason") != "stop"
            or not isinstance(message, dict)
            or message.get("role") != "assistant"
            or message.get("tool_calls")
            or not isinstance(message.get("content"), str)
        ):
            raise RetrievalError(
                "Generation response is incomplete or invalid; no answer displayed."
            )
        result = message["content"]
        if not result.strip() or len(result) > self.settings.max_output_chars:
            raise RetrievalError("Generation response exceeds its limits or is empty.")
        return str(result)
