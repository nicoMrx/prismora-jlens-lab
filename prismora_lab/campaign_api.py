from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

from fastapi import Body, HTTPException

from .campaign_store import get_campaign, list_campaigns, save_campaign
from .campaigns import campaign_progress, legacy_campaign_to_plan
from .canonical import sha256_json
from .matrix import expand_experiment
from .normalize import create_run_artifact
from .preregistration import lock_spec
from .timeutil import utc_now_iso


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    value = {key: item for key, item in plan.items() if key != "specs"}
    value["compiled_experiment_ids"] = [spec["experiment_id"] for spec in plan.get("specs", [])]
    return value


def _run_exists(store: Any, experiment_id: str, run_id: str) -> bool:
    try:
        store.get_run(run_id, experiment_id)
        return True
    except FileNotFoundError:
        return False


def _existing_campaign(context: Any, campaign_id: str) -> dict[str, Any] | None:
    try:
        return get_campaign(context.store, campaign_id)
    except FileNotFoundError:
        return None


def _require_locked(campaign: dict[str, Any]) -> None:
    if campaign.get("preregistration", {}).get("status") != "locked":
        raise HTTPException(
            status_code=409,
            detail="Campaign must be locked after a successful preflight before batch execution.",
        )


async def _execute_batch(
    context: Any,
    campaign: dict[str, Any],
    *,
    limit: int,
    condition_id: str | None,
    pace_seconds: float,
) -> dict[str, Any]:
    selected: list[tuple[dict[str, Any], Any]] = []
    for condition in campaign.get("conditions", []):
        if condition_id and condition.get("condition_id") != condition_id:
            continue
        experiment_id = str(condition["experiment_id"])
        spec = context.store.get_experiment(experiment_id)
        for planned in expand_experiment(spec):
            if _run_exists(context.store, experiment_id, planned.run_id):
                continue
            selected.append((condition, planned))
            if len(selected) >= limit:
                break
        if len(selected) >= limit:
            break

    completed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, (condition, planned) in enumerate(selected):
        request = copy.deepcopy(planned.request)
        backend_id = request["backend"]
        backend = context.backends.get(backend_id)
        if not backend:
            errors.append({"run_id": planned.run_id, "condition_id": condition["condition_id"], "error": f"Unknown backend: {backend_id}"})
            continue
        try:
            backend_result = await backend.run(request)
            if len(backend_result.raw_bytes) > context.settings.max_raw_bytes:
                raise ValueError(
                    f"Raw result is {len(backend_result.raw_bytes)} bytes, above PRISMORA_MAX_RAW_BYTES={context.settings.max_raw_bytes}."
                )
            artifact = create_run_artifact(
                store=context.store,
                experiment_id=planned.experiment_id,
                run_id=planned.run_id,
                request=request,
                raw=backend_result.value,
                raw_format=backend.raw_format(),
                raw_bytes=backend_result.raw_bytes,
                raw_content_type=backend_result.content_type,
                backend_environment={
                    "campaign_id": campaign["campaign_id"],
                    "condition_id": condition["condition_id"],
                    "campaign_signature": campaign.get("signature") or "NicoMrx",
                },
            )
            completed.append(
                {
                    "run_id": artifact["run_id"],
                    "experiment_id": artifact["experiment_id"],
                    "condition_id": condition["condition_id"],
                    "status": artifact.get("status"),
                    "independent_observation": artifact.get("quality", {}).get("independent_observation"),
                    "duplicate_of": artifact.get("quality", {}).get("duplicate_of"),
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "run_id": planned.run_id,
                    "experiment_id": planned.experiment_id,
                    "condition_id": condition["condition_id"],
                    "backend": backend_id,
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "status_code": getattr(exc, "status_code", None),
                }
            )
        if pace_seconds and index + 1 < len(selected):
            await asyncio.sleep(pace_seconds)

    status = campaign_progress(campaign, context.store)
    return {
        "campaign_id": campaign["campaign_id"],
        "selected": len(selected),
        "completed": completed,
        "errors": errors,
        "status": status,
    }


def mount_campaign_routes(app: Any, context: Any, package_root: Path) -> None:
    @app.get("/api/demo/campaign-01")
    async def demo_campaign_01() -> dict[str, Any]:
        path = package_root / "demo" / "campaign_01_2026" / "campaign_01.json"
        if not path.exists():
            path = Path(__file__).resolve().parent / "assets" / "demo" / "campaign_01_2026" / "campaign_01.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Campaign 01 demo is not packaged.")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/api/campaigns/legacy/preview")
    async def preview_legacy_campaign(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            campaign_id = payload.get("campaign_id") if isinstance(payload, dict) else None
            source = payload.get("legacy") if isinstance(payload, dict) and isinstance(payload.get("legacy"), dict) else payload
            plan = legacy_campaign_to_plan(source, campaign_id=campaign_id, author="NicoMrx")
            return _public_plan(plan)
        except Exception as exc:
            raise _error(exc) from exc

    @app.post("/api/campaigns/legacy/save")
    async def save_legacy_campaign(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            campaign_id = payload.get("campaign_id") if isinstance(payload, dict) else None
            source = payload.get("legacy") if isinstance(payload, dict) and isinstance(payload.get("legacy"), dict) else payload
            plan = legacy_campaign_to_plan(source, campaign_id=campaign_id, author="NicoMrx")
            existing = _existing_campaign(context, plan["campaign_id"])
            if existing and existing.get("preregistration", {}).get("status") == "locked":
                if existing.get("source", {}).get("sha256") != plan.get("source", {}).get("sha256"):
                    raise HTTPException(
                        status_code=409,
                        detail="Locked campaign is immutable. Use a new campaign_id for an amended protocol.",
                    )
                return campaign_progress(existing, context.store)
            for spec in plan["specs"]:
                context.store.save_experiment(spec)
            save_campaign(context.store, plan)
            return campaign_progress(get_campaign(context.store, plan["campaign_id"]), context.store)
        except Exception as exc:
            raise _error(exc) from exc

    @app.get("/api/campaigns")
    async def campaigns() -> dict[str, Any]:
        return {"campaigns": list_campaigns(context.store)}

    @app.get("/api/campaigns/{campaign_id}")
    async def campaign_status(campaign_id: str) -> dict[str, Any]:
        try:
            campaign = get_campaign(context.store, campaign_id)
            return campaign_progress(campaign, context.store)
        except Exception as exc:
            raise _error(exc) from exc

    @app.post("/api/campaigns/{campaign_id}/lock")
    async def lock_campaign(campaign_id: str) -> dict[str, Any]:
        try:
            campaign = get_campaign(context.store, campaign_id)
            current = campaign_progress(campaign, context.store)
            if current["completed_runs"] < 1:
                raise HTTPException(
                    status_code=409,
                    detail="Complete at least one successful preflight run before locking the campaign.",
                )
            if campaign.get("preregistration", {}).get("status") == "locked":
                return current
            hashes: list[str] = []
            for condition in campaign.get("conditions", []):
                spec = context.store.get_experiment(condition["experiment_id"])
                if spec.get("preregistration", {}).get("status") != "locked":
                    spec = lock_spec(spec)
                    context.store.save_experiment(spec)
                hashes.append(str(spec["preregistration"]["spec_sha256"]))
            campaign["preregistration"] = {
                "status": "locked",
                "locked_at": utc_now_iso(),
                "spec_sha256": sha256_json({"campaign_id": campaign_id, "experiment_hashes": hashes}),
            }
            campaign["author"] = "NicoMrx"
            campaign["signature"] = "NicoMrx"
            save_campaign(context.store, campaign)
            return campaign_progress(campaign, context.store)
        except Exception as exc:
            raise _error(exc) from exc

    @app.post("/api/campaigns/{campaign_id}/preflight")
    async def preflight_campaign(campaign_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        try:
            campaign = get_campaign(context.store, campaign_id)
            condition_id = payload.get("condition_id")
            return await _execute_batch(
                context,
                campaign,
                limit=1,
                condition_id=str(condition_id) if condition_id else None,
                pace_seconds=0,
            )
        except Exception as exc:
            raise _error(exc) from exc

    @app.post("/api/campaigns/{campaign_id}/execute")
    async def execute_campaign(campaign_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        try:
            campaign = get_campaign(context.store, campaign_id)
            _require_locked(campaign)
            limit = max(1, min(int(payload.get("limit", 1)), context.settings.max_runs_per_request))
            pace_seconds = max(0.0, min(float(payload.get("pace_seconds", 3)), 30.0))
            condition_id = payload.get("condition_id")
            return await _execute_batch(
                context,
                campaign,
                limit=limit,
                condition_id=str(condition_id) if condition_id else None,
                pace_seconds=pace_seconds,
            )
        except Exception as exc:
            raise _error(exc) from exc
