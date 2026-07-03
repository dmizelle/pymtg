"""Base authentication handler for MTG API providers.

This module provides the BaseAuthHandler abstract base class that all
authentication handlers inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any

import requests


class BaseAuthHandler(ABC):
    """Abstract base class for authentication handlers.

    This class defines the interface that all authentication handlers must
    implement. Each provider uses an appropriate authentication handler based
    on its requirements.
    """

    @abstractmethod
    def authenticate(self, **kwargs: Any) -> None:
        """Authenticate with the provider.

        Args:
            **kwargs: Authentication parameters.

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
