# Agent Instructions for pymtg

## Overview

This document defines **absolute, non-negotiable** requirements for all AI agents, subagents, and automated tools operating within the pymtg codebase. These instructions are **mandatory** and must be followed without exception.

---

## 1. Google-Style Docstring Enforcement (CRITICAL)

### 1.1 Absolute Requirement

**Every Python file, class, function, and method MUST have a Google-style docstring.** This is not optional. Agents **MUST** create, update, and maintain accurate docstrings for every modification they make to the codebase.

### 1.2 Google-Style Docstring Format

All docstrings must conform to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) and follow these patterns:

#### 1.2.1 Module-Level Docstrings

Every `.py` file must start with a module-level docstring immediately after license/boilerplate (if any):

```python
"""One-line summary of the module or program, terminated by a period.

Leave one blank line. The rest of this docstring should contain an overall
description of the module or program. Optionally, it may also contain a brief
description of exported classes and functions and/or usage examples.

Typical usage example:

    foo = ClassFoo()
    bar = foo.function_bar()
"""
```

#### 1.2.2 Class Docstrings

Every class must have a docstring immediately following the class definition:

```python
class SampleClass:
    """Summary of class here.

    Longer class information...
    Longer class information...

    Attributes:
        likes_spam (bool): A boolean indicating if we like SPAM or not.
        eggs (int): An integer count of the eggs we have laid.
    """

    def __init__(self, likes_spam: bool = False):
        ...
```

**Important:** Class docstrings must start with a one-line summary that describes **what the class instance represents**, not "A class that..."

#### 1.2.3 Function and Method Docstrings

Every function and method must have a docstring. The docstring must include:

```python
def fetch_smalltable_rows(
    table_handle: smalltable.Table,
    keys: Sequence[bytes | str],
    require_all_keys: bool = False,
) -> Mapping[bytes, tuple[str, ...]]:
    """Fetches rows from a Smalltable.

    Retrieves rows pertaining to the given keys from the Table instance
    represented by table_handle. String keys will be UTF-8 encoded.

    Args:
        table_handle: An open smalltable.Table instance.
        keys: A sequence of strings representing the key of each table
            row to fetch. String keys will be UTF-8 encoded.
        require_all_keys: If True only rows with values set for all keys will be
            returned.

    Returns:
        A dict mapping keys to the corresponding table row data fetched. Each
        row is represented as a tuple of strings.

    Raises:
        IOError: An error occurred accessing the smalltable.
    """
```

#### 1.2.4 Docstring Sections

Docstrings use these standard sections:

| Section | Purpose | Required |
|---------|---------|----------|
| Summary line | One-line description ending with period | **Yes** |
| Extended description | Additional context | Optional |
| `Args:` | Parameter descriptions | Yes (if function has parameters) |
| `Returns:` | Return value description | Yes (unless returns None) |
| `Yields:` | For generators, describes yielded values | Yes (for generators) |
| `Raises:` | Exceptions that may be raised | Yes (if applicable) |
| `Attributes:` | Public attributes (for classes) | Optional |
| `Note:` | Additional notes | Optional |
| `Examples:` | Usage examples | Optional |

**Section Formatting Rules:**
- Each section begins with a heading line ending with a colon
- Section content uses a hanging indent of 2 or 4 spaces (consistent within file)
- Parameter names in `Args:` are followed by optional type in parentheses, then colon, then description
- Type annotations in function signature **replace** type info in docstring (PEP 484)

#### 1.2.5 Parameter Documentation

```python
Args:
    param1 (int): The first parameter.
    param2 (str, optional): The second parameter. Defaults to None.
    *args: Variable length argument list.
    **kwargs: Arbitrary keyword arguments.
```

**If using PEP 484 type annotations, omit types from docstring:**

```python
def function_with_pep484_type_annotations(param1: int, param2: str) -> bool:
    """Example function with PEP 484 type annotations.

    Args:
        param1: The first parameter.
        param2: The second parameter.

    Returns:
        The return value. True for success, False otherwise.
    """
```

#### 1.2.6 Return Value Documentation

```python
Returns:
    bool: The return value. True for success, False otherwise.

    dict: A mapping of keys to values, where each value is a tuple of strings.

    tuple: A tuple (mat_a, mat_b), where mat_a is the first matrix and
        mat_b is the second matrix.
```

**For None returns:** Omit the `Returns:` section entirely.

#### 1.2.7 Exception Documentation

```python
Raises:
    ValueError: If param1 equals param2.
    IOError: An error occurred accessing the resource.
```

**Important:** Only document exceptions that are relevant to the **interface**. Do NOT document exceptions raised when the API contract is violated.

### 1.3 Docstring Maintenance Requirements

For **every** code change made by an agent:

1. **New code:** Must include Google-style docstrings from creation
2. **Modified code:** Must update all affected docstrings to reflect changes
3. **Deleted code:** Must remove associated docstrings
4. **Parameter changes:** Must update `Args:` section with new/removed parameters
5. **Return type changes:** Must update `Returns:` section
6. **New exceptions:** Must add to `Raises:` section

**Verification:** Before committing any change, agents MUST verify that:
- All new/modified functions have docstrings
- Docstring content matches the actual implementation
- All parameters are documented
- Return types are documented
- Exceptions are documented

### 1.4 Docstring Quality Checklist

Before any code is committed, verify the following for all affected code:

- [ ] Module has a module-level docstring
- [ ] Every class has a class docstring
- [ ] Every function has a function docstring
- [ ] Every method has a method docstring
- [ ] Summary line is one physical line (≤ 80 chars)
- [ ] Summary line ends with a period
- [ ] Sections are properly formatted (heading with colon)
- [ ] Parameters are documented in `Args:` section
- [ ] Return values are documented in `Returns:` or `Yields:` section
- [ ] Exceptions are documented in `Raises:` section
- [ ] Type information in docstring matches type annotations (or omitted if annotations present)
- [ ] Docstring accurately describes the current implementation
- [ ] No outdated information from previous versions

### 1.5 Command Execution Requirements (CRITICAL)

**ALL commands executed by agents MUST be prefaced with `uv run`.** This is an absolute requirement with no exceptions.

#### 1.5.1 uv Requirement

The `uv` package manager and Python tooling wrapper **MUST** be installed and available in the system PATH before any agent can execute commands.

**Agents MUST REFUSE to perform any actions if `uv` is not available.**

Users **MUST** have `uv` installed and accessible before requesting agent operations.

#### 1.5.2 Command Format

**Good examples:**
```bash
uv run python -c "import requests; print(requests.get('https://google.com/'))"
uv run pytest tests/
uv run pyright pymtg/
uv run python my_script.py
```

**Bad examples (MUST NOT be used):**
```bash
python -c "print(2*2)"
pytest tests/
pyright pymtg/
python my_script.py
```

#### 1.5.3 Verification

Before executing any command, agents MUST:
1. Check that `uv` is available by running `which uv` or `command -v uv`
2. Verify the command returns success (exit code 0)
3. **REFUSE** the action if `uv` is not found
4. Inform the user they must install `uv` first

#### 1.5.4 Installation Instructions for Users

If `uv` is not installed, users must install it using:

```bash
# Official installation (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

After installation, ensure `uv` is in your PATH and verify with:
```bash
uv --version
```

#### 1.5.5 Package Management

**Agents MUST NEVER run `pip` or `pip3` under any circumstances.**

ALL package installation, management, and dependency interactions MUST use `uv`.

**Good examples:**
```bash
uv add requests
uv add pytest
uv remove numpy
uv sync
```

**Bad examples (MUST NOT be used):**
```bash
pip install requests
pip3 install requests
python -m pip install requests
```

**Highly discouraged:**
```bash
uv pip install requests
```

Use `uv add` for adding dependencies, not `uv pip`. The `uv pip` command exists
for compatibility but should be avoided in favor of native `uv` commands.

---


## 2. Code Quality Standards

### 2.1 Type Annotations

- **Required:** All public APIs must have type annotations
- **Preferred:** Use PEP 484 type annotations in function signatures
- **Style:** When type annotations are present, omit type information from docstrings
- **Imports:** Group typing imports together, preferably at the top

```python
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
```

### 2.2 Line Length

- **Maximum:** 80 characters per line
- **Exceptions:**
  - Long import statements
  - URLs in comments
  - Module-level string constants without whitespace
- **Continuation:** Use implicit line joining with parentheses, not backslash

### 2.3 Indentation

- **Standard:** 4 spaces per indentation level
- **No tabs:** Never use tabs
- **Hanging indent:** 4-space hanging indent for continuation lines

### 2.4 Naming Conventions

| Type | Convention |
|------|------------|
| Module | `lower_with_under` |
| Class | `CapWords` |
| Function/Method | `lower_with_under` |
| Variable | `lower_with_under` |
| Constant | `CAPS_WITH_UNDER` |
| Protected | `_leading_underscore` |
| Private | `__double_leading` (discouraged) |

---

## 3. Testing Requirements

### 3.1 Test Documentation

All test files and test functions must also have docstrings:

```python
def test_function_behavior():
    """Tests that function behaves correctly under condition X.

    This test verifies that the function returns expected output when given
    specific input. It covers edge case Y and normal case Z.
    """
```

### 3.2 Test Coverage

- New functionality must include comprehensive tests
- Test docstrings must explain what is being tested and why
- Edge cases must be documented in test docstrings

---

## 4. Code Review Process

### 4.1 Pre-Commit Checks

Before any commit, agents MUST:

1. **Lint:** Run `pylint` or equivalent linter
2. **Type check:** Run type checker (pyright)
3. **Docstring verification:** Confirm all docstrings are present and accurate
4. **Test:** Run all relevant tests
5. **Manual review:** Review changes for compliance with this AGENTS.md

### 4.2 Docstring Verification Tools

Agents should use tools to verify docstring compliance:

```bash
# Check for missing docstrings
pylint --disable=all --enable=missing-docstring,empty-docstring your_module.py

# Generate documentation to verify formatting
pydoc -b
```

---

## 5. Enforcement

### 5.1 Non-Negotiable Rules

The following rules are **absolute** and have no exceptions:

1. All Python code must have Google-style docstrings
2. Docstrings must be accurate and up-to-date
3. Changes to code must include changes to docstrings
4. Type annotations are required for public APIs

### 5.2 Violations

Code found without proper docstrings or with outdated docstrings:

1. **Must be fixed immediately** before merging
2. **Must not be committed** to the repository
3. **Must be flagged** in code review

---

## 6. References

- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [Sphinx Napoleon - Google Style Examples](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)

---

## 7. Quick Reference Card

### 7.1 Minimal Function Docstring

```python
def add(a: int, b: int) -> int:
    """Returns the sum of two integers.

    Args:
        a: First integer.
        b: Second integer.

    Returns:
        The sum of a and b.
    """
    return a + b
```

### 7.2 Minimal Class Docstring

```python
class Point:
    """Represents a point in 2D space.

    Attributes:
        x (float): The x-coordinate.
        y (float): The y-coordinate.
    """

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
```

### 7.3 Minimal Module Docstring

```python
"""Provides utilities for geometric calculations.

This module contains classes and functions for working with geometric
shapes and performing common calculations.
"""
```

---

**Remember:** When in doubt, add a docstring. It's better to have a simple docstring than no docstring at all.

## Commit Testing / Validity

Before considering a task as completed, and especially before committing:

- Unit tests MUST be written and MUST be passing successfully.
- Integrations tests MUST be written for changes and MUST be passing successfully.
- `uv run pyright` must complete without warnings or errors.
- `uv run black` must complete without warnings or errors.

*Last updated: 2026-06-27*
