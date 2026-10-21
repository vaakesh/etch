import sys
import time

import httpx
from huggingface_hub import snapshot_download

from rag.config import get_settings
from rag.dependencies import (
    clear_dependency_caches,
    get_readiness_client,
    get_resources,
)


def wait_for_services() -> None:
    """Wait for Qdrant readiness before downloading model weights."""
    settings = get_settings()
    pending = {
        "Qdrant": f"{str(settings.qdrant_url).rstrip('/')}/readyz",
    }
    deadline = time.monotonic() + settings.init_timeout
    client = get_readiness_client()
    while pending:
        for name, url in list(pending.items()):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Services did not become ready: {', '.join(pending)}")
            try:
                response = client.get(url, timeout=min(1.0, remaining))
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            del pending[name]
        if pending:
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))


def main() -> None:
    resources = get_resources()
    resources.callback(clear_dependency_caches)
    try:
        try:
            wait_for_services()
            settings = get_settings()
            print(f"Downloading embedder: {settings.embedding_model}", flush=True)
            snapshot_download(repo_id=settings.embedding_model)
            print(f"Downloading reranker: {settings.reranker_model}", flush=True)
            snapshot_download(repo_id=settings.reranker_model)
            print("Models are ready.", flush=True)
        finally:
            resources.close()
    except (
        TimeoutError,
        ConnectionError,
        httpx.HTTPError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Model initialization failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
