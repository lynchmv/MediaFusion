# MediaFusion Tests

This directory contains tests for the MediaFusion application.

## Setup

Install test dependencies:

```bash
uv sync --group dev
# or
pip install -e ".[dev]"
```

## Running Tests

Run all tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=. --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_exceptions.py
```

Run tests matching a pattern:
```bash
pytest -k "test_exception"
```

Run tests with verbose output:
```bash
pytest -v
```

## Test Structure

- `conftest.py`: Shared fixtures and pytest configuration
- `test_exceptions.py`: Tests for custom exception classes
- `test_api_main.py`: Tests for API endpoints
- `test_database_operations.py`: Tests for database operations
- `test_rate_limiting.py`: Tests for rate limiting functionality

## Writing Tests

Follow these guidelines:

1. Use descriptive test names starting with `test_`
2. Group related tests in classes
3. Use fixtures from `conftest.py` for common setup
4. Mark async tests with `@pytest.mark.asyncio`
5. Use mocks for external dependencies (database, Redis, etc.)

## Coverage Goals

- Aim for >80% coverage on critical paths:
  - API endpoints
  - Database operations
  - Exception handling
  - Rate limiting
  - Streaming providers
