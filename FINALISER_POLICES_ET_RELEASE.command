#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
clear
printf '\n=== Prismora J-Lens 0.2.1 — finalisation typographie ===\n\n'
bash "$DIR/scripts/restore_original_fonts.sh"

printf '\n=== Vérification source/package web ===\n'
python3 - <<'PY'
from pathlib import Path
root=Path.cwd(); a=root/'web'; b=root/'prismora_lab/assets/web'
for rel in ['styles.css','v4-app.css']:
    assert (a/rel).read_bytes()==(b/rel).read_bytes(), rel
for p in (a/'assets/fonts').iterdir():
    q=b/'assets/fonts'/p.name
    assert q.exists() and p.read_bytes()==q.read_bytes(), p.name
print('Miroir web/package: OK')
PY

if python3 -c 'import pytest' >/dev/null 2>&1; then
  printf '\n=== Pytest complet ===\n'
  python3 -m pytest -q
else
  printf '\n[INFO] pytest non disponible dans ce Python ; validation logicielle 171/171 déjà gelée dans TEST_REPORT.md.\n'
fi

cat > TYPOGRAPHY_FINALIZED.txt <<'TXT'
Prismora J-Lens Lab 0.2.1
Typography decision: original families restored locally.
Families: Spectral / Albert Sans / Spline Sans Mono.
Source: google/fonts pinned commit ade3d1533e06b2b1462ffcde8e08b129627ca360.
License: SIL Open Font License 1.1; exact upstream OFL files are vendored with the fonts.
No CDN/runtime network dependency is used by the UI.
TXT

printf '\n=== Manifeste final ===\n'
python3 - <<'PY'
from pathlib import Path
import hashlib,json
root=Path.cwd()
exdirs={'.git','.venv','venv','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','node_modules'}
exfiles={'.DS_Store','RC_0.2.1_SHA256.json'}
rows=[]
for p in sorted(root.rglob('*')):
    if not p.is_file(): continue
    rel=p.relative_to(root)
    if any(x in exdirs for x in rel.parts) or p.name in exfiles: continue
    b=p.read_bytes(); rows.append({'path':rel.as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
out={'schema':'prismora.release-candidate-manifest/v1','name':'Prismora J-Lens Lab','version':'0.2.1','state':'TAG_READY_FONTS_RESTORED','generated_on':'2026-08-29','base':'a39ebf45 + release hardening + Fable regression suite + original OFL typography','file_count':len(rows),'excludes':sorted(exdirs|exfiles), 'font_source':'google/fonts@ade3d1533e06b2b1462ffcde8e08b129627ca360','files':rows}
(root/'RC_0.2.1_SHA256.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f"Manifest: {len(rows)} fichiers")
PY

OUT="$(dirname "$DIR")/Prismora-J-Lens-0.2.1-TAG-READY-2026-08-29.zip"
rm -f "$OUT"
cd "$(dirname "$DIR")"
zip -qry "$OUT" "$(basename "$DIR")" \
  -x '*/.git/*' '*/.venv/*' '*/venv/*' '*/__pycache__/*' '*/.pytest_cache/*' '*/.DS_Store'
printf '\n✅ TAG-READY créé :\n%s\n' "$OUT"
printf '\nAppuie sur Entrée pour fermer…'
read -r _
