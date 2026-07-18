from __future__ import annotations

import copy

from .canonical import sha256_json
from .schema import validate
from .timeutil import utc_now_iso


def _hashable_locked_spec(spec: dict) -> dict:
    value = copy.deepcopy(spec)
    prereg = value.setdefault("preregistration", {})
    prereg["spec_sha256"] = None
    return value


def compute_locked_hash(spec: dict) -> str:
    return sha256_json(_hashable_locked_spec(spec))


def lock_spec(spec: dict) -> dict:
    value = copy.deepcopy(spec)
    prereg = value.setdefault("preregistration", {})
    if prereg.get("status") == "locked" and prereg.get("spec_sha256"):
        expected = compute_locked_hash(value)
        if expected != prereg["spec_sha256"]:
            raise ValueError("Locked preregistration hash does not match the document.")
        return value
    prereg["status"] = "locked"
    prereg["locked_at"] = utc_now_iso()
    prereg["spec_sha256"] = None
    prereg["spec_sha256"] = compute_locked_hash(value)
    validate("experiment", value)
    return value


def verify_locked_spec(spec: dict) -> bool:
    prereg = spec.get("preregistration", {})
    return bool(
        prereg.get("status") == "locked"
        and prereg.get("spec_sha256")
        and compute_locked_hash(spec) == prereg["spec_sha256"]
    )
