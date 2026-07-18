# Campaign catalog — v0.2.0

All scientific examples remain **draft** until reviewed and locked. Every real
campaign asks for positive, mixed and null results to be retained.

| File | Backend | Runs | Purpose |
|---|---|---:|---|
| `strategy_quadratic_01.json` | Neuronpedia | 54 | Readability and verbalization of algebraic strategy under plain, method-forbidden and lexical-decoy prompts. |
| `filter_nonword_bootstrap.json` | Neuronpedia | 1 + generated replay | Capture one token sequence, then create an exact `inputTokenIds` A/B replay changing only `filterNonWordTokens`. |
| `early_layer_background_01.json` | Neuronpedia | 36 | Build model/lens-specific prompt-insensitive early-layer reference distributions over unrelated tasks. |
| `formal_language_boundary_01.json` | Neuronpedia | 48 | Compare naked equations/chemistry with English, French and Japanese natural-language wrappers. |
| `meta_capture_01.json` | Neuronpedia | 30 | Measure whether observation clauses displace task-family read-outs after controlling prompt copying and clause placement. |
| `world_competition_01.json` | Neuronpedia | 9 | Track competing semantic worlds in ambiguous versus disambiguated prompts. |
| `causal_strategy_worker_template.json` | GPU worker | 12 | **Template only:** task-level strategy swap; placeholders and missing controls forbid immediate scientific use. |
| `strategy_quadratic_mock.json` | Mock | 3 | Software smoke test only. |

## Recommended order

1. Run the mock campaign and export a bundle.
2. Run one Neuronpedia source observation and verify its raw SHA-256.
3. Generate and execute the exact filter replay.
4. Build the early-layer reference distribution.
5. Run the observation-only strategy campaign.
6. Validate a pinned local worker against an exact public token replay.
7. Only then edit and preregister the causal worker template.

## API limits encoded in the examples

Neuronpedia examples use top-k 8 and no more than 256 generated tokens. The
GPU worker schema permits larger values, but each runtime must advertise and
enforce its own capabilities.
