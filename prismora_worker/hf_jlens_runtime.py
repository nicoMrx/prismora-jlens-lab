"""Reference readout-only HuggingFace + Anthropic ``jlens`` worker runtime.

This optional runtime is deliberately conservative:

* it loads one pinned model/tokenizer/lens at worker startup;
* it generates once, then records the *exact resulting token IDs* in a second
  hooks-visible forward pass;
* it implements Jacobian- and vanilla-logit-lens readouts;
* it rejects interventions and unsupported generation settings rather than
  silently approximating them.

The implementation follows the public ``jlens`` reference API released by
Anthropic in July 2026. It is not imported by the base installation; install
``requirements-gpu.txt`` in the GPU image and set
``PRISMORA_WORKER_RUNTIME=prismora_worker.hf_jlens_runtime:create_runtime``.
"""

from __future__ import annotations

import asyncio
import os
import unicodedata
from dataclasses import dataclass
from typing import Any


class RuntimeConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HFJLENSConfig:
    model_id: str
    model_revision: str | None
    tokenizer_revision: str | None
    lens_name_or_path: str
    lens_filename: str
    lens_revision: str | None
    dtype: str
    device_map: str | None
    trust_remote_code: bool
    force_bos: bool
    allow_cpu: bool
    max_input_tokens: int
    max_new_tokens: int
    max_top_k: int
    attn_implementation: str | None

    @classmethod
    def from_env(cls) -> "HFJLENSConfig":
        def required(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise RuntimeConfigurationError(f"{name} is required for the HF J-Lens runtime")
            return value

        def optional(name: str) -> str | None:
            value = os.getenv(name, "").strip()
            return value or None

        def boolean(name: str, default: bool) -> bool:
            value = os.getenv(name)
            if value is None:
                return default
            value = value.strip().lower()
            if value in {"1", "true", "yes", "on"}:
                return True
            if value in {"0", "false", "no", "off"}:
                return False
            raise RuntimeConfigurationError(f"{name} must be true/false")

        return cls(
            model_id=required("PRISMORA_HF_MODEL_ID"),
            model_revision=optional("PRISMORA_HF_MODEL_REVISION"),
            tokenizer_revision=optional("PRISMORA_HF_TOKENIZER_REVISION") or optional("PRISMORA_HF_MODEL_REVISION"),
            lens_name_or_path=required("PRISMORA_JLENS_NAME_OR_PATH"),
            lens_filename=os.getenv("PRISMORA_JLENS_FILENAME", "lens.pt").strip() or "lens.pt",
            lens_revision=optional("PRISMORA_JLENS_REVISION"),
            dtype=os.getenv("PRISMORA_HF_DTYPE", "bfloat16").strip().lower(),
            device_map=optional("PRISMORA_HF_DEVICE_MAP"),
            trust_remote_code=boolean("PRISMORA_HF_TRUST_REMOTE_CODE", False),
            force_bos=boolean("PRISMORA_HF_FORCE_BOS", True),
            allow_cpu=boolean("PRISMORA_HF_ALLOW_CPU", False),
            max_input_tokens=int(os.getenv("PRISMORA_HF_MAX_INPUT_TOKENS", "512")),
            max_new_tokens=int(os.getenv("PRISMORA_HF_MAX_NEW_TOKENS", "512")),
            max_top_k=int(os.getenv("PRISMORA_HF_MAX_TOP_K", "16")),
            attn_implementation=optional("PRISMORA_HF_ATTN_IMPLEMENTATION"),
        )


class HFJacobianLensRuntime:
    is_mock = False

    def __init__(self, config: HFJLENSConfig | None = None) -> None:
        self.config = config or HFJLENSConfig.from_env()
        try:
            import jlens
            import torch
            import transformers
        except ImportError as exc:  # pragma: no cover - optional GPU dependencies
            raise RuntimeConfigurationError(
                "Install requirements-gpu.txt and Anthropic's jlens package in the worker image"
            ) from exc

        self.torch = torch
        self.transformers = transformers
        self.jlens = jlens
        if not torch.cuda.is_available() and not self.config.allow_cpu:
            raise RuntimeConfigurationError(
                "CUDA is unavailable. Set PRISMORA_HF_ALLOW_CPU=true only for tiny validation models."
            )
        dtype_map = {
            "float32": torch.float32,
            "fp32": torch.float32,
            "float16": torch.float16,
            "fp16": torch.float16,
            "bfloat16": torch.bfloat16,
            "bf16": torch.bfloat16,
        }
        if self.config.dtype not in dtype_map:
            raise RuntimeConfigurationError(f"Unsupported PRISMORA_HF_DTYPE={self.config.dtype!r}")
        dtype = dtype_map[self.config.dtype]

        common: dict[str, Any] = {
            "revision": self.config.model_revision,
            "trust_remote_code": self.config.trust_remote_code,
        }
        if self.config.attn_implementation:
            common["attn_implementation"] = self.config.attn_implementation
        if self.config.device_map:
            common["device_map"] = self.config.device_map
        # Transformers 5.5 uses `dtype`; older compatible versions may still
        # accept it. The GPU requirements pin the public reference minimum.
        common["dtype"] = dtype
        common = {key: value for key, value in common.items() if value is not None}

        self.hf_model = transformers.AutoModelForCausalLM.from_pretrained(self.config.model_id, **common)
        if not self.config.device_map:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.hf_model.to(device)
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            self.config.model_id,
            revision=self.config.tokenizer_revision,
            trust_remote_code=self.config.trust_remote_code,
        )
        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token_id is not None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        self.model = jlens.from_hf(
            self.hf_model,
            self.tokenizer,
            force_bos=self.config.force_bos,
        )
        self.lens = jlens.JacobianLens.from_pretrained(
            self.config.lens_name_or_path,
            filename=self.config.lens_filename,
            revision=self.config.lens_revision,
        )
        if self.lens.d_model != self.model.d_model:
            raise RuntimeConfigurationError(
                f"Lens d_model={self.lens.d_model} does not match model d_model={self.model.d_model}"
            )
        output_embeddings = self.hf_model.get_output_embeddings()
        if output_embeddings is None or not hasattr(output_embeddings, "weight"):
            raise RuntimeConfigurationError("Could not determine the model output vocabulary size")
        self.vocab_size = int(output_embeddings.weight.shape[0])
        self.runtime_id = f"hf-jlens:{self.config.model_id}"
        self._decoded_vocab: list[str] | None = None
        self._word_mask_by_device: dict[str, Any] = {}

    async def capabilities(self) -> dict[str, Any]:
        return {
            "schema": "prismora.backend-capabilities/v1",
            "backend_id": "worker",
            "available": True,
            "mock": False,
            "readouts": ["LOGIT_LENS", "JACOBIAN_LENS"],
            "interventions": [],
            "forced_tokens": True,
            "fit_lens": False,
            "supports_chat": True,
            "supports_completion": True,
            "models": [self.config.model_id],
            "limits": {
                "max_new_tokens": self.config.max_new_tokens,
                "max_top_k": self.config.max_top_k,
                "max_input_tokens": self.config.max_input_tokens,
                "max_batch_runs": 1,
            },
            "runtime": {
                "runtime_id": self.runtime_id,
                "model_revision": self.config.model_revision,
                "tokenizer_revision": self.config.tokenizer_revision,
                "lens_name_or_path": self.config.lens_name_or_path,
                "lens_filename": self.config.lens_filename,
                "lens_revision": self.config.lens_revision,
                "dtype": self.config.dtype,
                "source_layers": list(self.lens.source_layers),
                "n_layers": self.model.n_layers,
                "d_model": self.model.d_model,
            },
            "notes": [
                "Reference readout-only runtime built around Anthropic jlens.",
                "Generation and exact-token replay are supported; interventions and lens fitting are rejected.",
                "filter_nonword_tokens uses Prismora unicode-word-mask/v1, not an assumed Neuronpedia-identical filter.",
            ],
        }

    async def run(self, request: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._run_sync, request)

    def _validate_request(self, request: dict[str, Any]) -> tuple[list[str], int, bool]:
        model_id = request.get("model", {}).get("model_id")
        if model_id != self.config.model_id:
            raise ValueError(f"Worker is pinned to {self.config.model_id!r}, not {model_id!r}")
        intervention = request.get("intervention")
        if intervention and intervention.get("mode", "none") != "none":
            raise ValueError("This reference runtime is readout-only and rejects interventions")
        generation = request.get("generation", {})
        if float(generation.get("frequency_penalty", 0) or 0) != 0:
            raise ValueError("frequency_penalty is unsupported and will not be approximated")
        max_new = int(generation.get("max_new_tokens", 0))
        if not 0 <= max_new <= self.config.max_new_tokens:
            raise ValueError(f"max_new_tokens must be in [0,{self.config.max_new_tokens}]")
        readout = request.get("readout", {})
        top_k = int(readout.get("top_k", 8))
        if not 1 <= top_k <= self.config.max_top_k:
            raise ValueError(f"top_k must be in [1,{self.config.max_top_k}]")
        types = list(readout.get("types") or ["JACOBIAN_LENS", "LOGIT_LENS"])
        unknown = set(types) - {"JACOBIAN_LENS", "LOGIT_LENS"}
        if unknown:
            raise ValueError(f"Unsupported readout types: {sorted(unknown)}")
        return types, top_k, bool(readout.get("filter_nonword_tokens", True))

    def _input_ids(self, request: dict[str, Any]):
        torch = self.torch
        readout = request.get("readout", {})
        forced = readout.get("input_token_ids")
        if forced is not None:
            if not isinstance(forced, list) or not forced or not all(isinstance(item, int) for item in forced):
                raise ValueError("readout.input_token_ids must be a non-empty integer array")
            if len(forced) > self.config.max_input_tokens:
                raise ValueError("input_token_ids exceeds configured max input length")
            return torch.tensor([forced], dtype=torch.long, device=self.model.input_device)

        generation = request.get("generation", {})
        prepend_bos = bool(generation.get("prepend_bos", True))
        if "chat" in request:
            kwargs: dict[str, Any] = {
                "tokenize": True,
                "add_generation_prompt": True,
                "return_tensors": "pt",
            }
            enable_thinking = bool(generation.get("enable_thinking", False))
            try:
                ids = self.tokenizer.apply_chat_template(
                    request["chat"], enable_thinking=enable_thinking, **kwargs
                )
            except TypeError:
                if enable_thinking:
                    raise ValueError("Tokenizer chat template does not expose enable_thinking")
                ids = self.tokenizer.apply_chat_template(request["chat"], **kwargs)
            if hasattr(ids, "input_ids"):
                ids = ids.input_ids
        elif "prompt" in request:
            encoded = self.tokenizer(
                request["prompt"],
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_input_tokens,
                add_special_tokens=prepend_bos,
            )
            ids = encoded.input_ids
        else:
            raise ValueError("Request needs prompt, chat or input_token_ids")
        ids = ids.to(self.model.input_device)
        if ids.shape[1] > self.config.max_input_tokens:
            raise ValueError("Tokenized input exceeds configured max input length")
        bos = getattr(self.tokenizer, "bos_token_id", None)
        if prepend_bos and bos is not None and int(ids[0, 0]) != int(bos):
            prefix = torch.tensor([[bos]], dtype=ids.dtype, device=ids.device)
            ids = torch.cat([prefix, ids], dim=1)
        return ids

    def _generate(self, request: dict[str, Any], input_ids):
        torch = self.torch
        generation = request.get("generation", {})
        max_new = int(generation.get("max_new_tokens", 0))
        if max_new == 0:
            return input_ids
        temperature = float(generation.get("temperature", 0) or 0)
        seed = generation.get("seed")
        if seed is not None:
            torch.manual_seed(int(seed))
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(int(seed))
        kwargs: dict[str, Any] = {
            "max_new_tokens": max_new,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
            "use_cache": True,
        }
        if temperature > 0:
            kwargs["temperature"] = temperature
        attention_mask = torch.ones_like(input_ids)
        with torch.inference_mode():
            return self.hf_model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                **kwargs,
            )

    def _decode_token_id(self, token_id: int) -> str:
        try:
            token = self.tokenizer.decode(
                [token_id],
                skip_special_tokens=False,
                clean_up_tokenization_spaces=False,
            )
        except Exception:
            token = ""
        # Some tied/padded output heads expose rows beyond the tokenizer's
        # declared vocabulary. Preserve the ID instead of returning an empty
        # or misleading string.
        return token if token else f"<id:{token_id}>"

    def _decoded_tokens(self) -> list[str]:
        if self._decoded_vocab is None:
            self._decoded_vocab = [
                self._decode_token_id(token_id) for token_id in range(self.vocab_size)
            ]
        return self._decoded_vocab

    @staticmethod
    def _is_word_like(token: str) -> bool:
        cleaned = token.replace("▁", " ").replace("Ġ", " ").strip()
        if not cleaned:
            return False
        return any(unicodedata.category(char)[0] in {"L", "N"} for char in cleaned)

    def _word_mask(self, device):
        key = str(device)
        mask = self._word_mask_by_device.get(key)
        if mask is None:
            allowed = [self._is_word_like(token) for token in self._decoded_tokens()]
            mask = self.torch.tensor(allowed, dtype=self.torch.bool, device=device)
            self._word_mask_by_device[key] = mask
        return mask

    def _topk(self, logits, top_k: int, filter_nonword: bool):
        torch = self.torch
        logits = logits.float()
        log_norm = torch.logsumexp(logits, dim=-1, keepdim=True)
        ranked = logits
        if filter_nonword:
            # Match the documented public-API invariant as closely as possible:
            # retain the model's unfiltered top-1 even when it is punctuation or
            # a special token, then fill the remaining ranks with word-like IDs.
            mask = self._word_mask(logits.device).unsqueeze(0).expand_as(logits).clone()
            raw_top1 = logits.argmax(dim=-1, keepdim=True)
            mask.scatter_(1, raw_top1, True)
            ranked = logits.masked_fill(~mask, float("-inf"))
        values, ids = ranked.topk(top_k, dim=-1)
        probs = torch.exp(values - log_norm)
        return ids.cpu(), probs.cpu()

    def _run_sync(self, request: dict[str, Any]) -> dict[str, Any]:
        torch = self.torch
        types, top_k, filter_nonword = self._validate_request(request)
        input_ids = self._input_ids(request)
        prompt_len = int(input_ids.shape[1])
        full_ids = self._generate(request, input_ids)
        if int(full_ids.shape[1]) > self.config.max_input_tokens + self.config.max_new_tokens:
            raise ValueError("Combined sequence exceeds configured runtime bound")
        sequence = full_ids[0].tolist()
        positions = len(sequence)
        decoded = self._decoded_tokens()
        token_rows: list[dict[str, Any]] = [
            {
                "kind": "token",
                "position": position,
                "token": decoded[token_id],
                "id": int(token_id),
                "is_generated": position >= prompt_len,
                "results": [
                    {"type": lens_type, "top_tokens": [], "top_probs": []}
                    for lens_type in types
                ],
            }
            for position, token_id in enumerate(sequence)
        ]
        result_maps = [
            {result["type"]: result for result in row["results"]}
            for row in token_rows
        ]

        requested_layers = request.get("readout", {}).get("layers")
        if not requested_layers:
            layers = (
                list(self.lens.source_layers)
                if "JACOBIAN_LENS" in types
                else list(range(self.model.n_layers))
            )
        else:
            layers = sorted({int(layer) for layer in requested_layers})
        out_of_range = [layer for layer in layers if not 0 <= layer < self.model.n_layers]
        if out_of_range:
            raise ValueError(f"Requested layers out of range: {out_of_range}")
        if "JACOBIAN_LENS" in types:
            unavailable = set(layers) - set(self.lens.source_layers)
            if unavailable:
                raise ValueError(f"Requested layers not in fitted lens: {sorted(unavailable)}")
        final_layer = self.model.n_layers - 1
        record_at = sorted(set(layers) | {final_layer})
        exact_ids = full_ids.to(self.model.input_device)
        with torch.inference_mode(), self.jlens.ActivationRecorder(self.model.layers, at=record_at) as recorder:
            self.model.forward(exact_ids)
        activations = {layer: recorder.activations[layer].detach()[0] for layer in record_at}

        for lens_type in types:
            for layer in layers:
                residual = activations[layer].float()
                if lens_type == "JACOBIAN_LENS":
                    residual = self.lens.transport(residual, layer)
                logits = self.model.unembed(residual)
                ids, probs = self._topk(logits, top_k, filter_nonword)
                for position in range(positions):
                    result_maps[position][lens_type]["top_tokens"].append(
                        [decoded[int(token_id)] for token_id in ids[position].tolist()]
                    )
                    result_maps[position][lens_type]["top_probs"].append(
                        [float(value) for value in probs[position].tolist()]
                    )
                del logits, residual, ids, probs

        generated_ids = sequence[prompt_len:]
        completion = self.tokenizer.decode(
            generated_ids,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        temperature = float(request.get("generation", {}).get("temperature", 0) or 0)
        layers_by_type = {lens_type: layers for lens_type in types}
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
                "model_revision": self.config.model_revision,
                "tokenizer_revision": self.config.tokenizer_revision,
                "lens_name_or_path": self.config.lens_name_or_path,
                "lens_filename": self.config.lens_filename,
                "lens_revision": self.config.lens_revision,
                "precision": self.config.dtype,
                "filter_nonword_tokens": filter_nonword,
                "filter_implementation": "prismora-unicode-word-mask/v2-keep-raw-top1" if filter_nonword else None,
                "exact_token_replay": request.get("readout", {}).get("input_token_ids") is not None,
            },
            "tokens": token_rows,
            "done": {
                "kind": "done",
                "seq_len": len(sequence),
                "prompt_len": prompt_len,
                "vocab_size": self.vocab_size,
                "completion": completion,
            },
        }


def create_runtime() -> HFJacobianLensRuntime:
    return HFJacobianLensRuntime()
