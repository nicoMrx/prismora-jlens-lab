# Curated demo data specification

## Goal

Demonstrate, in under one minute:

> Same apparent output does not mean the same internal trajectory.

## Dataset

Provide four small artifacts grouped into two pairs.

### Pair A — same surface, different path

- same prompt token IDs;
- same generated token IDs and readable completion;
- identical layers before a declared split;
- different top-k/readout probabilities from a declared layer onward;
- explicit demo/synthetic label;
- coverage object.

Expected deterministic Understand facts:

- generated surface is identical;
- first strict divergence is layer N;
- first top-1 divergence may be later or absent;
- context coverage status;
- caution: this observation alone is not causal proof.

### Pair B — different surface, visible path

- same fixed prompt;
- outputs diverge;
- readouts diverge at a known layer;
- one or more missing-cell fixtures may be included separately for warning tests.

## Privacy and licensing

Do not include:

- API keys or environment values;
- Julie's private conversations;
- Grok conversation exports;
- political or medical material;
- file-system paths containing personal names;
- third-party data without permission.

## Manifest

Create a manifest containing:

- relative path;
- bytes;
- SHA-256;
- artifact schema;
- short description;
- synthetic/public origin.

The demo loader must verify the manifest before displaying the data.
