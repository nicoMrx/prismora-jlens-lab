from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.metadata
import json
from typing import Any

from .hf_jlens_runtime import HFJLENSConfig, HFJacobianLensRuntime, RuntimeConfigurationError


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def collect_preflight(*, probe_imports: bool = True) -> dict[str, Any]:
    """Collect a non-destructive environment report without loading model weights."""
    errors: list[str] = []
    warnings: list[str] = []
    config: HFJLENSConfig | None = None
    try:
        config = HFJLENSConfig.from_env()
    except Exception as exc:
        errors.append(f"configuration: {type(exc).__name__}: {exc}")

    packages = {
        name: _version(name)
        for name in ("prismora-jlens-lab", "torch", "transformers", "huggingface_hub", "jlens")
    }
    imports: dict[str, str] = {}
    if probe_imports:
        for module_name in ("torch", "transformers", "huggingface_hub", "jlens"):
            try:
                importlib.import_module(module_name)
                imports[module_name] = "ok"
            except Exception as exc:
                imports[module_name] = f"error: {type(exc).__name__}: {exc}"
                errors.append(f"import {module_name}: {type(exc).__name__}: {exc}")

    cuda: dict[str, Any] = {"available": None, "devices": []}
    if imports.get("torch") == "ok":
        import torch

        cuda["available"] = bool(torch.cuda.is_available())
        cuda["runtime_version"] = getattr(torch.version, "cuda", None)
        if torch.cuda.is_available():
            for index in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(index)
                cuda["devices"].append(
                    {
                        "index": index,
                        "name": props.name,
                        "total_memory_bytes": int(props.total_memory),
                        "compute_capability": f"{props.major}.{props.minor}",
                    }
                )
        elif config and not config.allow_cpu:
            errors.append("CUDA is unavailable and PRISMORA_HF_ALLOW_CPU is false")

    config_dict: dict[str, Any] | None = None
    if config:
        config_dict = {
            "model_id": config.model_id,
            "model_revision": config.model_revision,
            "tokenizer_revision": config.tokenizer_revision,
            "lens_name_or_path": config.lens_name_or_path,
            "lens_filename": config.lens_filename,
            "lens_revision": config.lens_revision,
            "dtype": config.dtype,
            "device_map": config.device_map,
            "allow_cpu": config.allow_cpu,
            "max_input_tokens": config.max_input_tokens,
            "max_new_tokens": config.max_new_tokens,
            "max_top_k": config.max_top_k,
        }
        if not config.model_revision:
            warnings.append("PRISMORA_HF_MODEL_REVISION is not pinned")
        if not config.tokenizer_revision:
            warnings.append("PRISMORA_HF_TOKENIZER_REVISION is not pinned")
        if not config.lens_revision and not config.lens_name_or_path.startswith(("/", ".")):
            warnings.append("PRISMORA_JLENS_REVISION is not pinned for the remote lens repository")
        if config.dtype in {"float16", "fp16"}:
            warnings.append("fp16 model precision is recorded but may not match public bf16 read-outs")

    return {
        "ok": not errors,
        "configuration": config_dict,
        "packages": packages,
        "imports": imports,
        "cuda": cuda,
        "warnings": warnings,
        "errors": errors,
    }


async def _load_report() -> dict[str, Any]:
    runtime = HFJacobianLensRuntime()
    return await runtime.capabilities()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a Prismora HuggingFace/J-Lens GPU worker environment."
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Also load model/tokenizer/lens and print worker capabilities (expensive).",
    )
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = collect_preflight()
    if args.load and report["ok"]:
        try:
            report["loaded_capabilities"] = asyncio.run(_load_report())
        except Exception as exc:
            report["ok"] = False
            report["errors"].append(f"runtime load: {type(exc).__name__}: {exc}")
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2))
    raise SystemExit(0 if report["ok"] else 2)


if __name__ == "__main__":
    main()
