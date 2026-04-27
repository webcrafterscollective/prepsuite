# Testing

Phase 1 uses Pytest, pytest-asyncio, HTTPX ASGI transport, Ruff, and Mypy.

## Commands

```bash
make lint
make typecheck
make test
make check
```

## Coverage

Bootstrap tests verify:

- Health endpoint behavior.
- Readiness endpoint success and failure behavior.
- Request ID propagation.
- Standard error envelope.
- Settings defaults.
- Async SQLAlchemy engine and session factory construction.

Future phases will add Testcontainers-backed PostgreSQL/Redis integration tests for tenant isolation, RLS, permissions, feature gates, workers, and live flows.
