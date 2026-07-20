from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
import httpx
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..analysis.baseline import build_top1_reference_distribution
from ..analysis.compare import bridge_equivalence, readout_filter_effect, strict_comparison_facts, top1_agreement_by_layer
from ..analysis.understand import understand_compare, understand_run
from ..backends.base import BackendError, ExecutionBackend
from ..backends.mock import MockBackend
from ..backends.neuronpedia import NeuronpediaBackend
from ..backends.worker_http import WorkerHTTPBackend
from ..canonical import canonical_json_bytes, sha256_json
from ..cockpit import to_cockpit_v1
from ..config import Settings
from ..demo import verify_demo_manifest
from ..matrix import MatrixError, expand_experiment, plan_summary
from ..normalize import RawShapeError, create_run_artifact
from ..preregistration import lock_spec, verify_locked_spec
from ..protocol_tools import make_filter_replay_spec
from ..schema import SchemaValidationError, load_schema, validate, validation_report
from ..store import LabStore
from ..timeutil import utc_now_iso


@dataclass(slots=True)
class SessionSettings:
    display_name: str = ""
    locale: str = "en"
    theme: str = "system"
    worker_url: str | None = None
    neuronpedia_api_key: str | None = None
    neuronpedia_connected: bool = False


@dataclass(slots=True)
class LabContext:
    settings: Settings
    store: LabStore
    backends: dict[str, ExecutionBackend]
    examples_dir: Path
    session: SessionSettings = field(default_factory=SessionSettings)


def _default_backends(settings: Settings) -> dict[str, ExecutionBackend]:
    return {
        "mock": MockBackend(),
        "neuronpedia": NeuronpediaBackend(
            api_key=settings.neuronpedia_api_key,
            base_url=settings.neuronpedia_base_url,
            timeout_seconds=settings.neuronpedia_timeout_seconds,
            max_retries=settings.neuronpedia_max_retries,
        ),
        "worker": WorkerHTTPBackend(base_url=settings.worker_url, token=settings.worker_token),
    }


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SchemaValidationError):
        return HTTPException(status_code=422, detail={"message": str(exc), "errors": exc.errors})
    if isinstance(exc, (MatrixError, RawShapeError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, BackendError):
        return HTTPException(
            status_code=exc.status_code or 502,
            detail={"message": str(exc), "details": exc.details},
        )
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


def create_app(
    settings: Settings | None = None,
    *,
    store: LabStore | None = None,
    backends: dict[str, ExecutionBackend] | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or LabStore(settings.data_dir)
    package_root = Path(__file__).resolve().parents[2]
    package_dir = Path(__file__).resolve().parents[1]
    examples_dir = package_root / "examples"
    web_root = package_root / "web"
    if not examples_dir.exists():
        examples_dir = package_dir / "assets" / "examples"
    if not web_root.exists():
        web_root = package_dir / "assets" / "web"
    context = LabContext(
        settings=settings,
        store=store,
        backends=backends or _default_backends(settings),
        examples_dir=examples_dir,
    )

    app = FastAPI(
        title="Prismora J-Lens Lab",
        version="0.2.0",
        description="Backend-neutral control plane for reproducible J-Lens experiments.",
    )
    app.state.lab = context

    @app.exception_handler(SchemaValidationError)
    async def schema_error_handler(_request, exc: SchemaValidationError):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=422, content={"detail": {"message": str(exc), "errors": exc.errors}})


    def public_session_settings() -> dict[str, Any]:
        return {
            "display_name": context.session.display_name,
            "locale": context.session.locale,
            "theme": context.session.theme,
            "worker_url": context.session.worker_url,
            "neuronpedia_connected": context.session.neuronpedia_connected,
            "backends": sorted(context.backends),
            "models": [],
        }

    @app.get("/api/session/settings")
    async def get_session_settings() -> dict[str, Any]:
        return public_session_settings()

    @app.put("/api/session/settings")
    async def put_session_settings(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        if "display_name" in payload:
            context.session.display_name = str(payload.get("display_name") or "")[:120]
        if payload.get("locale") in {"en", "fr"}:
            context.session.locale = payload["locale"]
        if payload.get("theme") in {"system", "dark", "light"}:
            context.session.theme = payload["theme"]
        if "worker_url" in payload:
            context.session.worker_url = str(payload.get("worker_url") or "") or None
        api_key = payload.get("neuronpedia_api_key")
        if api_key is not None:
            context.session.neuronpedia_api_key = str(api_key) or None
            context.session.neuronpedia_connected = bool(context.session.neuronpedia_api_key)
            if "neuronpedia" in context.backends:
                context.backends["neuronpedia"] = NeuronpediaBackend(
                    api_key=context.session.neuronpedia_api_key,
                    base_url=context.settings.neuronpedia_base_url,
                    timeout_seconds=context.settings.neuronpedia_timeout_seconds,
                    max_retries=context.settings.neuronpedia_max_retries,
                )
        return public_session_settings()

    @app.delete("/api/session/neuronpedia-key")
    async def delete_session_neuronpedia_key() -> dict[str, Any]:
        context.session.neuronpedia_api_key = None
        context.session.neuronpedia_connected = False
        if "neuronpedia" in context.backends:
            context.backends["neuronpedia"] = NeuronpediaBackend(
                api_key=None,
                base_url=context.settings.neuronpedia_base_url,
                timeout_seconds=context.settings.neuronpedia_timeout_seconds,
                max_retries=context.settings.neuronpedia_max_retries,
            )
        return public_session_settings()

    @app.post("/api/session/neuronpedia/test")
    async def test_session_neuronpedia(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        api_key = str(payload.get("neuronpedia_api_key") or context.session.neuronpedia_api_key or "")
        if not api_key:
            context.session.neuronpedia_connected = False
            return {"neuronpedia_connected": False, "message": "No API key supplied; demo and imports remain available."}
        try:
            async with httpx.AsyncClient(base_url=context.settings.neuronpedia_base_url, timeout=10, follow_redirects=True) as client:
                response = await client.get("/api/health", headers={"x-api-key": api_key})
            connected = response.status_code < 500
        except httpx.HTTPError:
            connected = False
        context.session.neuronpedia_api_key = api_key
        context.session.neuronpedia_connected = connected
        return {"neuronpedia_connected": connected, "message": "Connection test completed."}

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "version": "0.2.0",
            "data_dir": str(context.settings.data_dir),
            "localhost_default": context.settings.host in {"127.0.0.1", "localhost", "::1"},
        }

    @app.get("/api/backends")
    async def list_backends() -> dict[str, Any]:
        rows = []
        for backend_id, backend in context.backends.items():
            try:
                capability = await backend.capabilities()
                validate("capabilities", capability)
            except Exception as exc:  # capability discovery must not take the whole UI down
                capability = {
                    "schema": "prismora.backend-capabilities/v1",
                    "backend_id": backend_id,
                    "available": False,
                    "mock": False,
                    "readouts": [],
                    "interventions": [],
                    "supports_chat": True,
                    "supports_completion": True,
                    "limits": {"max_new_tokens": 0, "max_top_k": 1},
                    "notes": [f"Capability discovery failed: {type(exc).__name__}: {exc}"],
                }
            rows.append(capability)
        return {"backends": rows}

    @app.get("/api/schemas/{kind}")
    async def get_schema(kind: str) -> dict[str, Any]:
        try:
            return load_schema(kind)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/validate/{kind}")
    async def validate_document(kind: str, document: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return validation_report(kind, document)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/examples")
    async def list_examples() -> dict[str, Any]:
        return {"examples": sorted(path.name for path in context.examples_dir.glob("*.json"))}

    @app.get("/api/examples/{filename}")
    async def get_example(filename: str) -> Any:
        safe_name = Path(filename).name
        path = context.examples_dir / safe_name
        if not path.exists() or path.suffix != ".json":
            raise HTTPException(status_code=404, detail="Example not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/demo/build-week")
    async def get_build_week_demo() -> dict[str, Any]:
        try:
            demo_dir = package_root / "demo" / "build_week_2026"
            if not demo_dir.exists():
                raise FileNotFoundError("Build Week demo directory not found")
            payload = verify_demo_manifest(demo_dir)
            return {"schema": "prismora.demo_loader/v1", **payload}
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/demo/build-week/understand/compare")
    async def compare_build_week_demo(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            demo_dir = package_root / "demo" / "build_week_2026"
            verified = verify_demo_manifest(demo_dir)
            artifacts = {artifact["run_id"]: artifact for artifact in verified["artifacts"]}
            for required in ("run_a", "run_b", "lens", "scope", "probability_abs_tolerance"):
                if required not in payload:
                    raise ValueError(f"Missing required comparison field: {required}")
            return understand_compare(
                artifacts[payload["run_a"]], artifacts[payload["run_b"]],
                lens=payload["lens"], scope=payload["scope"], locale=payload.get("locale", "en"),
                probability_abs_tolerance=float(payload["probability_abs_tolerance"]),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Demo run not found: {exc}") from exc
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/experiments")
    async def list_experiments() -> dict[str, Any]:
        return {"experiments": context.store.list_experiments()}

    @app.post("/api/experiments")
    async def save_experiment(spec: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            validate("experiment", spec)
            try:
                existing = context.store.get_experiment(spec["experiment_id"])
            except FileNotFoundError:
                existing = None
            if existing and existing.get("preregistration", {}).get("status") == "locked":
                if sha256_json(existing) != sha256_json(spec):
                    raise HTTPException(
                        status_code=409,
                        detail="Locked experiment is immutable. Create a new experiment_id or a documented amendment.",
                    )
            context.store.save_experiment(spec)
            return {"ok": True, "experiment_id": spec["experiment_id"], "locked": verify_locked_spec(spec)}
        except HTTPException:
            raise
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/experiments/{experiment_id}")
    async def get_experiment(experiment_id: str) -> dict[str, Any]:
        try:
            return context.store.get_experiment(experiment_id)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/experiments/{experiment_id}/lock")
    async def lock_experiment(experiment_id: str) -> dict[str, Any]:
        try:
            spec = context.store.get_experiment(experiment_id)
            locked = lock_spec(spec)
            context.store.save_experiment(locked)
            return {
                "ok": True,
                "experiment_id": experiment_id,
                "locked_at": locked["preregistration"]["locked_at"],
                "spec_sha256": locked["preregistration"]["spec_sha256"],
            }
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/experiments/{experiment_id}/plan")
    async def plan_experiment(experiment_id: str) -> dict[str, Any]:
        try:
            spec = context.store.get_experiment(experiment_id)
            runs = expand_experiment(spec)
            return {
                "summary": plan_summary(spec, runs),
                "runs": [run.as_dict() for run in runs],
            }
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/models")
    async def get_models() -> dict[str, Any]:
        return context.store.get_models()

    @app.post("/api/models")
    async def save_models(registry: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            context.store.save_models(registry)
            return {"ok": True, "count": len(registry.get("models", []))}
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/runs")
    async def list_runs(experiment_id: str | None = Query(default=None)) -> dict[str, Any]:
        return {"runs": context.store.list_runs(experiment_id)}

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str, experiment_id: str | None = Query(default=None)) -> dict[str, Any]:
        try:
            return context.store.get_run(run_id, experiment_id)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/runs/{run_id}/cockpit")
    async def get_cockpit(run_id: str, experiment_id: str | None = Query(default=None)) -> dict[str, Any]:
        try:
            return to_cockpit_v1(context.store.get_run(run_id, experiment_id))
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/runs/{run_id}/understand")
    async def get_understand(run_id: str, experiment_id: str | None = Query(default=None), locale: str = Query(default="en")) -> dict[str, Any]:
        try:
            return understand_run(context.store.get_run(run_id, experiment_id), locale=locale)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/runs/{run_id}/raw")
    async def download_raw(run_id: str, experiment_id: str | None = Query(default=None)) -> FileResponse:
        try:
            artifact = context.store.get_run(run_id, experiment_id)
            path = (context.store.root / artifact["raw"]["relative_path"]).resolve()
            root = context.store.root.resolve()
            if root not in path.parents or not path.exists():
                raise FileNotFoundError(f"Raw artifact not found for {run_id}")
            media_type = str(artifact["raw"].get("content_type") or "application/octet-stream").split(";", 1)[0]
            return FileResponse(path, filename=f"{run_id}.raw.json", media_type=media_type)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/runs/{run_id}/make-filter-replay")
    async def make_filter_replay(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            artifact = context.store.get_run(run_id, payload.get("source_experiment_id"))
            new_id = str(payload.get("experiment_id") or f"{artifact['experiment_id']}-filter-replay")
            spec = make_filter_replay_spec(artifact, experiment_id=new_id, title=payload.get("title"))
            validate("experiment", spec)
            if payload.get("save", True):
                context.store.save_experiment(spec)
            return spec
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/runs/{run_id}/intervene")
    async def intervene_run(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            source = context.store.get_run(run_id, payload.get("source_experiment_id"))
            request = copy.deepcopy(source["request"])
            request["intervention"] = copy.deepcopy(payload["intervention"])
            label = str(payload.get("label", "intervention"))
            request.setdefault("factors", {})["_intervention_label"] = label
            request.setdefault("factors", {})["_source_run_id"] = source["run_id"]
            new_run_id = f"{source['experiment_id']}__intervention__{sha256_json(request)[:16]}"
            backend_id = request["backend"]
            backend = context.backends.get(backend_id)
            if not backend:
                raise ValueError(f"Unknown backend: {backend_id}")
            backend_result = await backend.run(request)
            artifact = create_run_artifact(
                store=context.store,
                experiment_id=source["experiment_id"],
                run_id=new_run_id,
                request=request,
                raw=backend_result.value,
                raw_format=backend.raw_format(),
                raw_bytes=backend_result.raw_bytes,
                raw_content_type=backend_result.content_type,
                backend_environment={"source_run_id": source["run_id"], "intervention_label": label},
            )
            return artifact
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/runs/execute")
    async def execute_runs(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        experiment_id = str(payload.get("experiment_id", ""))
        requested_run_ids = set(payload.get("run_ids") or [])
        force = bool(payload.get("force", False))
        limit = int(payload.get("limit", 1))
        limit = max(1, min(limit, context.settings.max_runs_per_request))
        try:
            spec = context.store.get_experiment(experiment_id)
            planned = expand_experiment(spec)
            if requested_run_ids:
                unknown = requested_run_ids - {run.run_id for run in planned}
                if unknown:
                    raise ValueError(f"Unknown run ids: {sorted(unknown)}")
                planned = [run for run in planned if run.run_id in requested_run_ids]
            selected = []
            for run in planned:
                try:
                    context.store.get_run(run.run_id, experiment_id)
                    exists = True
                except FileNotFoundError:
                    exists = False
                if exists and not force:
                    continue
                selected.append(run)
                if len(selected) >= limit:
                    break

            results: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            for run in selected:
                backend_id = run.request["backend"]
                backend = context.backends.get(backend_id)
                if not backend:
                    errors.append({"run_id": run.run_id, "error": f"Unknown backend: {backend_id}"})
                    continue
                try:
                    backend_result = await backend.run(run.request)
                    raw_size = len(backend_result.raw_bytes)
                    if raw_size > context.settings.max_raw_bytes:
                        raise ValueError(
                            f"Raw result is {raw_size} bytes, above PRISMORA_MAX_RAW_BYTES={context.settings.max_raw_bytes}."
                        )
                    artifact = create_run_artifact(
                        store=context.store,
                        experiment_id=experiment_id,
                        run_id=run.run_id,
                        request=run.request,
                        raw=backend_result.value,
                        raw_format=backend.raw_format(),
                        raw_bytes=backend_result.raw_bytes,
                        raw_content_type=backend_result.content_type,
                        backend_environment={"backend_capability_id": backend_id},
                    )
                    results.append(
                        {
                            "run_id": artifact["run_id"],
                            "status": artifact["status"],
                            "independent_observation": artifact["quality"]["independent_observation"],
                            "duplicate_of": artifact["quality"]["duplicate_of"],
                        }
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "run_id": run.run_id,
                            "backend": backend_id,
                            "error": str(exc),
                            "type": type(exc).__name__,
                            "status_code": getattr(exc, "status_code", None),
                        }
                    )
            return {
                "experiment_id": experiment_id,
                "selected": len(selected),
                "completed": results,
                "errors": errors,
                "remaining_unexecuted": max(0, len(planned) - len(selected)),
            }
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/import/neuronpedia")
    async def import_neuronpedia(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            experiment_id = payload["experiment_id"]
            context.store.get_experiment(experiment_id)
            request = copy.deepcopy(payload["request"])
            request.setdefault("backend", "neuronpedia")
            raw = payload["raw"]
            run_id = payload.get("run_id") or f"{experiment_id}__import__{sha256_json({'request': request, 'raw': raw})[:16]}"
            artifact = create_run_artifact(
                store=context.store,
                experiment_id=experiment_id,
                run_id=run_id,
                request=request,
                raw=raw,
                raw_format="imported-json",
                raw_bytes=canonical_json_bytes(raw),
                raw_content_type="application/json",
                backend_environment={"imported_at": utc_now_iso()},
            )
            return artifact
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/baselines/build")
    async def build_baseline(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            experiment_id = str(payload["experiment_id"])
            run_ids = payload.get("run_ids") or [row["run_id"] for row in context.store.list_runs(experiment_id)]
            if not run_ids:
                raise ValueError("No runs available for the baseline.")
            artifacts = [context.store.get_run(run_id, experiment_id) for run_id in run_ids]
            baseline = build_top1_reference_distribution(
                artifacts,
                lens=payload.get("lens", "JACOBIAN_LENS"),
                position_scope=payload.get("position_scope", "all"),
                max_tokens_per_layer=int(payload.get("max_tokens_per_layer", 30)),
            )
            path = context.store.save_derived(experiment_id, "baselines", baseline["baseline_id"], baseline)
            baseline["stored_relative_path"] = str(path.relative_to(context.store.root))
            return baseline
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/understand/compare")
    async def understand_compare_runs(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            for required in ("run_a", "run_b", "lens", "scope", "probability_abs_tolerance"):
                if required not in payload:
                    raise ValueError(f"Missing required comparison field: {required}")
            run_a = context.store.get_run(payload["run_a"])
            run_b = context.store.get_run(payload["run_b"])
            return understand_compare(
                run_a, run_b, lens=payload["lens"], scope=payload["scope"],
                locale=payload.get("locale", "en"),
                probability_abs_tolerance=float(payload["probability_abs_tolerance"]),
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/compare")
    async def compare_runs(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            run_a = context.store.get_run(payload["run_a"])
            run_b = context.store.get_run(payload["run_b"])
            lens = payload.get("lens", "JACOBIAN_LENS")
            mode = payload.get("mode", "agreement")
            if mode == "agreement":
                return top1_agreement_by_layer(run_a, run_b, lens)
            if mode == "filter_effect":
                return readout_filter_effect(run_a, run_b, lens)
            if mode == "bridge":
                return bridge_equivalence(
                    run_a,
                    run_b,
                    lens,
                    probability_abs_tolerance=float(payload.get("probability_abs_tolerance", 0.01)),
                )
            raise ValueError(f"Unknown comparison mode: {mode}")
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/claims")
    async def list_claims(experiment_id: str | None = Query(default=None)) -> dict[str, Any]:
        return {"claims": context.store.list_claims(experiment_id)}

    @app.post("/api/claims")
    async def save_claim(claim: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            claim = copy.deepcopy(claim)
            claim.setdefault("schema", "prismora.claim/v1")
            claim.setdefault("created_at", utc_now_iso())
            claim.setdefault("updated_at", None)
            claim.setdefault("author", "NicoMrx / Prismora")
            claim.setdefault("evidence_run_ids", [])
            claim.setdefault("limitations", [])
            claim.setdefault("metadata", {})
            context.store.save_claim(claim)
            return {"ok": True, "claim_id": claim["claim_id"]}
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/experiments/{experiment_id}/bundle")
    async def bundle_experiment(experiment_id: str) -> FileResponse:
        try:
            path = context.store.build_bundle(experiment_id)
            return FileResponse(path, filename=path.name, media_type="application/zip")
        except Exception as exc:
            raise _http_error(exc) from exc

    app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
    return app

