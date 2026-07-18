from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class BackendError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None):
        self.status_code = status_code
        self.details = details
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class BackendResult:
    """Parsed result plus the exact response bytes retained as raw evidence."""

    value: dict[str, Any]
    raw_bytes: bytes
    content_type: str = "application/json"


class ExecutionBackend(ABC):
    backend_id: str

    @abstractmethod
    async def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def run(self, request: dict[str, Any]) -> BackendResult:
        """Return parsed meta/tokens/done and exact raw response bytes."""
        raise NotImplementedError

    def raw_format(self) -> str:
        return "prismora-worker-json"
