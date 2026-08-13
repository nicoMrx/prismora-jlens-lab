from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import atomic_write_json, canonical_json_bytes, read_json
from .identifiers import validate_identifier


def campaigns_dir(store: Any) -> Path:
    path = store.root / "campaigns"
    path.mkdir(parents=True, exist_ok=True)
    return path


def campaign_path(store: Any, campaign_id: str) -> Path:
    return campaigns_dir(store) / validate_identifier(campaign_id, "campaign") / "campaign.json"


def save_campaign(store: Any, campaign: dict[str, Any]) -> Path:
    value = {key: val for key, val in campaign.items() if key != "specs"}
    path = campaign_path(store, str(value["campaign_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = read_json(path)
        if existing.get("preregistration", {}).get("status") == "locked":
            if canonical_json_bytes(existing) != canonical_json_bytes(value):
                raise FileExistsError(
                    "Locked campaign is immutable. Use a new campaign_id for an amended protocol."
                )
            return path
    atomic_write_json(path, value)
    return path


def get_campaign(store: Any, campaign_id: str) -> dict[str, Any]:
    path = campaign_path(store, campaign_id)
    if not path.exists():
        raise FileNotFoundError(campaign_id)
    return read_json(path)


def list_campaigns(store: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(campaigns_dir(store).glob("*/campaign.json")):
        try:
            campaign = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(
            {
                "campaign_id": campaign.get("campaign_id"),
                "title": campaign.get("title"),
                "author": campaign.get("author") or "NicoMrx",
                "signature": campaign.get("signature") or "NicoMrx",
                "status": campaign.get("preregistration", {}).get("status", "draft"),
                "condition_count": campaign.get("condition_count", len(campaign.get("conditions", []))),
                "run_count": campaign.get("run_count", 0),
            }
        )
    return rows
