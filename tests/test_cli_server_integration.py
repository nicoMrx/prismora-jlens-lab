import os
import socket
import subprocess
import sys
import time

import httpx


def test_cli_serve_exposes_understand_compare_route(tmp_path):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    environment = {**os.environ, 'PRISMORA_DATA_DIR': str(tmp_path / 'data')}
    proc = subprocess.Popen(
        [sys.executable, '-m', 'prismora_lab.cli', 'serve', '--host', '127.0.0.1', '--port', str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=environment,
    )
    client = httpx.Client(trust_env=False)
    try:
        base = f'http://127.0.0.1:{port}'
        last_error = None
        for _ in range(40):
            try:
                response = client.get(base + '/openapi.json', timeout=1.0)
                if response.status_code == 200:
                    break
            except Exception as exc:  # server startup race
                last_error = exc
            time.sleep(0.25)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            output = proc.stdout.read() if proc.stdout else ''
            raise AssertionError(f'CLI server did not start: {last_error}; output={output}')
        assert '/api/understand/compare' in response.text
        route = client.post(base + '/api/understand/compare', json={}, timeout=2.0)
        assert route.status_code != 404
        assert route.status_code == 400
        demo = client.post(base + '/api/demo/build-week/understand/compare', json={
            'run_a': 'demo-pair-a-control', 'run_b': 'demo-pair-a-shift',
            'lens': 'JACOBIAN_LENS', 'scope': 'all', 'locale': 'en', 'probability_abs_tolerance': 0,
        }, timeout=2.0)
        assert demo.status_code == 200
        rules = {sentence['rule_id'] for sentence in demo.json()['sentences']}
        assert 'compare.scope.generated_ordinal' in rules
        assert 'compare.intervention.member' in rules
    finally:
        client.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
