"""Session authentication handler for providers using session cookies.

This module provides the SessionAuthHandler for providers like Archidekt
and Moxfield that use session cookie-based authentication.
"""

import logging
from typing import Any

import requests

from pymtg.auth.base import BaseAuthHandler
from pymtg.exceptions import AuthenticationError, NetworkError

logger = logging.getLogger(__name__)


class SessionAuthHandler(BaseAuthHandler):
    """Authentication handler for providers using session cookies.

    This handler manages session cookie authentication for providers that
    require username/password login and maintain session state via cookies.

    Attributes:
        base_url: The base URL for the authentication endpoint.
        login_endpoint: The endpoint to POST credentials to.
        session_cookies: Dictionary of session cookies (name -> value).
        csrf_header: The header name for CSRF token.
        csrf_cookie: The cookie name for CSRF token.
        authenticated: Whether authentication is valid.
    """

    def __init__(
        self,
        base_url: str,
        login_endpoint: str = "/accounts/login/",
        csrf_header: str = "X-CSRFToken",
        csrf_cookie: str = "csrftoken",
    ) -> None:
        """Initialize the SessionAuthHandler.

        Args:
            base_url: The base URL for the authentication endpoint.
            login_endpoint: The endpoint to POST credentials to.
            csrf_header: The header name for CSRF token.
            csrf_cookie: The cookie name for CSRF token.
        """
        self.base_url = base_url.rstrip("/")
        self.login_endpoint = login_endpoint
        self.csrf_header = csrf_header
        self.csrf_cookie = csrf_cookie
        self.session_cookies: dict[str, str | None] = {}
        self._session: requests.Session | None = None
        self._authenticated = False
        self._username: str | None = None
        self._password: str | None = None

    def authenticate(self, *, username: str, password: str, **kwargs: Any) -> None:
        """Authenticate with the provider using username and password.

        Args:
            username: The username for authentication.
            password: The password for authentication.
            **kwargs: Additional authentication parameters.

        Raises:
            AuthenticationError: If authentication fails.
            NetworkError: If there is a network error.
        """
        # Initialize credentials to None to ensure cleanup on any failure
        self._username = None
        self._password = None

        auth_session = requests.Session()
        session_stored = False
        try:
            # Store credentials temporarily
            self._username = username
            self._password = password

            # First, get the login page to retrieve CSRF token
            login_url = f"{self.base_url}{self.login_endpoint}"
            logger.debug(f"Getting CSRF token from {login_url}")
            csrf_response = auth_session.get(login_url)

            if csrf_response.status_code != 200:
                raise AuthenticationError(
                    f"Failed to get CSRF token: {csrf_response.status_code}",
                    auth_type="session",
                )

            # Extract CSRF token from cookies
            csrf_token = csrf_response.cookies.get(self.csrf_cookie)
            if not csrf_token:
                raise AuthenticationError(
                    "CSRF token not found in response cookies",
                    auth_type="session",
                )

            # Prepare login data
            login_data = {
                "username": username,
                "password": password,
            }

            # Add CSRF token to headers
            headers = {
                self.csrf_header: csrf_token,
                "Referer": login_url,
            }

            # POST credentials
            logger.debug(f"Authenticating with {login_url}")
            response = auth_session.post(
                login_url,
                data=login_data,
                headers=headers,
                cookies={self.csrf_cookie: csrf_token},
                allow_redirects=True,
            )

            if response.status_code != 200:
                raise AuthenticationError(
                    f"Login failed: {response.status_code}",
                    auth_type="session",
                )

            # Store session cookies
            self.session_cookies = {
                cookie.name: cookie.value for cookie in auth_session.cookies
            }
            self._session = auth_session
            self._authenticated = True
            session_stored = True

            logger.info(f"Session authentication successful for {username}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during session authentication: {e}")
            raise NetworkError(
                "Network error during authentication",
                original_exception=e,
            ) from e
        finally:
            if not session_stored:
                auth_session.close()
            # Always clean up credentials on failure
            if not self._authenticated:
                self._username = None
                self._password = None

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if session cookies are present, False otherwise.
        """
        return self._authenticated and bool(self.session_cookies)

    def refresh(self) -> None:
        """Refresh authentication.

        Re-authenticates using the stored credentials.

        Raises:
            AuthenticationError: If refresh fails or no credentials stored.
        """
        if not self._username or not self._password:
            raise AuthenticationError(
                "Cannot refresh authentication: no credentials stored",
                auth_type="session",
            )
        self.authenticate(username=self._username, password=self._password)

    def apply_auth(self, session: requests.Session) -> None:
        """Apply authentication to a requests session.

        Args:
            session: The requests.Session to apply authentication to.
        """
        if self.session_cookies:
            for name, value in self.session_cookies.items():
                if value is not None:
                    session.cookies.set(name, value)

        # Also set CSRF token in headers if present
        if self.csrf_cookie in self.session_cookies:
            csrf_token = self.session_cookies[self.csrf_cookie]
            if csrf_token is not None:
                session.headers.update({self.csrf_header: csrf_token})

    def clear_auth(self) -> None:
        """Clear authentication credentials."""
        self.session_cookies.clear()
        self._authenticated = False
        self._username = None
        self._password = None
        if self._session:
            self._session.close()
            self._session = None

    @property
    def csrf_token(self) -> str | None:
        """Get the CSRF token.

        Returns:
            The CSRF token if available, None otherwise.
        """
        return self.session_cookies.get(self.csrf_cookie)

    @property
    def sessionid(self) -> str | None:
        """Get the session ID.

        Returns:
            The session ID if available, None otherwise.
        """
        return self.session_cookies.get("sessionid")
