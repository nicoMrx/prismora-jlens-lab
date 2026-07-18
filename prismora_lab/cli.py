from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .api.app import create_app
from .backends.mock import MockBackend
from .backends.neuronpedia import NeuronpediaBackend
from .canonical import read_json
from .config import Settings
from .legacy import import_legacy_campaign
from .matrix import expand_experiment, plan_summary
from .normalize import create_run_artifact
from .schema import validate
from .store import LabStore


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        value = yaml.safe_load(text)
    else:
        value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Document root must be an object")
    return value


def _cmd_validate(args: argparse.Namespace) -> int:
    value = _load_document(Path(args.path))
    validate(args.kind, value)
    print(f"OK: {args.kind} schema")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    spec = _load_document(Path(args.path))
    validate("experiment", spec)
    runs = expand_experiment(spec)
    output = {"summary": plan_summary(spec, runs), "runs": [run.as_dict() for run in runs]}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


async def _run_async(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    store = LabStore(Path(args.data_dir).resolve() if args.data_dir else settings.data_dir)
    spec = _load_document(Path(args.path))
    validate("experiment", spec)
    store.save_experiment(spec)
    runs = expand_experiment(spec)
    if args.backend:
        runs = [run for run in runs if run.request["backend"] == args.backend]
    runs = runs[: args.limit]
    if not runs:
        print("No matching runs.")
        return 1
    backend_map = {
        "mock": MockBackend(),
        "neuronpedia": NeuronpediaBackend(
            api_key=settings.neuronpedia_api_key,
            base_url=settings.neuronpedia_base_url,
            timeout_seconds=settings.neuronpedia_timeout_seconds,
            max_retries=settings.neuronpedia_max_retries,
        ),
    }
    for planned in runs:
        backend = backend_map.get(planned.request["backend"])
        if not backend:
            raise RuntimeError(f"CLI backend not available: {planned.request['backend']}")
        backend_result = await backend.run(planned.request)
        artifact = create_run_artifact(
            store=store,
            experiment_id=planned.experiment_id,
            run_id=planned.run_id,
            request=planned.request,
            raw=backend_result.value,
            raw_format=backend.raw_format(),
            raw_bytes=backend_result.raw_bytes,
            raw_content_type=backend_result.content_type,
        )
        print(
            json.dumps(
                {
                    "run_id": artifact["run_id"],
                    "independent_observation": artifact["quality"]["independent_observation"],
                    "duplicate_of": artifact["quality"]["duplicate_of"],
                },
                ensure_ascii=False,
            )
        )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    return asyncio.run(_run_async(args))


def _cmd_serve(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    host = args.host or settings.host
    port = args.port or settings.port
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print("WARNING: Prismora v0.2 has no user authentication. Protect non-local bindings with a reverse proxy.")
    import uvicorn

    if args.reload:
        uvicorn.run("prismora_lab.api.app:create_app", factory=True, host=host, port=port, reload=True)
    else:
        uvicorn.run(create_app(settings), host=host, port=port, reload=False)
    return 0


def _cmd_bundle(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    store = LabStore(Path(args.data_dir).resolve() if args.data_dir else settings.data_dir)
    path = store.build_bundle(args.experiment_id)
    print(path)
    return 0



def _cmd_import_legacy(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    store = LabStore(Path(args.data_dir).resolve() if args.data_dir else settings.data_dir)
    report = import_legacy_campaign(
        protocol_path=Path(args.protocol),
        raw_dir=Path(args.raw_dir),
        store=store,
        experiment_prefix=args.experiment_prefix,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prismora-lab", description="Prismora J-Lens Lab")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="Validate a JSON/YAML document")
    validate_parser.add_argument("kind", choices=["experiment", "run", "capabilities", "claim"])
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=_cmd_validate)

    plan_parser = sub.add_parser("plan", help="Expand an ExperimentSpec into deterministic planned runs")
    plan_parser.add_argument("path")
    plan_parser.set_defaults(func=_cmd_plan)

    run_parser = sub.add_parser("run", help="Execute a small synchronous batch")
    run_parser.add_argument("path")
    run_parser.add_argument("--backend", choices=["mock", "neuronpedia"])
    run_parser.add_argument("--limit", type=int, default=1)
    run_parser.add_argument("--data-dir")
    run_parser.set_defaults(func=_cmd_run)

    serve_parser = sub.add_parser("serve", help="Start the local control plane and interface")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.set_defaults(func=_cmd_serve)

    bundle_parser = sub.add_parser("bundle", help="Build a reproducibility ZIP for an experiment")
    bundle_parser.add_argument("experiment_id")
    bundle_parser.add_argument("--data-dir")
    bundle_parser.set_defaults(func=_cmd_bundle)

    legacy_parser = sub.add_parser("import-legacy", help="Import v0.1 protocol.csv plus original raw JSON")
    legacy_parser.add_argument("--protocol", required=True)
    legacy_parser.add_argument("--raw-dir", required=True)
    legacy_parser.add_argument("--experiment-prefix", required=True)
    legacy_parser.add_argument("--data-dir")
    legacy_parser.set_defaults(func=_cmd_import_legacy)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        code = args.func(args)
    except Exception as exc:
        parser.exit(2, f"ERROR: {type(exc).__name__}: {exc}\n")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
