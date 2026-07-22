"""JWT authentication handler for providers using JWT tokens.

This module provides the JWTAuthHandler for providers like Archidekt
that use JWT token-based authentication.
"""

import json
import logging
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
        access_token: The current JWT access token.
        refresh_token: The current JWT refresh token.
        authenticated: Whether authentication is valid.
        auth_header_name: The header name for the JWT token (default: "Authorization").
        auth_header_prefix: The prefix for the JWT token (default: "JWT").
    """

    def __init__(
        self,
        base_url: str,
        login_endpoint: str = "/api/rest-auth/login/",
        auth_header_name: str = "Authorization",
        auth_header_prefix: str = "JWT",
    ) -> None:
        """Initialize the JWTAuthHandler.

        Args:
            base_url: The base URL for the authentication endpoint.
            login_endpoint: The endpoint to POST credentials to.
                Defaults to "/api/rest-auth/login/".
            auth_header_name: The header name for the JWT token.
                Defaults to "Authorization".
            auth_header_prefix: The prefix for the JWT token.
                Defaults to "JWT".
        """
        self.base_url = base_url.rstrip("/")
        self.login_endpoint = login_endpoint
        self.auth_header_name = auth_header_name
        self.auth_header_prefix = auth_header_prefix

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
        # Initialize credentials to None to ensure cleanup on any failure
        self._username = None
        self._password = None
        self._access_token = None
        self._refresh_token = None
        self._authenticated = False

        auth_session = requests.Session()
        tokens_received = False
        try:
            # Keep credentials in local scope only during the network call to
            # minimize the window in which they are exposed on the instance.
            # They are not stored on self between requests.
            _req_username = username
            _req_password = password

            # Prepare login URL and data
            login_url = f"{self.base_url}{self.login_endpoint}"
            login_data = {
                "username": _req_username,
                "password": _req_password,
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
                if response.text:
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            error_msg += f" - {error_data.get('detail', error_data.get('error', 'Unknown error'))}"
                    except (json.JSONDecodeError, ValueError):
                        # If response is not JSON, include text if it's short
                        if len(response.text) < 200:
                            error_msg += f" - {response.text.strip()}"
                raise AuthenticationError(
                    error_msg,
                    auth_type="jwt",
                    provider="archidekt",
                    status_code=response.status_code,
                )

            # Parse response JSON
            try:
                auth_data = response.json()
                if not isinstance(auth_data, dict):
                    raise AuthenticationError(
                        "Invalid authentication response format",
                        auth_type="jwt",
                        provider="archidekt",
                        status_code=response.status_code,
                    )
            except (json.JSONDecodeError, ValueError) as e:
                raise AuthenticationError(
                    f"Failed to parse authentication response: {e}",
                    auth_type="jwt",
                    provider="archidekt",
                    status_code=response.status_code,
                ) from e

            # Extract tokens - try both 'token' and 'access_token' fields
            # Archidekt returns both 'token' and 'access_token' in the response
            self._access_token = auth_data.get("access_token") or auth_data.get("token")
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
                    provider="archidekt",
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

            # Credentials were only ever held in local scope; ensure the
            # instance attributes remain cleared after successful auth.
            self._username = None
            self._password = None

            logger.info("JWT authentication successful")

        except requests.exceptions.RequestException as e:
            logger.error("Network error during JWT authentication: %s", e)
            raise NetworkError(
                "Network error during authentication",
                original_exception=e,
                provider="archidekt",
            ) from e
        finally:
            auth_session.close()
            if not tokens_received:
                # Reset authenticated flag and clean up credentials on failure
                self._authenticated = False
                self._username = None
                self._password = None
                self._access_token = None
                self._refresh_token = None

    @property
    def user_id(self) -> str | None:
        """Get the authenticated user's ID.

        Returns:
            The user ID as a string, or None if not authenticated or not available.
        """
        return self._user_id

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if access token is present, False otherwise.
        """
        return self._authenticated and self._access_token is not None

    def refresh(
        self, *, username: str | None = None, password: str | None = None
    ) -> None:
        """Refresh authentication.

        Uses the refresh_token to obtain a new access token without requiring
        username/password. Falls back to re-authentication with provided credentials
        if refresh_token is unavailable.

        Note:
            For Archidekt, credentials are cleared from memory after successful
            authentication for security. This means stored credentials are not
            available for refresh. Either:
            - Use refresh_token if the API supports it (not yet implemented for Archidekt)
            - Provide username and password directly to this method

        Args:
            username: Optional username for re-authentication. Required if no
                refresh_token is available.
            password: Optional password for re-authentication. Required if no
                refresh_token is available.

        Raises:
            AuthenticationError: If refresh fails or no valid refresh mechanism available.
        """
        # Try using refresh_token first if available
        if self._refresh_token:
            # Implement token refresh using the refresh_token
            # For now, Archidekt doesn't seem to have a dedicated refresh endpoint
            # so we fall back to re-authentication with provided credentials
            logger.debug(
                "Refresh token available but dedicated refresh endpoint not implemented"
            )
            # Fall through to re-authentication

        # Re-authenticate with provided credentials
        if username and password:
            self.authenticate(username=username, password=password)
        else:
            raise AuthenticationError(
                "Cannot refresh authentication: no refresh token endpoint implemented "
                "for Archidekt and no credentials provided. "
                "Please call authenticate() again with username and password.",
                auth_type="jwt",
                provider="archidekt",
            )

    def apply_auth(self, session: requests.Session) -> None:
        """Apply authentication to a requests session.

        Adds the Authorization header with the JWT token to the session.

        Args:
            session: The requests.Session to apply authentication to.
        """
        if self._access_token:
            auth_value = f"{self.auth_header_prefix} {self._access_token}"
            session.headers.update({self.auth_header_name: auth_value})

    def clear_auth(self) -> None:
        """Clear authentication credentials.

        Clears all tokens and credentials from memory.
        """
        self._access_token = None
        self._refresh_token = None
        self._username = None
        self._password = None
        self._authenticated = False

    @property
    def access_token(self) -> str | None:
        """Get the access token.

        Returns:
            The JWT access token if available, None otherwise.
        """
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Get the refresh token.

        Returns:
            The JWT refresh token if available, None otherwise.
        """
        return self._refresh_token

    def get_auth_header(self) -> dict[str, str]:
        """Get the authentication header for manual request construction.

        Returns:
            A dictionary with the authorization header if authenticated,
            or an empty dictionary if not authenticated.
        """
        if self._access_token:
            return {
                self.auth_header_name: f"{self.auth_header_prefix} {self._access_token}"
            }
        return {}

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickle serialization to exclude sensitive data.

        This ensures that credentials and tokens are not accidentally
        serialized and stored in insecure locations.

        Returns:
            Dictionary of attributes to pickle, excluding sensitive data.
        """
        state = self.__dict__.copy()
        # Exclude sensitive data from pickle. The deserialized instance will
        # be unauthenticated and must call authenticate() again before use.
        state["_access_token"] = None
        state["_refresh_token"] = None
        state["_username"] = None
        state["_password"] = None
        state["_authenticated"] = False
        return state
