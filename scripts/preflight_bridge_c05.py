from __future__ import annotations
from pathlib import Path
import re, sys

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else 'BRIDGE_C05_PREREGISTRATION.md')
text = TARGET.read_text(encoding='utf-8')
placeholders = sorted(set(re.findall(r'<(?:commit|x\.y\.z)>', text)))
if placeholders:
    print(f'REFUSE: unresolved preregistration placeholders in {TARGET}: {", ".join(placeholders)}')
    raise SystemExit(2)
print(f'OK: no unresolved commit/version placeholders in {TARGET}')
