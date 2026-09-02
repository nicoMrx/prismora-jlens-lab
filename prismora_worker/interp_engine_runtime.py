"""interp-engine backed J-Lens worker runtime (readout-only, pinned).

Second real runtime behind the unchanged Prismora worker contract
(``/v1/health``, ``/v1/capabilities``, ``/v1/run``). It swaps the model
serving/capture layer of :mod:`prismora_worker.hf_jlens_runtime` for
Neuronpedia's ``interp-engine`` (https://github.com/decoderesearch/interp-engine)
and keeps everything else identical on purpose:

- same request validation, same ``{meta, tokens, done, coverage}`` return shape;
- same Anthropic ``jlens`` package to *apply* the pre-fitted Jacobian lens
  (interp-engine never fits a lens; neither does Prismora);
- same ``prismora-unicode-word-mask/v2-keep-raw-top1`` filter, so a bridge
  comparison against the HF runtime isolates the engine, not the filter.

What is new and declared in every ``meta`` record:

- ``engine``: ``interp-engine`` + version, and ``engine_backend``
  (``eager`` | ``vllm`` | ``vllm-static``);
- ``compute_path``: ``recompute`` (generate, then one full forward over the
  exact final token IDs -- the HF runtime's path) or ``incremental``
  (read-outs taken from the KV-cached generation pass itself). These are the
  two paths whose divergence was observed on Neuronpedia Free Chat in July 2026;
  here they are a switch, not an accident;
- ``lens_sha256``: the SHA-256 of the lens checkpoint actually loaded, when
  ``PRISMORA_JLENS_SHA256`` is set (the load refuses on mismatch);
- ``lens_shape``: ``[n_layers, d_model, d_model]`` as loaded, checked against
  the model.

Environment (in addition to the ``PRISMORA_HF_*`` / ``PRISMORA_JLENS_*``
variables documented in GPU_RUNTIME_REFERENCE.md)::

    PRISMORA_WORKER_RUNTIME='prismora_worker.interp_engine_runtime:create_runtime'
    PRISMORA_IE_BACKEND='eager'          # eager | vllm | vllm-static
    PRISMORA_IE_CAPTURE_PATH='recompute' # recompute | incremental
    PRISMORA_JLENS_SHA256='<64 hex>'     # optional, refuses on mismatch

STATUS: written from a static review of interp-engine 1.5.x and of this
repository on 2026-09-02. NOT executed on CUDA. Not scientific-ready until
it passes the bridge validation in CLOUD_GPU_GUIDE.md against archived
Neuronpedia exports (see docs/c05_bridge_preregistration.md).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from typing import Any

from .hf_jlens_runtime import HFJacobianLensRuntime, HFJLENSConfig, RuntimeConfigurationError

_BACKENDS = ("eager", "vllm", "vllm-static")
_CAPTURE_PATHS = ("recompute", "incremental")


@dataclass
class _ModelFacts:
    """The few attributes the inherited helpers read off ``self.model``."""

    input_device: str
    n_layers: int
    d_model: int


def _sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class InterpEngineJLensRuntime(HFJacobianLensRuntime):
    """Readout-only runtime: interp-engine serves the model, jlens applies the lens."""

    is_mock = False

    def __init__(self, config: HFJLENSConfig | None = None) -> None:  # noqa: PLR0915
        # Deliberately does not call HFJacobianLensRuntime.__init__ (it would load
        # a second copy of the model through transformers).
        self.config = config or HFJLENSConfig.from_env()
        backend = os.environ.get("PRISMORA_IE_BACKEND", "eager").strip().lower()
        if backend not in _BACKENDS:
            raise RuntimeConfigurationError(f"PRISMORA_IE_BACKEND must be one of {_BACKENDS}, got {backend!r}")
        capture_path = os.environ.get("PRISMORA_IE_CAPTURE_PATH", "recompute").strip().lower()
        if capture_path not in _CAPTURE_PATHS:
            raise RuntimeConfigurationError(
                f"PRISMORA_IE_CAPTURE_PATH must be one of {_CAPTURE_PATHS}, got {capture_path!r}"
            )
        expected_lens_sha = os.environ.get("PRISMORA_JLENS_SHA256", "").strip().lower() or None
        if expected_lens_sha is not None and len(expected_lens_sha) != 64:
            raise RuntimeConfigurationError("PRISMORA_JLENS_SHA256 must be a 64-hex SHA-256 or unset")
        expected_shape_raw = os.environ.get("PRISMORA_JLENS_EXPECTED_SHAPE", "").strip()
        expected_lens_shape = None
        if expected_shape_raw:
            try:
                expected_lens_shape = [int(part.strip()) for part in expected_shape_raw.split(",")]
            except ValueError as exc:
                raise RuntimeConfigurationError("PRISMORA_JLENS_EXPECTED_SHAPE must be three comma-separated integers") from exc
            if len(expected_lens_shape) != 3 or any(value <= 0 for value in expected_lens_shape):
                raise RuntimeConfigurationError("PRISMORA_JLENS_EXPECTED_SHAPE must be n_layers,d_model,d_model")
        self.expected_lens_shape = expected_lens_shape

        try:
            import torch
            import interp_engine
            import jlens
            from huggingface_hub import hf_hub_download, snapshot_download
            from transformers import AutoTokenizer
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeConfigurationError(
                "Install interp-engine (pip install 'interp-engine[vllm]' or 'interp-engine'), "
                "Anthropic's jlens package, transformers and huggingface_hub in the worker image"
            ) from exc

        self.torch = torch
        self.jlens = jlens
        self.backend = backend
        self.capture_path = capture_path

        # ---- pin the model snapshot on disk so every backend loads the same bytes
        if os.path.isdir(self.config.model_id):
            model_path = self.config.model_id
        else:
            model_path = snapshot_download(
                self.config.model_id,
                revision=self.config.model_revision,
                allow_patterns=None,
            )
        tokenizer_path = model_path
        if (
            not os.path.isdir(self.config.model_id)
            and self.config.tokenizer_revision
            and self.config.tokenizer_revision != self.config.model_revision
        ):
            tokenizer_path = snapshot_download(
                self.config.model_id,
                revision=self.config.tokenizer_revision,
                allow_patterns=None,
            )
        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_path,
            trust_remote_code=self.config.trust_remote_code,
        )

        # ---- engine
        self.engine_model = interp_engine.load_model(
            model_path,
            backend=backend,
            dtype=self.config.dtype,
            trust_remote_code=self.config.trust_remote_code,
        )
        self._warm = False
        n_layers = int(self.engine_model.n_layers)
        d_model = int(self.engine_model.d_model)
        self.model = _ModelFacts(input_device="cpu", n_layers=n_layers, d_model=d_model)

        # ---- lens: same package and same file as the HF runtime; hash-checked if asked
        lens_local_path: str | None = None
        if os.path.isdir(self.config.lens_name_or_path):
            lens_local_path = os.path.join(self.config.lens_name_or_path, self.config.lens_filename)
        else:
            lens_local_path = hf_hub_download(
                self.config.lens_name_or_path,
                filename=self.config.lens_filename,
                revision=self.config.lens_revision,
            )
        self.lens_sha256 = _sha256_of(lens_local_path)
        if expected_lens_sha is not None and self.lens_sha256 != expected_lens_sha:
            raise RuntimeConfigurationError(
                f"Lens checkpoint SHA-256 {self.lens_sha256} does not match PRISMORA_JLENS_SHA256 {expected_lens_sha}"
            )
        lens_snapshot_dir = os.path.dirname(lens_local_path)
        self.lens = jlens.JacobianLens.from_pretrained(
            lens_snapshot_dir,
            filename=os.path.basename(lens_local_path),
            revision=None,
        )
        if int(self.lens.d_model) != d_model:
            raise RuntimeConfigurationError(
                f"Lens d_model={self.lens.d_model} does not match model d_model={d_model}"
            )
        source_layers = [int(layer) for layer in getattr(self.lens, "source_layers", [])]
        if not source_layers:
            raise RuntimeConfigurationError("Lens exposes no source_layers; refusing to guess its shape")
        if max(source_layers) >= n_layers:
            raise RuntimeConfigurationError(
                f"Lens source_layers reach {max(source_layers)} but model has n_layers={n_layers}"
            )
        # e.g. Qwen3.6-27B: [64, 5120, 5120] expected; a 23 x 2880 file under this path is the
        # wrong-shape checkpoint that once sat in the HF repo (GPT-OSS-20B dimensions).
        self.lens_shape = [len(source_layers), d_model, d_model]
        if self.expected_lens_shape is not None and self.lens_shape != self.expected_lens_shape:
            raise RuntimeConfigurationError(
                f"Lens shape {self.lens_shape} does not match PRISMORA_JLENS_EXPECTED_SHAPE {self.expected_lens_shape}"
            )

        # ---- identity
        vocab = getattr(self.tokenizer, "vocab_size", None) or len(self.tokenizer)
        self.vocab_size = int(vocab)
        self._decoded_vocab: list[str] | None = None
        self._word_mask_by_device: dict[str, Any] = {}
        identity = "|".join(
            str(part)
            for part in (
                self.config.model_id,
                self.config.model_revision,
                self.config.tokenizer_revision,
                self.config.lens_name_or_path,
                self.config.lens_filename,
                self.config.lens_revision,
                self.lens_sha256,
                self.config.dtype,
                backend,
                capture_path,
            )
        )
        identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        self.runtime_id = (
            f"interp-engine-jlens:{self.config.model_id}@{self.config.model_revision or 'local'}"
            f":{backend}:{capture_path}:{identity_hash}"
        )
        self.software_versions = {
            "interp_engine": getattr(interp_engine, "__version__", None),
            "jlens": getattr(jlens, "__version__", None),
            "torch": getattr(torch, "__version__", None),
        }
        self._run_lock = asyncio.Lock()

    # ------------------------------------------------------------------ contract
    async def capabilities(self) -> dict[str, Any]:
        base = await super().capabilities()
        base["runtime"].update(
            {
                "runtime_id": self.runtime_id,
                "engine": "interp-engine",
                "engine_backend": self.backend,
                "compute_path": self.capture_path,
                "lens_sha256": self.lens_sha256,
                "lens_shape": self.lens_shape,
                "n_layers": self.model.n_layers,
                "d_model": self.model.d_model,
            }
        )
        base.setdefault("notes", []).append(
            "interp-engine runtime: static review only until bridge validation passes (docs/c05_bridge_preregistration.md)."
        )
        return base

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        async with self._run_lock:
            if not self._warm:
                await self.engine_model.warmup()
                self._warm = True
            return await self._run_async(request)

    # ------------------------------------------------------------------ engine glue
    async def _generate_ids(self, request: dict[str, Any], prompt_ids: list[int]) -> tuple[list[int], dict | None]:
        """Return the full token sequence and, on the incremental path, the captured rows."""
        generation = request.get("generation", {})
        max_new = int(generation.get("max_new_tokens", 0))
        if max_new == 0:
            return prompt_ids, None
        temperature = float(generation.get("temperature", 0) or 0)
        seed = generation.get("seed")
        # capture_generation is used on both paths because it is the only call that
        # returns the exact generated token IDs (generate_text returns text, and
        # re-tokenizing text is not acceptable for exact replay).
        points = [f"resid_post.{layer}" for layer in self._record_at] if self.capture_path == "incremental" else []
        completion, rows = await self.engine_model.capture_generation(
            prompt_ids, points, max_tokens=max_new, temperature=temperature, seed=seed
        )
        full = list(prompt_ids) + [int(t) for t in completion.token_ids]
        return full, (rows if self.capture_path == "incremental" else None)

    async def _run_async(self, request: dict[str, Any]) -> dict[str, Any]:
        torch = self.torch
        types, top_k, filter_nonword, excluded = self._validate_request(request)
        prompt_tensor = self._input_ids(request)  # inherited: prompt/chat/forced ids, BOS rule
        prompt_ids = [int(t) for t in prompt_tensor[0].tolist()]
        prompt_len = len(prompt_ids)

        requested_layers = request.get("readout", {}).get("layers")
        layers = self._validated_layers(requested_layers, types)
        final_layer = self.model.n_layers - 1
        self._record_at = sorted(set(layers) | {final_layer})

        sequence, incremental_rows = await self._generate_ids(request, prompt_ids)
        if len(sequence) > self.config.max_input_tokens + self.config.max_new_tokens:
            raise ValueError("Combined sequence exceeds configured runtime bound")
        positions = len(sequence)
        decoded = self._decoded_tokens()

        token_rows: list[dict[str, Any]] = [
            {
                "kind": "token",
                "position": position,
                "token": decoded[token_id] if token_id < len(decoded) else f"<id:{token_id}>",
                "id": int(token_id),
                "is_generated": position >= prompt_len,
                "results": [{"type": lens_type, "top_tokens": [], "top_probs": []} for lens_type in types],
            }
            for position, token_id in enumerate(sequence)
        ]
        result_maps = [{result["type"]: result for result in row["results"]} for row in token_rows]

        # ---- activations: recompute = one full forward over the exact final IDs
        if incremental_rows is None:
            points = [f"resid_post.{layer}" for layer in self._record_at]
            captured = await self.engine_model.capture(sequence, points)
            activations = {layer: self._row(captured, layer) for layer in self._record_at}
            captured_positions = positions
        else:
            activations = {layer: self._row(incremental_rows, layer) for layer in self._record_at}
            # capture_generation returns prompt_len + generated_len - 1 rows: the last sampled
            # token is never fed back. Declared in coverage, never padded.
            captured_positions = int(next(iter(activations.values())).shape[0])

        for lens_type in types:
            for layer in layers:
                residual = activations[layer].float()
                if lens_type == "JACOBIAN_LENS" and layer != final_layer:
                    residual = self.lens.transport(residual, layer)
                logits = await self.engine_model.decode_residuals(residual)
                ids, probs = self._topk(logits, top_k, filter_nonword)
                for position in range(captured_positions):
                    if position < excluded:
                        continue
                    result_maps[position][lens_type]["top_tokens"].append(
                        [decoded[int(t)] if int(t) < len(decoded) else f"<id:{int(t)}>" for t in ids[position].tolist()]
                    )
                    result_maps[position][lens_type]["top_probs"].append(
                        [float(v) for v in probs[position].tolist()]
                    )
                del logits, residual, ids, probs

        generated_ids = sequence[prompt_len:]
        completion = self.tokenizer.decode(generated_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        temperature = float(request.get("generation", {}).get("temperature", 0) or 0)
        layers_by_type = {lens_type: layers for lens_type in types}
        truncated = positions - captured_positions
        return {
            "meta": {
                "kind": "meta",
                "model": self.config.model_id,
                "types": types,
                "layers_by_type": layers_by_type,
                "top_n": top_k,
                "prompt_len": prompt_len,
                "num_completion_tokens": len(generated_ids),
                "temperature": temperature,
                "prepend_bos": bool(request.get("generation", {}).get("prepend_bos", True)),
                "reuse_len": 0,
                "backend": "worker",
                "worker_runtime": self.runtime_id,
                "engine": "interp-engine",
                "engine_backend": self.backend,
                "compute_path": self.capture_path,
                "model_revision": self.config.model_revision,
                "tokenizer_revision": self.config.tokenizer_revision,
                "lens_name_or_path": self.config.lens_name_or_path,
                "lens_filename": self.config.lens_filename,
                "lens_revision": self.config.lens_revision,
                "lens_sha256": self.lens_sha256,
                "lens_shape": self.lens_shape,
                "precision": self.config.dtype,
                "quantization": None,
                "filter_nonword_tokens": filter_nonword,
                "filter_implementation": "prismora-unicode-word-mask/v2-keep-raw-top1" if filter_nonword else None,
                "exact_token_replay": request.get("readout", {}).get("input_token_ids") is not None,
                "exclude_first_n_positions": excluded,
                "software_versions": self.software_versions,
            },
            "tokens": token_rows,
            "done": {
                "kind": "done",
                "seq_len": len(sequence),
                "prompt_len": prompt_len,
                "vocab_size": self.vocab_size,
                "completion": completion,
            },
            "coverage": {
                "source_tokens_total": prompt_len,
                "transmitted_tokens": prompt_len,
                "instrumented_tokens": max(0, prompt_len - excluded),
                "instrumented_generated_tokens": max(0, captured_positions - prompt_len - max(0, excluded - prompt_len)),
                "truncated_tokens": truncated,
                "source_messages_total": len(request.get("chat", [])) if "chat" in request else 1,
                "transmitted_messages": len(request.get("chat", [])) if "chat" in request else 1,
                "truncated_message_indices": [],
                "context_window_limit": self.config.max_input_tokens,
                "capture_mode": (
                    "full_returned_positions" if excluded == 0 and truncated == 0 else "partial_positions"
                ),
                "requested_layers": layers,
                "captured_layers": layers,
                "status": "complete" if (excluded == 0 and truncated == 0) else "partial",
                "warnings": (
                    ([f"The first {excluded} sequence positions were intentionally excluded from readout capture."] if excluded else [])
                    + ([f"Incremental path: the final sampled token ({truncated} position) has no read-out."] if truncated else [])
                ),
            },
        }

    def _row(self, captured: dict, layer: int):
        """Fetch a ``[positions, d_model]`` tensor for ``resid_post.<layer>`` from a capture dict."""
        for key, value in captured.items():
            name = getattr(key, "name", None) or str(key).split(".")[0]
            key_layer = getattr(key, "layer", None)
            if key_layer is None:
                tail = str(key).split(".")[-1]
                key_layer = int(tail) if tail.isdigit() else None
            if name == "resid_post" and key_layer == layer:
                return value
        raise KeyError(f"resid_post.{layer} missing from capture")


def create_runtime() -> InterpEngineJLensRuntime:
    return InterpEngineJLensRuntime()
