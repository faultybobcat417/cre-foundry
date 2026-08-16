.PHONY: demo test check clean

demo:
	PYTHONPATH=src python -m cre_foundry demo

test:
	PYTHONPATH=src python -m pytest

check:
	python -m compileall -q src tests
	PYTHONPATH=src python -m pytest

clean:
	rm -rf outputs .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
