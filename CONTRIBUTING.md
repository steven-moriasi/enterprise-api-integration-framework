# Contributing

## Development contract

Use Python 3.12 and keep changes focused on integration-boundary behavior.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check app tests scripts
mypy app tests scripts
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

## Provider adapter requirements

Every adapter change must include:

1. typed request and response models;
2. explicit authentication behavior;
3. timeout and retry classification;
4. pagination boundaries where applicable;
5. contract tests using a deterministic provider;
6. safe errors that omit credentials and raw provider bodies;
7. bounded metric labels;
8. documentation of provider-specific idempotency semantics.

Do not add live credentials, recorded production payloads, or customer data. Fixtures must use
reserved domains and clearly fictional identifiers.
