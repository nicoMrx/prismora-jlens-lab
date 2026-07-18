# Pre-Build-Week evidence record

This file records the evidence available before the `build-week-2026` development branch is created. It is a provenance record, not a claim that filesystem timestamps alone prove authorship or originality.

## Artifact timeline observed on Julie's Mac

The following Finder creation dates are visible in screenshots captured on 18 July 2026:

| Artifact | Finder creation date shown |
|---|---:|
| `prismora-jlens-lab-v0.2.0.zip` | 14 July 2026, 21:36 |
| `SHA256SUMS-prismora-v0.2.0.txt` | 14 July 2026, 21:37 |
| `prismora-jlens-lab-v0.2.0-release.zip` | 15 July 2026, 06:33 |
| `strategy-quadratic-mock-…zip` | 15 July 2026, 08:12 |
| `Lanceur_Prismora_Mac.zip` | 15 July 2026, 08:30 |
| `Probe_Fable_Prismora_corrige.zip` | 15 July 2026, 09:13 |
| `Suite_Probe_Fable_sans_T0.zip` | 15 July 2026, 09:43 |
| `probe_20260715T074434Z.zip` | 15 July 2026, 09:49 |
| `Campagne_Fable_…_Causale_v0.1.zip` | 15 July 2026, 10:19 |
| `Prismora_Visualiseur_Humain_v0.2.1.zip` | 15 July 2026, 15:57 |

Finder creation dates establish when these copies appeared on that filesystem. They are useful corroborating evidence, but they can be altered by copying, restoring, timezone conversion, or filesystem behavior. They must therefore be combined with content hashes, archive manifests, dated chat exports, and—once created—Git commits.

## Cryptographic identity of the laboratory release

The uploaded release wrapper contains the original checksum file. The inner source archive and wheel match it exactly:

```text
aab4d2da57ad187f1f8d5c729c4032360b8d0193fd0048c7a86b367a502a874e  prismora-jlens-lab-v0.2.0.zip
5e6d5ba86e1caa4ac59158bfbf4dbba8564980ac55199d63c01b842fdf3cdb0c  prismora_jlens_lab-0.2.0-py3-none-any.whl
```

The outer release ZIP inspected for this record has SHA-256:

```text
2e5aad6ece283993c44ef7f35291d6382f9dcb813807b877cd5ccd86798c524f
```

Its archive entries are timestamped between 14 July 2026 21:32 and 21:37 in the ZIP metadata. ZIP timestamps are timezone-naive and are not treated as sole proof of chronology.

## Cryptographic identity of the visualizer patch

The uploaded visualizer package has SHA-256:

```text
3ec7d6b97e66bcaebe74f3c25973d265b2b757517c349f94d3b76b3ec4add3e3
```

It contains `MANIFEST_SHA256.json`, which records hashes for the interface patch, the probe importer, and the Mac installer/launcher files.

## Build Week boundary

The baseline represented by this directory is:

```text
Prismora J-Lens Lab v0.2.0
+ Human Visualizer patch v0.2.1
```

Features already present before the Build Week branch include the protocol engine, Neuronpedia adapter, mock and GPU-worker contracts, immutable raw storage, Run Inspector, Comparison Studio, claim ledger, and the A/B Human Visualizer.

The Build Week contribution must be documented as additions on top of this baseline. Proposed additions include deterministic Understand narratives, English/French localization, context-coverage reporting, and curated demonstration data.
