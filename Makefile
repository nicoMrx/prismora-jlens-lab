.PHONY: install test serve worker clean

install:
	python -m pip install -e ".[dev]"

test:
	pytest

serve:
	python -m prismora_lab.cli serve

worker:
	python -m prismora_worker.app

clean:
	rm -rf .pytest_cache .prismora-data build dist *.egg-info
