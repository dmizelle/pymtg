"""OAuth2 authentication handler for providers using OAuth2.

This module provides the OAuth2ClientCredentialsHandler for providers like
TCGPlayer that use OAuth2 client credentials flow.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from pymtg.auth.base import BaseAuthHandler
from pymtg.exceptions import AuthenticationError, NetworkError

logger = logging.getLogger(__name__)


class OAuth2ClientCredentialsHandler(BaseAuthHandler):
    """Authentication handler for providers using OAuth2 client credentials flow.

    This handler manages OAuth2 client credentials authentication for
    providers that require client_id and client_secret.

    Attributes:
        token_url: The URL to request access tokens from.
        client_id: The OAuth2 client ID.
        client_secret: The OAuth2 client secret.
        access_token: The current access token.
        token_type: The type of the access token (usually "Bearer").
        expires_at: When the access token expires.
        scope: The scope of the access token.
        authenticated: Whether authentication is valid.
    """

    def __init__(
        self,
        token_url: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
    ) -> None:
        """Initialize the OAuth2ClientCredentialsHandler.

        Args:
            token_url: The URL to request access tokens from.
            client_id: The OAuth2 client ID.
            client_secret: The OAuth2 client secret.
            scope: The scope of the access token.
        """
        self.token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self.access_token: str | None = None
        self.token_type: str | None = None
        self.expires_at: datetime | None = None
        self._authenticated = False

    def authenticate(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Authenticate with the provider using client credentials.

        Args:
            client_id: The OAuth2 client ID (overrides initialization value).
            client_secret: The OAuth2 client secret (overrides initialization value).
            **kwargs: Additional authentication parameters.

        Raises:
            AuthenticationError: If authentication fails.
            NetworkError: If there is a network error.
        """
        self._client_id = client_id or self._client_id
        self._client_secret = client_secret or self._client_secret
        self._scope = kwargs.get("scope", self._scope)

        if not self._client_id or not self._client_secret:
            raise AuthenticationError(
                "Client ID and client secret are required for OAuth2 authentication",
                auth_type="oauth2",
            )

        try:
            # Prepare token request
            data = {
                "grant_type": "client_credentials",
            }
            if self._scope:
                data["scope"] = self._scope

            auth = (self._client_id, self._client_secret)

            # Request token
            logger.debug(f"Requesting OAuth2 token from {self.token_url}")
            response = requests.post(
                self.token_url,
                data=data,
                auth=auth,
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error = response.json().get("error", "Unknown error")
                error_description = response.json().get("error_description", "")
                raise AuthenticationError(
                    f"OAuth2 token request failed: {error} - {error_description}",
                    auth_type="oauth2",
                    status_code=response.status_code,
                )

            # Parse and store token
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            self.token_type = token_data.get("token_type", "Bearer")

            # Calculate expiration time
            expires_in = token_data.get("expires_in")
            if expires_in:
                self.expires_at = datetime.now() + timedelta(seconds=expires_in)
            else:
                self.expires_at = None

            self._authenticated = True
            logger.info("OAuth2 authentication successful")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during OAuth2 authentication: {e}")
            raise NetworkError(
                "Network error during OAuth2 authentication",
                original_exception=e,
            ) from e

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if access token is present and not expired, False otherwise.
        """
        if not self._authenticated or not self.access_token:
            return False

        # Check if token is expired
        if self.expires_at and datetime.now() >= self.expires_at:
            return False

        return True

    def refresh(self) -> None:
        """Refresh authentication.

        Re-authenticates using the stored credentials.

        Raises:
            AuthenticationError: If refresh fails or no credentials stored.
        """
        if not self._client_id or not self._client_secret:
            raise AuthenticationError(
                "Cannot refresh authentication: no client credentials stored",
                auth_type="oauth2",
            )
        self.authenticate()

    def apply_auth(self, session: requests.Session) -> None:
        """Apply authentication to a requests session.

        Args:
            session: The requests.Session to apply authentication to.
        """
        if self.access_token and self.token_type:
            session.headers.update(
                {"Authorization": f"{self.token_type} {self.access_token}"}
            )

    def clear_auth(self) -> None:
        """Clear authentication credentials."""
        self.access_token = None
        self.token_type = None
        self.expires_at = None
        self._authenticated = False
