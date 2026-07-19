# Build Week acceptance tests

## Historical boundary

- [ ] Active branch is `build-week-2026`.
- [ ] `main` still points to the historical baseline commit.
- [ ] tag `lab-v0.2.1-pre-build-week` still points to that commit.
- [ ] Git history clearly separates pre-existing and Build Week work.

## Context coverage

- [ ] Old v0.2 artifacts still validate and load.
- [ ] New artifacts may contain validated `coverage`.
- [ ] Unknown pre-truncation counts remain `null`.
- [ ] UI never displays “no truncation” when the backend did not report it.
- [ ] Source, transmitted, and instrumented counts are separate.
- [ ] Requested and captured layers are separate.
- [ ] Partial and unknown coverage produce visible warnings.
- [ ] Conversation-message truncation can be represented by exact indices.

## Deterministic Understand

- [ ] No LLM/API/network call exists in the narrative path.
- [ ] The same artifact input produces byte-identical structured output.
- [ ] Every sentence exposes `rule_id`, `template_id`, and evidence.
- [ ] French and English are supported.
- [ ] Unsupported locale falls back explicitly.
- [ ] The UI never labels consciousness, thought, bias, censorship, or causality
      automatically.
- [ ] “Why?” displays the exact measurements behind the sentence.

## Comparison

- [ ] Actual layer numbers are preserved.
- [ ] Prompt tokens are aligned by position and token ID.
- [ ] Generated ordinal alignment is labeled as a limitation.
- [ ] Strict difference distinguishes top-k/probability changes from top-1.
- [ ] Missing cells are reported rather than skipped silently.
- [ ] A fixture that diverges at layer 40 reports no earlier divergence.
- [ ] Identical surface output can coexist with a measured internal divergence.

## UI and i18n

- [ ] Submission path opens in English by default.
- [ ] French switch works without reloading raw data.
- [ ] Context coverage appears before interpretive narrative.
- [ ] Existing raw download and visualizer remain available.
- [ ] Keyboard focus and labels are usable.
- [ ] `web/` and packaged web assets do not drift.

## Demo

- [ ] Works without API key, network, or GPU.
- [ ] Contains no private conversations or personal metadata.
- [ ] Clearly labeled synthetic or public demo.
- [ ] Manifest SHA-256 validates.
- [ ] Judge can reach the core demo in three actions or fewer after launch.

## Documentation

- [ ] README distinguishes existing work from Build Week work.
- [ ] README explains Codex and GPT-5.6 collaboration accurately.
- [ ] README includes setup, supported platforms, sample data, and test path.
- [ ] `PROVENANCE.md` remains honest and visible.
- [ ] `BUILD_WEEK_LOG.md` records sessions and commits.
- [ ] No “100% created with GPT-5.6” claim.
