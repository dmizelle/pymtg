"""Base authentication handler for MTG API providers.

This module provides the BaseAuthHandler abstract base class that all
authentication handlers inherit from.
"""

from abc import ABC, abstractmethod

import requests

from pymtg.exceptions import AuthenticationError  # noqa: F401

# AuthenticationError is imported so it is available in this module's
# namespace, matching the `Raises:` sections of the abstract method
# docstrings below. Subclasses raise this exception and callers may
# catch it by reference from either pymtg.auth.base or pymtg.exceptions.


class BaseAuthHandler(ABC):
    """Abstract base class for authentication handlers.

    This class defines the interface that all authentication handlers must
    implement. Each provider uses an appropriate authentication handler based
    on its requirements.
    """

    @abstractmethod
    def authenticate(self) -> None:
        """Authenticate with the provider.

        Raises:
            AuthenticationError: If authentication fails.
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if authenticated, False otherwise.
        """
        pass

    @abstractmethod
    def refresh(self) -> None:
        """Refresh authentication.

        Raises:
            AuthenticationError: If refresh fails.
        """
        pass

    @abstractmethod
    def apply_auth(self, session: requests.Session) -> None:
        """Apply authentication to a requests session.

        Args:
            session: The requests.Session to apply authentication to.
        """
        pass

    @abstractmethod
    def clear_auth(self) -> None:
        """Clear authentication credentials."""
        pass
