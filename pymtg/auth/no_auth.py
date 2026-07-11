"""No authentication handler for providers that don't require authentication.

This module provides the NoAuthHandler for providers like Scryfall that
don't require any authentication.
"""

from typing import Any

import requests

from pymtg.auth.base import BaseAuthHandler


class NoAuthHandler(BaseAuthHandler):
    """Authentication handler for providers that don't require authentication.

    This handler is used for providers like Scryfall that have public APIs
    that don't require any authentication.

    Attributes:
        authenticated: Always True for no-auth providers.
    """

    def __init__(self) -> None:
        """Initialize the NoAuthHandler."""
        self._authenticated = True

    def authenticate(self, **kwargs: Any) -> None:
        """Authenticate with the provider.

        For no-auth providers, this is a no-op.

        Args:
            **kwargs: Unused.
        """
        self._authenticated = True

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            Always True for no-auth providers.
        """
        return self._authenticated

    def refresh(self) -> None:
        """Refresh authentication.

        For no-auth providers, this is a no-op.
        """
        self._authenticated = True

    def apply_auth(self, session: requests.Session) -> None:
        """Apply authentication to a requests session.

        For no-auth providers, this is a no-op.

        Args:
            session: The requests.Session to apply authentication to.
        """
        # No authentication needed
        pass

    def clear_auth(self) -> None:
        """Clear authentication credentials.

        For no-auth providers, this is a no-op.
        """
        pass
