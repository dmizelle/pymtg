"""OAuth2 authentication handler for providers using OAuth2.

This module provides the OAuth2ClientCredentialsHandler for providers like
TCGPlayer that use OAuth2 client credentials flow.
"""

import logging
import threading
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
        self._lock = threading.RLock()
        self.token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self.access_token: str | None = None
        self.token_type: str | None = None
        self.expires_at: datetime | None = None
        self._authenticated = False

    def __getstate__(self) -> dict[str, Any]:
        """Exclude sensitive data and the non-picklable lock from pickle.

        The internal ``_lock`` (a ``threading.RLock``) cannot be pickled.
        Sensitive credentials (``_client_secret``, ``access_token``) are
        also scrubbed so that serialized state does not leak secrets. The
        deserialized instance will be unauthenticated and must call
        :meth:`authenticate` again before use.

        Returns:
            A copy of the handler's state dict with ``_lock``, secrets,
            and token state removed.
        """
        state = self.__dict__.copy()
        # Exclude sensitive data from pickle.
        state["_client_secret"] = None
        state["access_token"] = None
        state["token_type"] = None
        state["_authenticated"] = False
        # threading.RLock is not picklable; exclude it here and recreate it
        # in __setstate__.
        state["_lock"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state after unpickling, re-creating the internal lock.

        Args:
            state: The serialized state dictionary produced by
                ``__getstate__``.
        """
        for key, value in state.items():
            setattr(self, key, value)
        self._lock = threading.RLock()

    def authenticate(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
    ) -> None:
        """Authenticate with the provider using client credentials.

        All authentication state fields (access_token, token_type,
        expires_at, _authenticated) are updated atomically: token data is
        parsed into local variables first, and only committed to instance
        attributes once every field has been successfully parsed. A parsing
        failure (e.g. an invalid expires_in type) therefore cannot leave
        the handler in a half-authenticated state.

        Args:
            client_id: The OAuth2 client ID (overrides initialization value).
            client_secret: The OAuth2 client secret (overrides initialization
                value).
            scope: The OAuth2 scope (overrides initialization value).

        Raises:
            AuthenticationError: If authentication fails.
            NetworkError: If there is a network error.
        """
        with self._lock:
            self._client_id = client_id or self._client_id
            self._client_secret = client_secret or self._client_secret
            self._scope = scope or self._scope

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
                logger.debug("Requesting OAuth2 token from %s", self.token_url)
                response = requests.post(
                    self.token_url,
                    data=data,
                    auth=auth,
                    headers={"Accept": "application/json"},
                    timeout=30,
                )

                if response.status_code != 200:
                    try:
                        response_data = response.json()
                        error = response_data.get("error", "Unknown error")
                        error_description = response_data.get("error_description", "")
                    except ValueError:
                        error = "Invalid JSON response"
                        error_description = ""
                    raise AuthenticationError(
                        f"OAuth2 token request failed: {error} - {error_description}",
                        auth_type="oauth2",
                        status_code=response.status_code,
                    )

                # Parse token data into locals first so that a parsing failure
                # cannot leave the handler in a half-updated (inconsistent) state.
                # Only once all fields are successfully parsed do we commit them to
                # instance attributes, making the update atomic.
                try:
                    token_data = response.json()
                except ValueError as e:
                    raise AuthenticationError(
                        f"Invalid JSON response from token endpoint: {e}",
                        auth_type="oauth2",
                        status_code=response.status_code,
                    ) from e

                # Validate required fields before updating state
                if not token_data.get("access_token"):
                    raise AuthenticationError(
                        "Missing access_token in token response",
                        auth_type="oauth2",
                    )

                new_access_token = token_data.get("access_token")
                new_token_type = token_data.get("token_type", "Bearer")

                # Calculate expiration time. timedelta() raises TypeError if
                # expires_in is a non-numeric type (e.g. a string); computing it
                # before any state is updated prevents a partial write.
                expires_in = token_data.get("expires_in")
                if expires_in is not None:
                    try:
                        new_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    except (TypeError, ValueError) as e:
                        raise AuthenticationError(
                            f"Invalid expires_in value in token response: "
                            f"{expires_in!r}",
                            auth_type="oauth2",
                            status_code=response.status_code,
                        ) from e
                else:
                    # When the token endpoint omits expires_in, default to a
                    # conservative 1-hour expiry rather than treating the token
                    # as never-expiring. This prevents a token that has been
                    # revoked server-side from being used indefinitely until an
                    # API call returns a 401.
                    new_expires_at = datetime.now() + timedelta(hours=1)

                # Commit all related state fields atomically.
                self.access_token = new_access_token
                self.token_type = new_token_type
                self.expires_at = new_expires_at
                self._authenticated = True
                logger.info("OAuth2 authentication successful")

            except AuthenticationError:
                # Clear stale token state on any authentication failure
                # so callers do not continue using a revoked token.
                self.access_token = None
                self.token_type = None
                self.expires_at = None
                self._authenticated = False
                raise
            except requests.exceptions.RequestException as e:
                logger.error("Network error during OAuth2 authentication: %s", e)
                self.access_token = None
                self.token_type = None
                self.expires_at = None
                self._authenticated = False
                raise NetworkError(
                    "Network error during OAuth2 authentication",
                    original_exception=e,
                ) from e

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if access token is present and not expired, False otherwise.
        """
        with self._lock:
            if not self._authenticated or not self.access_token:
                return False

            # Check if token is expired (with a safety buffer to avoid
            # 401s from clock skew or in-flight requests).
            if self.expires_at and datetime.now() >= self.expires_at - timedelta(
                seconds=60
            ):
                return False

            return True

    def refresh(self) -> None:
        """Refresh authentication.

        Re-authenticates using the stored credentials.

        Raises:
            AuthenticationError: If refresh fails or no credentials stored.
        """
        with self._lock:
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
        with self._lock:
            if self.access_token and self.token_type and self.is_authenticated():
                session.headers.update(
                    {"Authorization": f"{self.token_type} {self.access_token}"}
                )
            else:
                logger.warning(
                    "apply_auth() called with no valid token; "
                    "Authorization header not set"
                )
                # Remove any previously-applied Authorization header so a
                # reused session does not carry a stale/invalid token after
                # auth is cleared or a refresh fails.
                session.headers.pop("Authorization", None)

    def clear_auth(self) -> None:
        """Clear authentication credentials."""
        with self._lock:
            self.access_token = None
            self.token_type = None
            self.expires_at = None
            self._authenticated = False
