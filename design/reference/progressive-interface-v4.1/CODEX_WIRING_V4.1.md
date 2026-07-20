# CODEX TASK — Wire Prismora Interface v4.1 to the existing engine

## Repository workflow

Start from the latest published implementation branch that currently backs draft PR #2:

`codex/implementer-l-interface-progressive-prismora`

The attached/reference branch must also contain these authoritative files:

- `prismora-interface-v4.1-autonome.html`
- `PRISMORA_UI_V4_STATE_MACHINE.md`
- `PRISMORA_TYPOGRAPHY.md`

Create a new Codex implementation branch. The final pull-request base must be:

`ux/progressive-interface`

This task supersedes the visual implementation currently shown in draft PR #2. Do not merge PR #2. Do not run `/feedback` yet.

## Non-negotiable product rule

**The interface evolves according to what it has to say.**

Do not redesign, simplify or reinterpret the supplied v4.1 interface.

The v4.1 HTML is the production visual source of truth. Its synthetic JavaScript data is only a preview fixture and must be replaced with real Prismora artifacts.

## State machine to preserve exactly

### Empty state

- large Prismora mark occupies the centre;
- calm Reader shell;
- Chat, Conversations, Import, Models and Settings available;
- no J-Lens chart or fake result;
- settings dialog may be suggested but never blocks entry;
- visible path: continue without key using demo or imports.

### Request pending

- user message appears;
- model and measurement status are visible;
- the mark begins to yield space;
- never draw layers, tokens or probabilities before real data exists.

### Measured response

- mark becomes smaller and moves to the side;
- response tokens become clickable;
- measured J-Lens panel appears;
- top bar reveals useful status/theme/language controls;
- top-8 and trajectory use real cells only;
- non-measured layers remain explicit gaps.

The same artifact must feed Read, Explore and Control. Switching depth must never rerun the analysis or clear selection state.

## Phase 1 — Adopt the exact v4.1 shell

Replace the current production Reader markup and styles with the supplied v4.1 structure.

Preserve:

- exact visual hierarchy;
- mark movement between empty and measured states;
- progressive top-bar behaviour;
- sidebar menus per level;
- non-blocking settings dialog;
- permanent Neuronpedia import entry;
- light/dark/system themes;
- EN/FR;
- Spectral / Albert Sans / Spline Sans Mono roles.

For production, vendor WOFF2 files and OFL licences locally. No Google Fonts or CDN dependency may remain.

Keep `web/` and `prismora_lab/assets/web/` synchronized.

## Phase 2 — Wire existing real artifact flows

Connect the v4.1 UI to the existing Prismora engine without changing scientific semantics.

Supported initial sources:

1. verified Build Week demo;
2. archived run artifacts;
3. compatible Neuronpedia export folders/files.

Use the existing artifact schema and helpers where correct.

Wire:

- real prompt/request;
- real generated output;
- real generated tokens;
- selected token;
- actual captured layers;
- selected measured layer;
- actual top-8 candidate tokens and probabilities;
- selected-candidate probability trajectory;
- deterministic Understand output and evidence;
- model/backend/run provenance;
- links from Read to the full Explorer evidence.

Never copy the prototype’s synthetic `DEMO` object into production.

Never interpolate missing layers.

When a value is absent, render a localized explicit empty state.

## Phase 3 — Permanent Neuronpedia import

Import must be accessible in every level and must work without an API key.

Reuse and improve the existing local probe-folder reader/import pipeline.

The import dialog must accept:

- one export file;
- multiple related files;
- a decompressed export folder.

After successful parsing:

- create or wrap a real Prismora artifact;
- display it immediately in Read;
- make it available to Explore and Control;
- clearly label whether it is archived or only loaded locally;
- never upload local files anywhere unless the user explicitly starts a remote action.

Add tests with representative fixture exports.

## Phase 4 — Session settings and secrets

Add an in-memory local-server session settings service.

Suggested routes:

- `GET /api/session/settings`
- `PUT /api/session/settings`
- `POST /api/session/neuronpedia/test`
- `DELETE /api/session/neuronpedia-key`

Public response fields may include:

- display name;
- locale;
- theme preference;
- optional worker URL;
- Neuronpedia connected/not connected;
- available backend/model metadata.

Secret rules:

- never return the API key to the browser after submission;
- never store the API key in `localStorage`;
- never write it to logs, artifacts, exports or error traces;
- keep it in process memory only for this version;
- clear it when the server stops or the user disconnects.

The user may always continue without a key.

## Phase 5 — Live Qwen path

Add a real instrumented conversation action using an actually available Neuronpedia Qwen model.

Do not invent model availability.

The model selector must be driven by:

- `/api/models`;
- `/api/backends`;
- tested session connection state;
- actual backend capabilities.

A submitted message must:

1. create a real request;
2. execute through the selected real backend;
3. create/store a real RunArtifact;
4. return the artifact to Read;
5. progressively render response, tokens and measured layers;
6. remain available in Conversations, Explore and Control.

Errors must be localized and must not erase the previous valid artifact.

For the video path, support loading a previously saved real Qwen artifact so the demonstration does not depend on network reliability during recording.

## Existing functionality that must remain reachable

- deterministic Understand and Why?/Pourquoi ? evidence;
- verified demo manifest;
- Human Visualizer;
- A/B comparison;
- runs and Run Inspector;
- baselines;
- causal/intervention tools;
- Claim Ledger;
- exact raw downloads;
- model registry;
- GPU/API fleet;
- experiments, campaigns and preregistration;
- old deep links such as `#visualizer`.

Do not create fake panels.

## Tests

Retain all existing tests and add coverage for:

- exact source/packaged asset synchronization;
- no CDN dependency;
- empty → pending → measured state transitions;
- mark and top-bar state classes;
- settings dialog never blocks demo/import;
- API key never appears in GET responses, logs or persisted browser storage;
- import without API key;
- one imported artifact shared across Read/Explore/Control;
- verified demo real top-8 and trajectory;
- selected token/layer preserved across theme, locale and level changes;
- live backend errors preserve prior artifact;
- old deep-link compatibility;
- EN/FR paired strings;
- no invented/interpolated layers.

Run:

- `python -m pytest`
- `python -m compileall prismora_lab prismora_worker`
- `node --check web/app.js`
- demo manifest verification
- real CLI/Uvicorn smoke test

## Commit plan

1. `ui: adopt Prismora v4.1 progressive shell`
2. `feat: wire Reader to real artifacts and imports`
3. `feat: add session-only Neuronpedia connection settings`
4. `feat: execute and archive live instrumented conversations`
5. `test: cover progressive interface engine wiring`

Stop after each stable milestone if visual or scientific behaviour diverges from the v4.1 contract.

Do not merge and do not run `/feedback`.

At completion report:

- branch and commit SHAs;
- final tests;
- API routes added;
- exact source of model availability;
- proof that secrets are not persisted;
- exact macOS pull/test/serve commands;
- visual acceptance checklist for empty, measured, import and live-Qwen flows.
