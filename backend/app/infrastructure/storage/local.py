"""Local filesystem Object Storage adapter for dev/MVP1.

Swap this module for an S3-compatible client behind the same two functions when
deploying — nothing above this layer (Document Layer, extraction) should need to
change (SYSTEM_ARCHITECTURE.md section 1.2 storage component).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.infrastructure.db.config import settings


def save_upload(voyage_id: str, filename: str, content: bytes) -> tuple[str, str]:
    """Persist an uploaded file. Returns (storage_uri, sha256_hash)."""
    directory = Path(settings.storage_dir) / voyage_id
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    safe_name = filename.replace("/", "_")
    dest = directory / f"{digest}_{safe_name}"
    dest.write_bytes(content)
    return str(dest), digest
