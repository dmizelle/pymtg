

# Code Style and Conventions

## Documentation

### Docstrings
- **Google Style Docstrings**: All classes, methods, and functions should use Google style docstrings. Here's an example:

  ```python
  """
  Foobar is a thing that bars foos

  Args:
      name (str): name of the foobar

  Attributes:
      full_name (str): full name of the foobar

  Raises:
      TooOldFoobarError: When the foobar is too old
  """
  class Foobar:
      def __init__(self, name: str):
          self.full_name = name
  ```

### Attributes
- **Attribute Docstrings**: All attributes should have docstrings explaining what they are.

  ```python
  class Foobar:
      def __init__(self, name: str):
          """Initialize a new Foobar instance.

          Args:
              name (str): name of the foobar
          """
          self.full_name: str = name  # full name of the foobar
  ```

## Type Hints
- **Type Hints**: Use type hints wherever possible to improve code readability and maintainability. Prefer `str | None` over `Optional[str]`.

  ```python
  from typing import List

  class Foobar:
      def __init__(self, name: str):
          self.full_name: str = name
          self.age: int | None = None
          self.foos: list[str] = []
  ```

## Serena Memories
- **Update Memories**: Whenever a large enough change is made, update the Serena memories to reflect the changes.

## Example

Here is a complete example:

```python
"""
A class representing a Foobar.

This class is used to manage foos and bars.

Attributes:
    full_name (str): full name of the foobar
    age (int | None): age of the foobar
    foos (list[str]): list of foos

Raises:
    TooOldFoobarError: When the foobar is too old
"""

from typing import List

class TooOldFoobarError(Exception):
    """Exception raised when the foobar is too old."""
    pass

class Foobar:
    """A class representing a Foobar."""

    def __init__(self, name: str):
        """
        Initialize a new Foobar instance.

        Args:
            name (str): name of the foobar
        """
        self.full_name: str = name  # full name of the foobar
        self.age: int | None = None  # age of the foobar
        self.foos: list[str] = []  # list of foos

    def add_foo(self, foo: str) -> None:
        """
        Add a foo to the foobar.

        Args:
            foo (str): foo to add
        """
        self.foos.append(foo)

    def get_foos(self) -> list[str]:
        """
        Get the list of foos.

        Returns:
            list[str]: list of foos
        """
        return self.foos
```

