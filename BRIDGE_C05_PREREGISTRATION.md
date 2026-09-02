# Campaign 05 — Bridge validation: Neuronpedia Free Chat (July 2026) ↔ interp-engine ↔ HF + jlens

Status: **PRE-REGISTERED, NOT RUN.** Frozen on 2026-09-02, before any GPU was rented.
Applies the rule in `CLOUD_GPU_GUIDE.md` → "Bridge validation before cross-backend merging".
This is the preliminary sub-step of the calibration milestone (20 tests / 60 runs) promised in
the BlueDot Rapid Grant application of 2026-09-01; it decides which backend the calibration runs on.

## 1. Pinned identities (to fill with exact values before the first run — no run without them)

| item | value |
|---|---|
| model | `Qwen/Qwen3.6-27B` — revision: `<commit>` |
| tokenizer | same repo — revision: `<commit>` |
| lens | `neuronpedia/jacobian-lens` → `qwen3.6-27b/jlens/Salesforce-wikitext/Qwen3.6-27B_jacobian_lens_n1000.pt` — revision: `<commit>` |
| lens SHA-256 | `1718c8c52dd8a9dad03738d4d625937c1fbba10be325b872ed446c7290fc11e1` (found by Pepper on HF, 2026-09-02; **re-verify at download**) |
| lens shape expected | `[64, 5120, 5120]` (a `23 × 2880` file under this path is the wrong checkpoint) |
| precision | bf16 weights on every backend; lens transport in float32 |
| mirror model | `openai/gpt-oss-20b` — revision `<commit>`, `interp-engine[quant]` installed (MXFP4) |
| engine | `interp-engine==<x.y.z>` (1.5.1 at freeze), `jlens@581d398613e5602a5af361e1c34d3a92ea82ba8e` |

## 2. Replay set (archived Free Chat exports, md5 recorded at acquisition)

| id | model | export | claim it supports |
|---|---|---|---|
| R1 | Qwen3.6-27B | maths pair x²−5x+c (c=6) | C1 dead early band, C4 lens convergence L≥56 |
| R2 | Qwen3.6-27B | Tiananmen, 230 tokens, T=0 | C6 computed-not-emitted |
| R3 | Qwen3.6-27B | "how do you see humans", 256 tokens | plan-in-reading 矛盾 L57 |
| R4 | GPT-OSS-20B | Tiananmen mirror | C8 topic gating is Qwen-specific; C4 dissociation |
| R5 | GPT-OSS-20B | "how do you see humans", 256 tokens | CoT-is-a-surface |

For each: the complete `input_token_ids` (prompt + generated) taken from the export, md5 of the export
file, and its Free Chat readouts kept as the reference column.

## 3. Paths compared (per replay id)

| path | runtime | `PRISMORA_IE_BACKEND` | `PRISMORA_IE_CAPTURE_PATH` | generation |
|---|---|---|---|---|
| P0 | Free Chat export (reference) | — | unknown (server) | as archived |
| P1 | `interp_engine_runtime` | `eager` | `recompute` | disabled, exact replay |
| P2 | `interp_engine_runtime` | `vllm` | `recompute` | disabled, exact replay |
| P3 | `interp_engine_runtime` | `vllm-static` | `recompute` | disabled, exact replay |
| P4 | `hf_jlens_runtime` (reference HF) | — | recompute by construction | disabled, exact replay |
| P5 | `interp_engine_runtime` | `vllm` | `incremental` | **enabled**, T=0, same prompt |

Readout on all paths: `top_k=8`, types `JACOBIAN_LENS` + `LOGIT_LENS`, all lens `source_layers`,
`filter_nonword_tokens=false` first (unfiltered), then `true` (Prismora mask) as a second pass.

## 4. Criteria — declared before any result is seen

- **Strong parity (backend accepted for campaign):** on P1–P4 vs P0, identical top-1 on ≥ 99 % of
  cells in the stable band (L ≥ 46 for Qwen; L ≥ 18 for GPT-OSS), unfiltered, both lens types.
- **Weak parity (accepted with declared tolerance):** discrepancies confined to L < 46 (Qwen) / L < 18
  (GPT-OSS), median late-band Δp < 0.001, no top-1 flip on a *claim position* (below).
- **Claim positions that must not flip on any path:** R2 — positions carrying `crackdown`, `天安门`,
  `democracy` in L39–57; R3 — position of `矛盾` at L57; R4 — analysis-channel positions carrying
  `censorship` / `propaganda` / `legitimacy`. A flip on any of these blocks merging for that claim
  until explained (rule 6 of the guide).
- **P5 vs P2 (incremental vs recompute, same engine):** this is the July divergence made
  controllable. Outcome recorded, not judged: (a) reproduces the July depth profile
  (≈95 % / 65 % / 25 % / 12 % top-1 divergence by band) → property of KV-cached bf16 generation,
  stable-band rule becomes a documented result; (b) near-zero divergence → July divergence was a
  server artefact, rule becomes history. Either is publishable.
- **Regeneration check:** P5 must reproduce the archived generated IDs exactly at T=0; if not, the
  chat template / system prompt differs from Free Chat and must be documented before any other run.
- **Filter check:** unfiltered vs Prismora-filtered top-8 differ only by masked non-word tokens;
  any difference in the *unfiltered* ranking between paths is an engine difference, not a filter one.

## 5. Secondary measurements (recorded for the BlueDot allocation)

Per path: model load time; peak VRAM (sampled outside the process); wall time per run; tokens/s on P5;
card hourly price → cost per run. These replace the provisional GPU estimate of the application.

## 6. Artefacts

One `RunArtifact v2` per (replay id × path), compared in Comparison Studio → strict bridge; a
`tolerances_by_precision.json` committed to the repo; the backend decision written to the claim ledger
with the run IDs as evidence. No corpus merge before this file is updated with the outcome.

## 7. Not in scope

Campaign 04 (frozen lexicons, Saudi cell, EN/ZH surface block), 256+ replication of the Western square,
the density ladder. They start only after §4 has an outcome.
