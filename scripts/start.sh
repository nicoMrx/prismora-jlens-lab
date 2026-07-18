#!/usr/bin/env sh
set -eu
exec python -m prismora_lab.cli serve "$@"
