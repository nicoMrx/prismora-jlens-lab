#!/usr/bin/env sh
set -eu
python -m prismora_lab.cli validate experiment examples/strategy_quadratic_mock.json
python -m prismora_lab.cli plan examples/strategy_quadratic_mock.json >/tmp/prismora-plan.json
python -m prismora_lab.cli run examples/strategy_quadratic_mock.json --backend mock --limit 3
python -m pytest
