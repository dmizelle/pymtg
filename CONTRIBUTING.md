# Contributing to pymtg

Thank you for your interest in contributing to pymtg. This document outlines how to contribute to the project.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://astral.sh/uv/) package manager (required for all commands)
- Git

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/dmizelle/pymtg.git
   cd pymtg
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Install development dependencies:

   ```bash
   uv sync --all-extras
   ```

## Development Workflow

### Running Tests

All commands must use the `uv run` prefix, as required by [AGENTS.md](AGENTS.md):

```bash
# Run the full suite
uv run pytest

# Run tests with coverage
uv run pytest --cov=pymtg

# Run a single provider's tests
uv run pytest tests/test_providers/test_scryfall.py

# Run with verbose output
uv run pytest -v
```

### Type Checking

```bash
uv run pyright pymtg/
```

### Linting

```bash
uv run ruff check pymtg/
```

### Docstring Verification

All Python code must have Google-style docstrings. Verify compliance:

```bash
uv run pydoc -b
```

## Code Style Guidelines

### General Requirements

1. Google-style docstrings on every Python file, class, function, and method.
2. PEP 484 type annotations on all public APIs.
3. Maximum 80 characters per line. Exceptions: long import statements, URLs, and module-level constants.
4. 4 spaces per indentation level. No tabs.
5. Naming conventions:
   - Modules: `lower_with_under`
   - Classes: `CapWords`
   - Functions and methods: `lower_with_under`
   - Variables: `lower_with_under`
   - Constants: `CAPS_WITH_UNDER`
   - Protected: `_leading_underscore`
   - Private: `__double_leading` (discouraged)

### Command Execution

All commands executed in this repository must be prefaced with `uv run`. This is an absolute requirement with no exceptions.

## Pull Request Process

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes with descriptive messages.
4. Ensure all tests pass.
5. Ensure code passes type checking and linting.
6. Verify all docstrings are present and accurate.
7. Push to the branch (`git push origin feature/amazing-feature`).
8. Open a pull request.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### PR Title Format

Use conventional commits style. Examples:

- `feat: add Scryfall provider`
- `fix: handle rate limit errors in search`
- `docs: update README with usage examples`

## Reporting Bugs

When reporting bugs, please include:

1. Python version
2. pymtg version
3. Operating system
4. Steps to reproduce
5. Expected behavior
6. Actual behavior
7. Relevant code snippets

## Feature Requests

Feature requests should include:

1. Description of the feature
2. Use case or problem it solves
3. Proposed API (if applicable)
4. Any relevant context

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See [LICENSE](LICENSE) for details.
