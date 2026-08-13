from __future__ import annotations

import re
from typing import Final


class IdentifierError(ValueError):
    """Raised when an identifier cannot safely name a stored record."""


_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "experiment": re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$"),
    "run": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,159}$"),
    "claim": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,119}$"),
    "campaign": re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$"),
}


def validate_identifier(value: object, kind: str) -> str:
    """Return a validated storage identifier or reject it without sanitizing.

    Replacing unsafe characters would make distinct external identifiers collide.
    Storage-facing identifiers therefore use an allow-list and fail closed.
    """
    if kind not in _PATTERNS:
        raise KeyError(f"Unknown identifier kind: {kind}")
    if not isinstance(value, str) or not _PATTERNS[kind].fullmatch(value):
        raise IdentifierError(f"Invalid {kind}_id: {value!r}")
    return value
