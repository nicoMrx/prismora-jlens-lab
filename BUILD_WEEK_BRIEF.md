# Prismora J-Lens Lab — Build Week brief

## Project identity

**Entrant:** NicoMrx  
**Track:** Developer Tools  
**Repository:** `nicoMrx/prismora-jlens-lab`  
**Historical baseline:** tag `lab-v0.2.1-pre-build-week`  
**Build branch:** `build-week-2026`

## One-sentence demo

> Same apparent output does not mean the same internal trajectory.

## Existing before Build Week

The following already existed and must not be presented as Build Week work:

- ExperimentSpec v2 and RunArtifact v2;
- mock, Neuronpedia, and private GPU-worker contracts;
- immutable exact raw storage and SHA-256 provenance;
- campaign planning and preregistration locking;
- Run Inspector, Baseline Lab, Causal Lab, Comparison Studio, Claim Ledger;
- strict public/private bridge checks;
- A/B Human Visualizer v0.2.1.

See `BUILD_WEEK_BOUNDARY.md`, `PROVENANCE.md`, and
`PRE_BUILD_WEEK_EVIDENCE.md`.

## Build Week product slice

Build a human-verifiable layer on top of the existing laboratory:

1. **Deterministic Understand**
   - Narrative produced only by explicit rules.
   - Every sentence includes a rule ID and links to source measurements.
   - No LLM-generated explanatory text.
   - French and English templates.

2. **Context coverage**
   - Show what source material existed.
   - Show what was transmitted to the model.
   - Show what was instrumented.
   - Show truncation or unknown coverage explicitly.
   - Show requested and captured layers.
   - Never infer missing values.

3. **Submission demo**
   - Curated, non-sensitive sample artifacts.
   - A stable local path for judges.
   - Clear installation and test instructions.
   - A short flow demonstrating an observable internal divergence.

## Product principles

- Raw bytes are never rewritten.
- A derived explanation cannot alter evidence.
- Unknown values remain `null`/unknown, never guessed.
- A measured divergence is not automatically called cognition, bias, censorship,
  consciousness, or causality.
- A duplicate result is not independent evidence.
- Same surface output is not proof of the same internal path.
- Coverage of model context and coverage of instrumentation are distinct.
- Build Week changes must remain visible in Git history.

## Scope cuts

If time becomes limited, cut in this order:

1. re-importing external analyses;
2. complete Research Handoff ZIP;
3. secondary narrative rules;
4. full-app localization outside the submission path.

Do **not** cut:

- deterministic rule traceability;
- context coverage;
- EN/FR on the submission path;
- demo data;
- tests and pre-existing-work disclosure.
