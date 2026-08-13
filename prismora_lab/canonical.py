from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Stable UTF-8 JSON representation used for protocol/result identities."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_bytes(path: Path, data: bytes, *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(tmp_name, path)
        else:
            # Publishing a completed temporary inode with a hard link gives
            # true create-if-absent semantics. A pre-check followed by
            # os.replace() races and can overwrite a concurrent writer.
            os.link(tmp_name, path)
            os.unlink(tmp_name)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, value: Any, *, pretty: bool = True, overwrite: bool = True) -> None:
    if pretty:
        data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    else:
        data = canonical_json_bytes(value)
    atomic_write_bytes(path, data, overwrite=overwrite)
