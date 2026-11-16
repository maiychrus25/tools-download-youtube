.PHONY: build test lint

build:
	@python3 -c "import ast; from pathlib import Path; [ast.parse(Path(name).read_text(), filename=name) for name in ('server.py', 'test_server.py')]"
	@node scripts/check-docs.js
	@echo "Build succeeded"

test:
	@PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v

lint:
	@python3 -m tabnanny server.py test_server.py
	@node --check scripts/check-docs.js
	@echo "Lint succeeded (Python indentation and JavaScript syntax)"
