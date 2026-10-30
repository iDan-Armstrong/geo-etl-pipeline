.PHONY: install lint test demo data clean

install:
	pip install -e ".[dev]"

lint:
	ruff check .

test:
	pytest --cov=geoetl --cov-report=term-missing

data:
	python examples/make_example_data.py

demo:
	geoetl run examples/facilities_pipeline.yml --qa-report out/qa_report.md
	@echo "--- QA report ---"
	@cat out/qa_report.md

clean:
	rm -rf out dist .pytest_cache .ruff_cache
