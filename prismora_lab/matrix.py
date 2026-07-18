from __future__ import annotations

import copy
import itertools
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .canonical import sha256_json


_TEMPLATE = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


class MatrixError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlannedRun:
    run_id: str
    experiment_id: str
    request: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "experiment_id": self.experiment_id, "request": self.request}


def render_template(text: str, factors: dict[str, Any]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in factors:
            missing.add(key)
            return match.group(0)
        value = factors[key]
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    rendered = _TEMPLATE.sub(replace, text)
    if missing:
        raise MatrixError(f"Missing template factors: {', '.join(sorted(missing))}")
    return rendered


def _factor_combinations(factors: dict[str, list[Any]]) -> Iterable[dict[str, Any]]:
    if not factors:
        yield {}
        return
    names = sorted(factors)
    values = [factors[name] for name in names]
    for combination in itertools.product(*values):
        yield dict(zip(names, combination, strict=True))


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current: dict[str, Any] = target
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise MatrixError(f"Cannot bind factor through non-object path: {path}")
        current = child
    current[parts[-1]] = value


def _render_prompt(prompt_spec: dict[str, Any], factors: dict[str, Any]) -> dict[str, Any]:
    if "prompt" in prompt_spec:
        return {"prompt": render_template(prompt_spec["prompt"], factors)}
    chat: list[dict[str, str]] = []
    for message in prompt_spec["chat"]:
        chat.append({"role": message["role"], "content": render_template(message["content"], factors)})
    return {"chat": chat}


def planned_request_identity(request: dict[str, Any]) -> dict[str, Any]:
    """Fields that define a planned observation, excluding mutable run status."""
    return request


def expand_experiment(spec: dict[str, Any]) -> list[PlannedRun]:
    matrix = spec.get("matrix", {})
    factors = matrix.get("factors", {})
    bindings = matrix.get("bindings", {})
    repeats = int(matrix.get("repeats", 1))
    runs: list[PlannedRun] = []
    seen: set[str] = set()

    for model, prompt_spec, factor_values, repeat in itertools.product(
        spec["models"],
        spec["prompts"],
        _factor_combinations(factors),
        range(1, repeats + 1),
    ):
        request: dict[str, Any] = {
            "backend": model["backend"],
            "model": copy.deepcopy(model),
            "prompt_id": prompt_spec["prompt_id"],
            "factors": copy.deepcopy(factor_values),
            "repeat": repeat,
            "generation": copy.deepcopy(spec["generation"]),
            "readout": copy.deepcopy(spec["readout"]),
            "intervention": copy.deepcopy(spec.get("intervention")),
        }
        request.update(_render_prompt(prompt_spec, factor_values))
        for factor_name, path in bindings.items():
            if factor_name not in factor_values:
                raise MatrixError(f"Binding refers to missing factor: {factor_name}")
            _set_path(request, path, factor_values[factor_name])

        digest = sha256_json({"experiment_id": spec["experiment_id"], "request": planned_request_identity(request)})
        run_id = f"{spec['experiment_id']}__{model['alias']}__{prompt_spec['prompt_id']}__r{repeat}__{digest[:12]}"
        if run_id in seen:
            raise MatrixError(f"Duplicate planned run identity: {run_id}")
        seen.add(run_id)
        runs.append(PlannedRun(run_id=run_id, experiment_id=spec["experiment_id"], request=request))
    return runs


def plan_summary(spec: dict[str, Any], runs: list[PlannedRun]) -> dict[str, Any]:
    by_backend: dict[str, int] = {}
    by_model: dict[str, int] = {}
    warnings: list[str] = []
    for run in runs:
        backend = run.request["backend"]
        alias = run.request["model"]["alias"]
        by_backend[backend] = by_backend.get(backend, 0) + 1
        by_model[alias] = by_model.get(alias, 0) + 1
        if run.request["readout"].get("top_k", 8) > 8 and backend == "neuronpedia":
            warnings.append(f"{run.run_id}: Neuronpedia currently documents top_k <= 8.")
        if run.request["generation"].get("max_new_tokens", 0) > 256 and backend == "neuronpedia":
            warnings.append(f"{run.run_id}: Neuronpedia currently documents max_new_tokens <= 256.")
    if spec.get("preregistration", {}).get("status") != "locked":
        warnings.append("The experiment is still draft; results must not be described as preregistered.")
    return {
        "experiment_id": spec["experiment_id"],
        "run_count": len(runs),
        "by_backend": by_backend,
        "by_model": by_model,
        "warnings": sorted(set(warnings)),
    }
