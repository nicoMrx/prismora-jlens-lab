import subprocess
import sys
import time

import httpx


def test_cli_serve_exposes_understand_compare_route(tmp_path):
    port = 8137
    proc = subprocess.Popen(
        [sys.executable, '-m', 'prismora_lab.cli', 'serve', '--host', '127.0.0.1', '--port', str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base = f'http://127.0.0.1:{port}'
        last_error = None
        for _ in range(40):
            try:
                response = httpx.get(base + '/openapi.json', timeout=1.0)
                if response.status_code == 200:
                    break
            except Exception as exc:  # server startup race
                last_error = exc
            time.sleep(0.25)
        else:
            output = proc.stdout.read() if proc.stdout else ''
            raise AssertionError(f'CLI server did not start: {last_error}; output={output}')
        assert '/api/understand/compare' in response.text
        route = httpx.post(base + '/api/understand/compare', json={}, timeout=2.0)
        assert route.status_code != 404
        assert route.status_code == 400
        demo = httpx.post(base + '/api/demo/build-week/understand/compare', json={
            'run_a': 'demo-pair-a-control', 'run_b': 'demo-pair-a-shift',
            'lens': 'JACOBIAN_LENS', 'scope': 'all', 'locale': 'en', 'probability_abs_tolerance': 0,
        }, timeout=2.0)
        assert demo.status_code == 200
        rules = {sentence['rule_id'] for sentence in demo.json()['sentences']}
        assert 'compare.scope.generated_ordinal' in rules
        assert 'compare.intervention.member' in rules
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
