from __future__ import annotations
import subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'preflight_bridge_c05.py'

def test_preflight_refuses_placeholders(tmp_path: Path):
    doc = tmp_path / 'bridge.md'
    doc.write_text('engine=<commit> version=<x.y.z>\n', encoding='utf-8')
    p = subprocess.run([sys.executable, str(SCRIPT), str(doc)], text=True, capture_output=True)
    assert p.returncode == 2
    assert 'REFUSE:' in p.stdout

def test_preflight_accepts_frozen_values(tmp_path: Path):
    doc = tmp_path / 'bridge.md'
    doc.write_text('engine=abc123 version=1.2.3\n', encoding='utf-8')
    p = subprocess.run([sys.executable, str(SCRIPT), str(doc)], text=True, capture_output=True)
    assert p.returncode == 0
    assert 'OK:' in p.stdout
