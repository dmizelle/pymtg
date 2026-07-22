"""JWT authentication handler for providers using JWT tokens.

This module provides the JWTAuthHandler for providers like Archidekt
that use JWT token-based authentication.
"""

import json
import logging
import threading
from typing import Any

import requests

from pymtg.auth.base import BaseAuthHandler
from pymtg.exceptions import AuthenticationError, NetworkError

logger = logging.getLogger(__name__)


class JWTAuthHandler(BaseAuthHandler):
    """Authentication handler for providers using JWT tokens.

    This handler manages JWT token authentication for providers that require
    username/password login and maintain session state via JWT tokens in the
    Authorization header.

    For Archidekt, this uses the /api/rest-auth/login/ endpoint to obtain
    JWT tokens which are then included in the Authorization header as
    "JWT <token>".

    Attributes:
        base_url: The base URL for the authentication endpoint.
        login_endpoint: The endpoint to POST credentials to.
        refresh_endpoint: The endpoint to POST refresh tokens to.
        access_token: The current JWT access token.
        refresh_token: The current JWT refresh token.
        authenticated: Whether authentication is valid.
        auth_header_name: The header name for the JWT token (default: "Authorization").
        auth_header_prefix: The prefix for the JWT token (default: "JWT").
        provider: The provider name reported in raised exceptions.
    """

    def __init__(
        self,
        base_url: str,
        login_endpoint: str = "/api/rest-auth/login/",
        refresh_endpoint: str = "/api/rest-auth/token/refresh/",
        auth_header_name: str = "Authorization",
        auth_header_prefix: str = "JWT",
        provider: str | None = None,
    ) -> None:
        """Initialize the JWTAuthHandler.

        Args:
            base_url: The base URL for the authentication endpoint.
            login_endpoint: The endpoint to POST credentials to.
                Defaults to "/api/rest-auth/login/".
            refresh_endpoint: The endpoint to POST refresh tokens to.
                Defaults to "/api/rest-auth/token/refresh/".
            auth_header_name: The header name for the JWT token.
                Defaults to "Authorization".
            auth_header_prefix: The prefix for the JWT token.
                Defaults to "JWT".
            provider: The provider name to report in raised
                :class:`~pymtg.exceptions.AuthenticationError` and
                :class:`~pymtg.exceptions.NetworkError` exceptions. Defaults
                to ``None`` so the handler is generic; callers using a
                named backend (e.g. "archidekt") should pass it explicitly.
        """
        self.base_url = base_url.rstrip("/")
        self.login_endpoint = login_endpoint
        self.refresh_endpoint = refresh_endpoint
        self.auth_header_name = auth_header_name
        self.auth_header_prefix = auth_header_prefix
        self.provider = provider

        # Thread-safety: guard all mutable auth state.
        self._lock = threading.RLock()

        # Token storage
        self._access_token: str | None = None
        self._refresh_token: str | None = None

        # User ID storage (extracted from login response)
        self._user_id: str | None = None

        # Authentication state
        self._authenticated = False

        # Credential storage (temporary, cleared after auth)
        self._username: str | None = None
        self._password: str | None = None

    def authenticate(self, *, username: str, password: str) -> None:
        """Authenticate with the provider using username and password.

        Sends a POST request to the login endpoint with username and password
        in JSON format. On success, stores the JWT access and refresh tokens.

        Args:
            username: The username for authentication.
            password: The password for authentication.

        Raises:
            AuthenticationError: If authentication fails (wrong credentials,
                server error, etc.).
            NetworkError: If there is a network error.
        """
        with self._lock:
            # Initialize credentials to None to ensure cleanup on any failure
            self._username = None
            self._password = None
            self._access_token = None
            self._refresh_token = None
            self._authenticated = False

            auth_session = requests.Session()
            tokens_received = False
            try:
                # Prepare login URL and data. Credentials are kept in local
                # scope only during the network call to minimize the window
                # in which they are exposed on the instance; they are not
                # stored on self between requests.
                login_url = f"{self.base_url}{self.login_endpoint}"
                login_data = {
                    "username": username,
                    "password": password,
                }

                logger.debug("Authenticating with %s", login_url)

                # POST credentials as JSON
                response = auth_session.post(
                    login_url,
                    json=login_data,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_msg = f"Login failed: {response.status_code}"
                    # Only surface structured error fields parsed from the
                    # JSON body. The raw response text is server-controlled
                    # and unvalidated; embedding it directly into the
                    # exception message could leak internal diagnostics or
                    # reflected user input into logs, so it is deliberately
                    # excluded.
                    if response.text:
                        try:
                            error_data = response.json()
                            if isinstance(error_data, dict):
                                detail = error_data.get(
                                    "detail", error_data.get("error", "")
                                )
                                if detail:
                                    error_msg += f" - {detail}"
                        except (json.JSONDecodeError, ValueError):
                            # Non-JSON body: do not embed the raw text.
                            pass
                    raise AuthenticationError(
                        error_msg,
                        auth_type="jwt",
                        provider=self.provider,
                        status_code=response.status_code,
                    )

                # Parse response JSON
                try:
                    auth_data = response.json()
                    if not isinstance(auth_data, dict):
                        raise AuthenticationError(
                            "Invalid authentication response format",
                            auth_type="jwt",
                            provider=self.provider,
                            status_code=response.status_code,
                        )
                except (json.JSONDecodeError, ValueError) as e:
                    raise AuthenticationError(
                        f"Failed to parse authentication response: {e}",
                        auth_type="jwt",
                        provider=self.provider,
                        status_code=response.status_code,
                    ) from e

                # Extract tokens - try both 'token' and 'access_token' fields
                # Archidekt returns both 'token' and 'access_token' in resp.
                self._access_token = auth_data.get("access_token") or auth_data.get(
                    "token"
                )
                self._refresh_token = auth_data.get("refresh_token")

                # Validate access token is a non-empty string
                if (
                    not self._access_token
                    or not isinstance(self._access_token, str)
                    or not self._access_token.strip()
                ):
                    raise AuthenticationError(
                        "No valid access token in authentication response",
                        auth_type="jwt",
                        provider=self.provider,
                        status_code=response.status_code,
                        details={"response_keys": list(auth_data.keys())},
                    )

                # Extract and store user_id for API calls that need it
                user_data = auth_data.get("user", {})
                if isinstance(user_data, dict):
                    raw_id = user_data.get("id")
                    self._user_id = str(raw_id) if raw_id is not None else None
                else:
                    self._user_id = None

                self._authenticated = True
                tokens_received = True

                # Credentials were only ever held in local scope; ensure
                # the instance attributes remain cleared after successful
                # auth.
                self._username = None
                self._password = None

                logger.info("JWT authentication successful")

            except requests.exceptions.RequestException as e:
                logger.error("Network error during JWT authentication: %s", e)
                raise NetworkError(
                    "Network error during authentication",
                    original_exception=e,
                    provider=self.provider,
                ) from e
            finally:
                auth_session.close()
                if not tokens_received:
                    # Reset authenticated flag and clean up credentials on
                    # failure.
                    self._authenticated = False
                    self._username = None
                    self._password = None
                    self._access_token = None
                    self._refresh_token = None

    @property
    def user_id(self) -> str | None:
        """Get the authenticated user's ID.

        Returns:
            The user ID as a string, or None if not authenticated or not
            available.
        """
        with self._lock:
            return self._user_id

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if access token is present, False otherwise.
        """
        with self._lock:
            return self._authenticated and self._access_token is not None

    def refresh(
        self, *, username: str | None = None, password: str | None = None
    ) -> None:
        """Refresh authentication using the stored refresh token.

        POSTs the refresh token to the token-refresh endpoint to obtain a
        new access token. If the server supports token rotation (enabled
        via ``ROTATE_REFRESH_TOKENS`` in SimpleJWT), a new refresh token is
        also stored.

        If no refresh token is available, falls back to full
        re-authentication using the provided username and password.

        Args:
            username: Optional username for re-authentication fallback.
                Required if no refresh token is stored.
            password: Optional password for re-authentication fallback.
                Required if no refresh token is stored.

        Raises:
            AuthenticationError: If the refresh request fails, the refresh
                token is invalid/expired, or no refresh mechanism is
                available.
            NetworkError: If a network error occurs during the refresh
                request.
        """
        with self._lock:
            if self._refresh_token:
                self._refresh_with_token(self._refresh_token)
                logger.info("JWT token refreshed successfully")
                return

            # No refresh token — fall back to full re-authentication
            if username and password:
                self.authenticate(username=username, password=password)
                return

            raise AuthenticationError(
                "Cannot refresh authentication: no refresh token stored and "
                "no credentials provided. Call authenticate(username=..., "
                "password=...) first.",
                auth_type="jwt",
                provider=self.provider,
            )

    def _refresh_with_token(self, refresh_token: str) -> None:
        """Exchange a refresh token for a new access token.

        POSTs to the token-refresh endpoint and updates stored tokens.
        Handles both default (access-only) and rotation (access+refresh)
        response formats.

        On any failure (non-200 status, unparseable body, or missing access
        token in the response), all stored tokens are cleared and
        ``_authenticated`` is set to ``False``. Because the JWT handler does
        not retain username/password after a successful
        :meth:`authenticate`, a failed token refresh leaves the handler
        fully unauthenticated with no automatic fallback — the caller must
        re-authenticate manually via :meth:`authenticate` (or via
        :meth:`refresh` with explicit ``username``/``password`` arguments,
        which routes to :meth:`authenticate` once ``_refresh_token`` is
        ``None``).

        Args:
            refresh_token: The JWT refresh token to exchange.

        Raises:
            AuthenticationError: If the refresh endpoint rejects the token
                or returns an unexpected response.
            NetworkError: If a network error occurs.
        """
        with self._lock:
            refresh_url = f"{self.base_url}{self.refresh_endpoint}"
            logger.debug("Refreshing JWT token at %s", refresh_url)

            session = requests.Session()
            try:
                response = session.post(
                    refresh_url,
                    json={"refresh": refresh_token},
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_msg = "Token refresh failed"
                    # Only surface structured error fields parsed from the
                    # JSON body; the raw response text is not embedded to
                    # avoid leaking server-controlled diagnostics into logs.
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            detail = error_data.get(
                                "detail", error_data.get("error", "")
                            )
                            if detail:
                                error_msg += f": {detail}"
                    except (json.JSONDecodeError, ValueError):
                        # Non-JSON body: do not embed the raw text.
                        pass
                    # Clear stale tokens on refresh failure
                    self._access_token = None
                    self._refresh_token = None
                    self._user_id = None
                    self._authenticated = False
                    raise AuthenticationError(
                        error_msg,
                        auth_type="jwt",
                        provider=self.provider,
                        status_code=response.status_code,
                    )

                try:
                    token_data = response.json()
                except (json.JSONDecodeError, ValueError) as e:
                    self._access_token = None
                    self._refresh_token = None
                    self._user_id = None
                    self._authenticated = False
                    raise AuthenticationError(
                        f"Failed to parse refresh response: {e}",
                        auth_type="jwt",
                        provider=self.provider,
                        status_code=response.status_code,
                    ) from e

                # SimpleJWT returns "access" (not "access_token").
                # With rotation enabled, also returns a new "refresh".
                new_access = token_data.get("access")
                new_refresh = token_data.get("refresh")

                if not new_access or not isinstance(new_access, str):
                    # Clear stale tokens consistently with the other failure
                    # paths in this method so the handler is left fully
                    # unauthenticated rather than holding a stale access
                    # token.
                    self._access_token = None
                    self._refresh_token = None
                    self._user_id = None
                    self._authenticated = False
                    raise AuthenticationError(
                        "Refresh response did not contain a valid access " "token",
                        auth_type="jwt",
                        provider=self.provider,
                        status_code=response.status_code,
                        details={"response_keys": list(token_data.keys())},
                    )

                self._access_token = new_access
                if new_refresh and isinstance(new_refresh, str):
                    self._refresh_token = new_refresh
                self._authenticated = True

            except requests.exceptions.RequestException as e:
                logger.error("Network error during JWT refresh: %s", e)
                # Clear stale tokens on refresh failure, consistent with
                # the HTTP-error path, so is_authenticated() no longer
                # reports True with an expired access token after a network
                # failure.
                self._access_token = None
                self._refresh_token = None
                self._user_id = None
                self._authenticated = False
                raise NetworkError(
                    "Network error during token refresh",
                    original_exception=e,
                    provider=self.provider,
                ) from e
            finally:
                session.close()

    def apply_auth(self, session: requests.Session) -> None:
        """Apply authentication to a requests session.

        Adds the Authorization header with the JWT token to the session.

        Args:
            session: The requests.Session to apply authentication to.
        """
        with self._lock:
            if not self._access_token:
                logger.warning(
                    "apply_auth() called on a JWTAuthHandler with no access "
                    "token; no Authorization header will be set. Call "
                    "authenticate(username=..., password=...) first."
                )
                # Remove any previously-applied Authorization header so a
                # reused session does not carry a stale/invalid token after
                # auth is cleared or a refresh fails.
                session.headers.pop(self.auth_header_name, None)
                return
            auth_value = f"{self.auth_header_prefix} {self._access_token}"
            session.headers.update({self.auth_header_name: auth_value})

    def clear_auth(self) -> None:
        """Clear authentication credentials.

        Clears all tokens and credentials from memory.
        """
        with self._lock:
            self._access_token = None
            self._refresh_token = None
            self._username = None
            self._password = None
            self._user_id = None
            self._authenticated = False

    @property
    def access_token(self) -> str | None:
        """Get the access token.

        Returns:
            The JWT access token if available, None otherwise.
        """
        with self._lock:
            return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Get the refresh token.

        Returns:
            The JWT refresh token if available, None otherwise.
        """
        with self._lock:
            return self._refresh_token

    def get_auth_header(self) -> dict[str, str]:
        """Get the authentication header for manual request construction.

        Returns:
            A dictionary with the authorization header if authenticated,
            or an empty dictionary if not authenticated.
        """
        with self._lock:
            if self._access_token:
                return {
                    self.auth_header_name: (
                        f"{self.auth_header_prefix} {self._access_token}"
                    )
                }
            return {}

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickle serialization to exclude sensitive data.

        Returns:
            Dictionary of attributes to pickle, excluding sensitive data
            and the threading lock.
        """
        state = self.__dict__.copy()
        # Exclude sensitive data from pickle. The deserialized instance will
        # be unauthenticated and must call authenticate() again before use.
        state["_access_token"] = None
        state["_refresh_token"] = None
        state["_username"] = None
        state["_password"] = None
        state["_user_id"] = None
        state["_authenticated"] = False
        state["_lock"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state after deserialization, recreating the lock.

        Args:
            state: The pickled state dictionary produced by __getstate__.
        """
        for key, value in state.items():
            setattr(self, key, value)
        self._lock = threading.RLock()
