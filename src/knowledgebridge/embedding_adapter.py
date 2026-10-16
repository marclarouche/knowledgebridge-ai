"""Bounded Ollama HTTP adapter: loopback literals only, no proxy/redirect/cloud/pull."""

import http.client
import json
import math
from typing import Protocol

from knowledgebridge.config import RetrievalSettings
from knowledgebridge.retrieval_models import EmbeddingIdentity, RetrievalError


class OllamaTimeoutError(RetrievalError):
    """The configured local socket deadline elapsed; safe diagnostic only."""


class Embedder(Protocol):
    def identity(self) -> EmbeddingIdentity: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def validate_vectors(raw: object, count: int, dimensions: int | None = None) -> list[list[float]]:
    """Reject truncated, ragged, nonfinite, zero and oversized model vectors."""
    if not isinstance(raw, list) or len(raw) != count:
        raise RetrievalError("Embedding response count is invalid.")
    result: list[list[float]] = []
    for vector in raw:
        if not isinstance(vector, list) or not 1 <= len(vector) <= 8192:
            raise RetrievalError("Embedding dimensions are invalid.")
        if dimensions is None:
            dimensions = len(vector)
        if len(vector) != dimensions or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in vector
        ):
            raise RetrievalError("Embedding values or dimensions are invalid.")
        converted = [float(v) for v in vector]
        norm = math.sqrt(sum(v * v for v in converted))
        if not math.isfinite(norm) or norm <= 0:
            raise RetrievalError("Embedding vector has an invalid norm.")
        result.append([v / norm for v in converted])
    return result


class OllamaTransport:
    def __init__(self, settings: RetrievalSettings):
        self.settings = settings

    def _request(self, path: str, body: dict[str, object] | None = None) -> dict[str, object]:
        connection = http.client.HTTPConnection(
            self.settings.host, self.settings.port, timeout=self.settings.timeout_seconds
        )
        try:
            connection.request(
                "POST" if body is not None else "GET",
                path,
                body=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            if response.status != 200:
                raise RetrievalError(
                    "Ollama request failed. Check the local model and input limits."
                )
            data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise RetrievalError("Ollama response exceeds its limit.")
            decoded = json.loads(data)
            if not isinstance(decoded, dict):
                raise RetrievalError("Ollama returned an invalid response.")
            return decoded
        except RetrievalError:
            raise
        except TimeoutError:
            raise OllamaTimeoutError(
                "Local Ollama timed out. Check model load and runtime budgets."
            ) from None
        except (OSError, http.client.HTTPException, ValueError):
            raise RetrievalError(
                "Local Ollama is unavailable or returned malformed data."
            ) from None
        finally:
            connection.close()

    def _digest(self) -> str:
        tags = self._request("/api/tags").get("models")
        model = self.settings.model
        if not isinstance(tags, list):
            raise RetrievalError("Ollama model catalog is invalid.")
        match = next((m for m in tags if isinstance(m, dict) and m.get("name") == model), None)
        if match is None or not isinstance(match.get("digest"), str):
            raise RetrievalError(
                "Configured model is not installed locally. Install it with Ollama."
            )
        shown = self._request("/api/show", {"model": model})
        if shown.get("remote_host") or shown.get("remote_model") or model.endswith(":cloud"):
            raise RetrievalError("Cloud-backed models are prohibited. Choose a local model.")
        return str(match["digest"])


class OllamaEmbedder(OllamaTransport):
    def identity(self) -> EmbeddingIdentity:
        digest = self._digest()
        probe = self.embed(["KnowledgeBridge embedding dimension probe"])
        if self._digest() != digest:
            raise RetrievalError("Embedding model changed during validation. Retry indexing.")
        return EmbeddingIdentity(model=self.settings.model, digest=digest, dimensions=len(probe[0]))

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or len(texts) > 50000 or any(not t.strip() or len(t) > 20000 for t in texts):
            raise RetrievalError("Embedding input exceeds its limits or is empty.")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.settings.batch_size):
            batch = texts[start : start + self.settings.batch_size]
            response = self._request(
                "/api/embed",
                {
                    "model": self.settings.model,
                    "input": batch,
                    "truncate": False,
                    "keep_alive": "5m",
                },
            )
            if response.get("model") not in (
                self.settings.model,
                self.settings.model.removesuffix(":latest"),
            ):
                raise RetrievalError("Ollama returned a different embedding model.")
            vectors.extend(
                validate_vectors(
                    response.get("embeddings"), len(batch), len(vectors[0]) if vectors else None
                )
            )
        return vectors
