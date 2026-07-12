"""API key authentication handler for providers using API keys.

This module provides the APIKeyAuthHandler for providers like Deckbox
that use API key-based authentication.
"""

import threading
from typing import Any

import requests

from pymtg.auth.base import BaseAuthHandler


class APIKeyAuthHandler(BaseAuthHandler):
    """Authentication handler for providers using API keys.

    This handler manages API key authentication for providers that require
    an API key to be included in request headers.

    Attributes:
        api_key: The API key for authentication.
        header_name: The header name to use for the API key.
        header_value: The header value (may include key with prefix).
        authenticated: Whether authentication is valid.
    """

    def __init__(
        self,
        header_name: str = "Authorization",
        header_prefix: str | None = None,
    ) -> None:
        """Initialize the APIKeyAuthHandler.

        Args:
            header_name: The header name to use for the API key.
                Defaults to "Authorization".
            header_prefix: Optional prefix for the API key
                (e.g., "Bearer", "Token").
        """
        self._lock = threading.Lock()

        self.header_name = header_name
        self.header_prefix = header_prefix
        self._api_key: str | None = None
        self._authenticated = False

    def authenticate(self, *, api_key: str, **kwargs: Any) -> None:
        """Authenticate with the provider using an API key.

        Args:
            api_key: The API key for authentication.
            **kwargs: Additional authentication parameters.
        """
        with self._lock:
            self._api_key = api_key
            self._authenticated = api_key is not None and api_key != ""

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if API key is present, False otherwise.
        """
        with self._lock:
            return self._authenticated and self._api_key is not None

    def refresh(self) -> None:
        """Refresh authentication.

        For API key authentication, this is a no-op since API keys don't expire.
        """
        with self._lock:
            # API keys don't expire, so just verify we still have one
            self._authenticated = self._api_key is not None

    def apply_auth(self, session: requests.Session) -> None:
        """Apply authentication to a requests session.

        Args:
            session: The requests.Session to apply authentication to.

        Raises:
            ValueError: If session is None.
        """
        if session is None:
            raise ValueError("Cannot apply API key authentication: session is None")
        with self._lock:
            if self._api_key:
                if self.header_prefix:
                    header_value = f"{self.header_prefix} {self._api_key}"
                else:
                    header_value = self._api_key
        session.headers.update({self.header_name: header_value})

    def clear_auth(self) -> None:
        """Clear authentication credentials."""
        with self._lock:
            self._api_key = None
            self._authenticated = False

    @property
    def api_key(self) -> str | None:
        """Get the API key.

        Returns:
            The API key if present, None otherwise.
        """
        with self._lock:
            return self._api_key

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickle serialization to exclude sensitive data.

        Returns:
            Dictionary of attributes to pickle, excluding _api_key.
        """
        state = self.__dict__.copy()
        state["_api_key"] = None
        return state
