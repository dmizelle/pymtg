# Contributing to PyMTG

Thank you for your interest in contributing to PyMTG! This document outlines how to contribute to the project.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://astral.sh/uv/) package manager (required for all commands)
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/devon-shire/pymtg.git
   cd pymtg
   ```

2. Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Install development dependencies:
   ```bash
   uv sync --all-extras
   ```

## Development Workflow

### Running Tests

All test commands must use `uv run` prefix as per AGENTS.md requirements:

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=pymtg

# Run specific test file
uv run pytest tests/test_providers/test_scryfall.py

# Run tests with verbose output
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

1. **Google-Style Docstrings**: Every Python file, class, function, and method MUST have a Google-style docstring
2. **Type Annotations**: All public APIs must have PEP 484 type annotations
3. **Line Length**: Maximum 80 characters per line (exceptions: long import statements, URLs, module-level constants)
4. **Indentation**: 4 spaces per level, no tabs
5. **Naming Conventions**:
   - Modules: `lower_with_under`
   - Classes: `CapWords`
   - Functions/Methods: `lower_with_under`
   - Variables: `lower_with_under`
   - Constants: `CAPS_WITH_UNDER`
   - Protected: `_leading_underscore`
   - Private: `__double_leading` (discouraged)

### Command Execution

**ALL commands executed must be prefaced with `uv run`.** This is an absolute requirement with no exceptions.

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes with descriptive messages
4. Ensure all tests pass
5. Ensure code passes type checking and linting
6. Verify all docstrings are present and accurate
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

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
2. PyMTG version
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

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
