from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings. Secrets remain server-side."""

    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8000
    neuronpedia_api_key: str | None = None
    neuronpedia_base_url: str = "https://www.neuronpedia.org"
    neuronpedia_timeout_seconds: float = 300.0
    neuronpedia_max_retries: int = 3
    worker_url: str | None = "http://127.0.0.1:8100"
    worker_token: str | None = None
    max_runs_per_request: int = 8
    max_raw_bytes: int = 250_000_000

    @classmethod
    def from_env(cls) -> "Settings":
        key = os.getenv("NEURONPEDIA_API_KEY", "").strip() or None
        worker_url = os.getenv("PRISMORA_WORKER_URL", "http://127.0.0.1:8100").strip() or None
        worker_token = os.getenv("PRISMORA_WORKER_TOKEN", "").strip() or None
        return cls(
            data_dir=Path(os.getenv("PRISMORA_DATA_DIR", ".prismora-data")).expanduser().resolve(),
            host=os.getenv("PRISMORA_HOST", "127.0.0.1"),
            port=int(os.getenv("PRISMORA_PORT", "8000")),
            neuronpedia_api_key=key,
            neuronpedia_base_url=os.getenv("NEURONPEDIA_BASE_URL", "https://www.neuronpedia.org").rstrip("/"),
            neuronpedia_timeout_seconds=float(os.getenv("NEURONPEDIA_TIMEOUT_SECONDS", "300")),
            neuronpedia_max_retries=int(os.getenv("NEURONPEDIA_MAX_RETRIES", "3")),
            worker_url=worker_url.rstrip("/") if worker_url else None,
            worker_token=worker_token,
            max_runs_per_request=int(os.getenv("PRISMORA_MAX_RUNS_PER_REQUEST", "8")),
            max_raw_bytes=int(os.getenv("PRISMORA_MAX_RAW_BYTES", "250000000")),
        )
