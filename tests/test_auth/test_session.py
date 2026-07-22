"""Tests for the session authentication handler module.

This module tests the SessionAuthHandler, focusing on resource management
of the auth_session (requests.Session) created during authentication.
Specifically, it verifies that the session is properly closed on error
paths and kept open on success.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from pymtg.auth.session import SessionAuthHandler
from pymtg.exceptions import AuthenticationError, NetworkError


class TestSessionAuthHandlerInit:
    """Tests for SessionAuthHandler initialization."""

    def test_init_with_defaults(self):
        """Test that SessionAuthHandler initializes with default values."""
        handler = SessionAuthHandler(base_url="https://example.com")
        assert handler.base_url == "https://example.com"
        assert handler.login_endpoint == "/accounts/login/"
        assert handler.csrf_header == "X-CSRFToken"
        assert handler.csrf_cookie == "csrftoken"
        assert handler.session_cookies == {}
        assert handler._session is None
        assert handler._authenticated is False

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base_url."""
        handler = SessionAuthHandler(base_url="https://example.com/")
        assert handler.base_url == "https://example.com"

    def test_init_with_custom_values(self):
        """Test that SessionAuthHandler accepts custom configuration."""
        handler = SessionAuthHandler(
            base_url="https://example.com",
            login_endpoint="/custom/login/",
            csrf_header="X-Custom-CSRF",
            csrf_cookie="custom_csrf",
        )
        assert handler.login_endpoint == "/custom/login/"
        assert handler.csrf_header == "X-Custom-CSRF"
        assert handler.csrf_cookie == "custom_csrf"


class TestSessionAuthHandlerAuthenticateSuccess:
    """Tests for successful authentication."""

    @patch("pymtg.auth.session.requests.Session")
    def test_authenticate_success_stores_session(self, mock_session_cls):
        """Test that successful authentication stores the session.

        Verifies that on success, the auth_session is stored in
        self._session and not closed.
        """
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # Mock CSRF GET response
        mock_csrf_response = MagicMock()
        mock_csrf_response.status_code = 200
        mock_csrf_response.cookies.get.return_value = "csrf-token-123"
        mock_session.get.return_value = mock_csrf_response

        # Mock login POST response
        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_session.post.return_value = mock_login_response

        # Mock session cookies
        mock_cookie = MagicMock()
        mock_cookie.name = "sessionid"
        mock_cookie.value = "session-value"
        mock_session.cookies = [mock_cookie]

        handler = SessionAuthHandler(base_url="https://example.com")
        handler.authenticate(username="user", password="pass")

        assert handler._authenticated is True
        assert handler._session is mock_session
        assert "sessionid" in handler.session_cookies
        # Session should NOT be closed on success
        mock_session.close.assert_not_called()

    @patch("pymtg.auth.session.requests.Session")
    def test_authenticate_success_sets_cookies(self, mock_session_cls):
        """Test that successful authentication extracts session cookies."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_csrf_response = MagicMock()
        mock_csrf_response.status_code = 200
        mock_csrf_response.cookies.get.return_value = "csrf-token-123"
        mock_session.get.return_value = mock_csrf_response

        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_session.post.return_value = mock_login_response

        mock_csrf_cookie = MagicMock()
        mock_csrf_cookie.name = "csrftoken"
        mock_csrf_cookie.value = "csrf-token-123"
        mock_session_cookie = MagicMock()
        mock_session_cookie.name = "sessionid"
        mock_session_cookie.value = "session-value"
        mock_session.cookies = [mock_csrf_cookie, mock_session_cookie]

        handler = SessionAuthHandler(base_url="https://example.com")
        handler.authenticate(username="user", password="pass")

        assert handler.session_cookies["csrftoken"] == "csrf-token-123"
        assert handler.session_cookies["sessionid"] == "session-value"


class TestSessionAuthHandlerAuthenticateErrorPaths:
    """Tests that auth_session is closed on error paths."""

    @patch("pymtg.auth.session.requests.Session")
    def test_authenticate_csrf_failure_closes_session(self, mock_session_cls):
        """Test that session is closed when CSRF token retrieval fails.

        Verifies that auth_session.close() is called when the CSRF GET
        returns a non-200 status code.
        """
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_csrf_response = MagicMock()
        mock_csrf_response.status_code = 500
        mock_session.get.return_value = mock_csrf_response

        handler = SessionAuthHandler(base_url="https://example.com")
        with pytest.raises(AuthenticationError):
            handler.authenticate(username="user", password="pass")

        # Session must be closed on error
        mock_session.close.assert_called_once()
        assert handler._authenticated is False
        assert handler._session is None

    @patch("pymtg.auth.session.requests.Session")
    def test_authenticate_csrf_token_missing_closes_session(self, mock_session_cls):
        """Test that session is closed when CSRF token is not in cookies.

        Verifies that auth_session.close() is called when the CSRF cookie
        is not found in the response.
        """
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_csrf_response = MagicMock()
        mock_csrf_response.status_code = 200
        mock_csrf_response.cookies.get.return_value = None
        mock_session.get.return_value = mock_csrf_response

        handler = SessionAuthHandler(base_url="https://example.com")
        with pytest.raises(AuthenticationError):
            handler.authenticate(username="user", password="pass")

        mock_session.close.assert_called_once()
        assert handler._authenticated is False

    @patch("pymtg.auth.session.requests.Session")
    def test_authenticate_login_failure_closes_session(self, mock_session_cls):
        """Test that session is closed when login POST fails.

        Verifies that auth_session.close() is called when the login POST
        returns a non-200 status code.
        """
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_csrf_response = MagicMock()
        mock_csrf_response.status_code = 200
        mock_csrf_response.cookies.get.return_value = "csrf-token-123"
        mock_session.get.return_value = mock_csrf_response

        mock_login_response = MagicMock()
        mock_login_response.status_code = 403
        mock_session.post.return_value = mock_login_response

        handler = SessionAuthHandler(base_url="https://example.com")
        with pytest.raises(AuthenticationError):
            handler.authenticate(username="user", password="pass")

        mock_session.close.assert_called_once()
        assert handler._authenticated is False

    @patch("pymtg.auth.session.requests.Session")
    def test_authenticate_network_error_closes_session(self, mock_session_cls):
        """Test that session is closed on network error.

        Verifies that auth_session.close() is called when a
        RequestException occurs during authentication.
        """
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_session.get.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        handler = SessionAuthHandler(base_url="https://example.com")
        with pytest.raises(NetworkError):
            handler.authenticate(username="user", password="pass")

        mock_session.close.assert_called_once()
        assert handler._authenticated is False


class TestSessionAuthHandlerIsAuthenticated:
    """Tests for is_authenticated method."""

    def test_is_authenticated_false_initially(self):
        """Test that handler is not authenticated initially."""
        handler = SessionAuthHandler(base_url="https://example.com")
        assert handler.is_authenticated() is False

    def test_is_authenticated_true_with_cookies(self):
        """Test that handler is authenticated with cookies and flag set."""
        handler = SessionAuthHandler(base_url="https://example.com")
        handler._authenticated = True
        handler.session_cookies = {"sessionid": "value"}
        handler._session = MagicMock()
        assert handler.is_authenticated() is True

    def test_is_authenticated_false_without_session(self):
        """Test that handler is not authenticated when no session is stored.

        ``is_authenticated()`` guards on ``_session is not None`` so that a
        handler whose session was closed externally (or via ``clear_auth``)
        is not reported as authenticated.
        """
        handler = SessionAuthHandler(base_url="https://example.com")
        handler._authenticated = True
        handler.session_cookies = {"sessionid": "value"}
        handler._session = None
        assert handler.is_authenticated() is False

    def test_is_authenticated_false_without_cookies(self):
        """Test that handler is not authenticated without cookies."""
        handler = SessionAuthHandler(base_url="https://example.com")
        handler._authenticated = True
        assert handler.is_authenticated() is False


class TestSessionAuthHandlerClearAuth:
    """Tests for clear_auth method."""

    def test_clear_auth_closes_session(self):
        """Test that clear_auth closes and clears the stored session."""
        handler = SessionAuthHandler(base_url="https://example.com")
        mock_session = MagicMock()
        handler._session = mock_session
        handler._authenticated = True
        handler.session_cookies = {"sessionid": "value"}
        handler._username = "user"
        handler._password = "pass"

        handler.clear_auth()

        mock_session.close.assert_called_once()
        assert handler._session is None
        assert handler._authenticated is False
        assert handler.session_cookies == {}
        assert handler._username is None
        assert handler._password is None

    def test_clear_auth_without_session(self):
        """Test that clear_auth works when no session exists."""
        handler = SessionAuthHandler(base_url="https://example.com")
        handler.clear_auth()
        assert handler._session is None
        assert handler._authenticated is False


class TestSessionAuthHandlerRefresh:
    """Tests for refresh method."""

    def test_refresh_without_credentials_raises(self):
        """Test that refresh raises when no credentials are stored."""
        handler = SessionAuthHandler(base_url="https://example.com")
        with pytest.raises(AuthenticationError):
            handler.refresh()

    @patch("pymtg.auth.session.requests.Session")
    def test_refresh_with_credentials_reauthenticates(self, mock_session_cls):
        """Test that refresh re-authenticates with stored credentials."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_csrf_response = MagicMock()
        mock_csrf_response.status_code = 200
        mock_csrf_response.cookies.get.return_value = "csrf-token-123"
        mock_session.get.return_value = mock_csrf_response

        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_session.post.return_value = mock_login_response

        mock_cookie = MagicMock()
        mock_cookie.name = "sessionid"
        mock_cookie.value = "session-value"
        mock_session.cookies = [mock_cookie]

        handler = SessionAuthHandler(base_url="https://example.com")
        handler._username = "user"
        handler._password = "pass"

        handler.refresh()

        assert handler._authenticated is True
        assert handler._session is mock_session
        # Credentials are retained after successful auth so refresh() can
        # be called again later. Use clear_auth() for explicit cleanup.
        # NOTE: This confirms plaintext credential retention on the handler
        # instance; see the security note in SessionAuthHandler's docstring.
        assert handler._username == "user"
        assert handler._password == "pass"

    @patch("pymtg.auth.session.requests.Session")
    def test_refresh_failure_closes_session(self, mock_session_cls):
        """Test that a failed refresh closes the session and resets state.

        When refresh() delegates to authenticate() and authentication fails
        (e.g. CSRF retrieval returns a non-200 status), the in-flight session
        must be closed and ``_authenticated`` reset so the handler is left in
        a clean, unauthenticated state.
        """
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_csrf_response = MagicMock()
        mock_csrf_response.status_code = 500
        mock_session.get.return_value = mock_csrf_response

        handler = SessionAuthHandler(base_url="https://example.com")
        handler._username = "user"
        handler._password = "pass"

        with pytest.raises(AuthenticationError):
            handler.refresh()

        mock_session.close.assert_called_once()
        assert handler._authenticated is False
        assert handler._session is None


class TestSessionAuthHandlerProperties:
    """Tests for csrf_token and sessionid properties."""

    def test_csrf_token_property(self):
        """Test that csrf_token property returns the CSRF token."""
        handler = SessionAuthHandler(base_url="https://example.com")
        handler.session_cookies = {"csrftoken": "token123"}
        assert handler.csrf_token == "token123"

    def test_csrf_token_property_missing(self):
        """Test that csrf_token property returns None when not present."""
        handler = SessionAuthHandler(base_url="https://example.com")
        assert handler.csrf_token is None

    def test_sessionid_property(self):
        """Test that sessionid property returns the session ID."""
        handler = SessionAuthHandler(base_url="https://example.com")
        handler.session_cookies = {"sessionid": "session123"}
        assert handler.sessionid == "session123"

    def test_sessionid_property_missing(self):
        """Test that sessionid property returns None when not present."""
        handler = SessionAuthHandler(base_url="https://example.com")
        assert handler.sessionid is None


class TestSessionAuthHandlerApplyAuth:
    """Tests for apply_auth method."""

    def test_apply_auth_sets_cookies(self):
        """Test that apply_auth sets cookies on a session."""
        handler = SessionAuthHandler(base_url="https://example.com")
        handler.session_cookies = {
            "sessionid": "session-value",
            "csrftoken": "csrf-value",
        }
        session = MagicMock()
        handler.apply_auth(session)

        assert session.cookies.set.call_count == 2
        # Verify each cookie name maps to its correct value to catch swap
        # bugs that the call_count check alone would miss.
        session.cookies.set.assert_any_call("sessionid", "session-value")
        session.cookies.set.assert_any_call("csrftoken", "csrf-value")
        session.headers.update.assert_called_once_with({"X-CSRFToken": "csrf-value"})

    def test_apply_auth_without_cookies(self):
        """Test that apply_auth does nothing without cookies."""
        handler = SessionAuthHandler(base_url="https://example.com")
        session = MagicMock()
        handler.apply_auth(session)

        session.cookies.set.assert_not_called()
        session.headers.update.assert_not_called()

    def test_apply_auth_skips_none_values(self):
        """Test that apply_auth skips cookies with None values."""
        handler = SessionAuthHandler(base_url="https://example.com")
        handler.session_cookies = {"sessionid": None}
        session = MagicMock()
        handler.apply_auth(session)

        session.cookies.set.assert_not_called()
