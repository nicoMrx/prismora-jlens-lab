# Prismora J-Lens Lab — Contest Release Candidate 1

**Signature:** NicoMrx  
**Frozen on:** 2026-07-21  
**Source branch:** `nicomrx/campaign-center-demo-library`

## Validation evidence

- Full automated suite: **128 passed**, with one known non-blocking Starlette deprecation warning.
- `git diff --check`: clean.
- Local working tree at validation: clean.
- Live Neuronpedia chat verified with Qwen3.6-27B, GPT-OSS-20B and Gemma-3-12B.
- Live run UX verified with an honest elapsed timer; observed Qwen response time: approximately **21 seconds** in the validation environment.
- Campaign 01 preview: **29 conditions**, **3 repetitions**, **87 planned runs**, **2 models**, approximately **324 MB** estimated raw storage.
- Campaign 01 real preflight: **1 completed**, **0 errors**, **86 remaining**.
- The preflight raw and normalized artifact were archived locally through the Prismora campaign pipeline.

## Frozen contest scope

- Progressive Read / Explore / Control interface.
- Local import of Prismora and Neuronpedia artifacts.
- Live single-turn Neuronpedia runs.
- Qwen, GPT-OSS and Gemma live model selection.
- Immutable raw preservation and normalized human-readable artifacts.
- Technical channel-marker separation, including GPT-OSS analysis/final handling and chat-template terminator trimming.
- Layer scrubbing and sparse-layer disclosure.
- Jacobian Lens and Logit Lens inspection and controlled overlay.
- User-selected A/B comparison with compatibility guards.
- Verified synthetic demo, same-question Qwen ↔ GPT-OSS demo, Meta Capture demo and Campaign 01 demo.
- Campaign compilation, preview, save, preflight, protocol gates and resumable missing-run execution.
- Session-only Neuronpedia key handling with explicit connection testing.
- Research signature and authorship: **NicoMrx**.

## Explicitly deferred after the contest

- True multi-turn live conversations with preserved conversational context.
- Full execution of the remaining 86 Campaign 01 runs.
- Optional secure key persistence across server restarts.
- Advanced live-chat generation controls in the primary interface.
- Non-blocking visual refinements that do not affect the presentation path.

## Freeze policy

This branch is frozen for contest video production. Changes are limited to:

1. crash fixes;
2. incorrect scientific data presentation;
3. secret exposure or security defects;
4. blockers in the recorded presentation path.

No new feature work is accepted into RC1.
