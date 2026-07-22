"""Tests for the JWT authentication handler.

This module tests pymtg.auth.jwt.JWTAuthHandler, covering all the requirements
specified in the task list including:
- Successful authentication with valid credentials
- Authentication failure with invalid credentials
- Authentication with network error
- is_authenticated() returns True after auth
- is_authenticated() returns False before auth
- clear_auth() removes tokens
- get_auth_header() returns correct format
- get_auth_header() returns empty dict when not authenticated
- __getstate__ excludes credentials
"""

import json
import pickle
from unittest.mock import MagicMock, patch

import pytest
import requests

from pymtg.auth.jwt import JWTAuthHandler
from pymtg.exceptions import AuthenticationError, NetworkError


def _make_mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock requests.Response object.

    Args:
        status_code: HTTP status code to return.
        json_data: Dictionary to return from response.json().
        text: Text to return from response.text.

    Returns:
        A MagicMock configured as a requests.Response.
    """
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("No JSON data provided")
    return response


class TestJWTAuthHandlerInitialization:
    """Tests for JWTAuthHandler initialization."""

    def test_init_default_values(self):
        """Test that JWTAuthHandler initializes with default values."""
        handler = JWTAuthHandler("https://archidekt.com")

        assert handler.base_url == "https://archidekt.com"
        assert handler.login_endpoint == "/api/rest-auth/login/"
        assert handler.refresh_endpoint == "/api/rest-auth/token/refresh/"
        assert handler.auth_header_name == "Authorization"
        assert handler.auth_header_prefix == "JWT"
        assert handler.is_authenticated() is False
        assert handler.access_token is None
        assert handler.refresh_token is None

    def test_init_custom_values(self):
        """Test that JWTAuthHandler accepts custom values."""
        handler = JWTAuthHandler(
            base_url="https://example.com",
            login_endpoint="/custom/login/",
            refresh_endpoint="/custom/refresh/",
            auth_header_name="X-Auth",
            auth_header_prefix="Bearer",
        )

        assert handler.base_url == "https://example.com"
        assert handler.login_endpoint == "/custom/login/"
        assert handler.refresh_endpoint == "/custom/refresh/"
        assert handler.auth_header_name == "X-Auth"
        assert handler.auth_header_prefix == "Bearer"

    def test_init_strips_trailing_slash(self):
        """Test that base_url trailing slash is stripped."""
        handler = JWTAuthHandler("https://example.com/")
        assert handler.base_url == "https://example.com"

    def test_get_auth_header_not_authenticated(self):
        """Test get_auth_header returns empty dict when not authenticated."""
        handler = JWTAuthHandler("https://archidekt.com")
        assert handler.get_auth_header() == {}

    def test_get_auth_header_authenticated(self):
        """Test get_auth_header returns correct format when authenticated."""
        handler = JWTAuthHandler("https://archidekt.com")
        handler._access_token = "test_token_123"
        handler._authenticated = True

        auth_header = handler.get_auth_header()
        assert auth_header == {"Authorization": "JWT test_token_123"}

    def test_get_auth_header_custom_prefix(self):
        """Test get_auth_header uses custom prefix."""
        handler = JWTAuthHandler(
            "https://archidekt.com",
            auth_header_name="X-Token",
            auth_header_prefix="Bearer",
        )
        handler._access_token = "test_token_456"
        handler._authenticated = True

        auth_header = handler.get_auth_header()
        assert auth_header == {"X-Token": "Bearer test_token_456"}


class TestJWTAuthHandlerIsAuthenticated:
    """Tests for is_authenticated() method."""

    def test_is_authenticated_false_before_auth(self):
        """Test is_authenticated() returns False before authentication."""
        handler = JWTAuthHandler("https://archidekt.com")
        assert handler.is_authenticated() is False

    def test_is_authenticated_true_after_auth(self):
        """Test is_authenticated() returns True after successful authentication."""
        handler = JWTAuthHandler("https://archidekt.com")
        handler._access_token = "test_token"
        handler._authenticated = True
        assert handler.is_authenticated() is True

    def test_is_authenticated_false_without_token(self):
        """Test is_authenticated() returns False when _authenticated=True but no token."""
        handler = JWTAuthHandler("https://archidekt.com")
        handler._authenticated = True
        handler._access_token = None
        assert handler.is_authenticated() is False


class TestJWTAuthHandlerClearAuth:
    """Tests for clear_auth() method."""

    def test_clear_auth_clears_all(self):
        """Test clear_auth() removes all tokens and credentials."""
        handler = JWTAuthHandler("https://archidekt.com")

        # Set up authenticated state
        handler._access_token = "access_token_123"
        handler._refresh_token = "refresh_token_456"
        handler._username = "test_user"
        handler._password = "test_pass"
        handler._authenticated = True

        # Clear authentication
        handler.clear_auth()

        # Verify all are cleared
        assert handler._access_token is None
        assert handler._refresh_token is None
        assert handler._username is None
        assert handler._password is None
        assert handler._authenticated is False
        assert handler.is_authenticated() is False

    def test_clear_auth_idempotent(self):
        """Test clear_auth() can be called multiple times safely."""
        handler = JWTAuthHandler("https://archidekt.com")

        # Clear when already cleared
        handler.clear_auth()
        handler.clear_auth()

        # Should not raise any errors
        assert handler.is_authenticated() is False


class TestJWTAuthHandlerApplyAuth:
    """Tests for apply_auth() method."""

    def test_apply_auth_adds_header(self):
        """Test apply_auth adds Authorization header to session."""
        handler = JWTAuthHandler("https://archidekt.com")
        handler._access_token = "test_token_789"

        session = MagicMock()
        handler.apply_auth(session)

        session.headers.update.assert_called_once_with(
            {"Authorization": "JWT test_token_789"}
        )

    def test_apply_auth_no_token(self):
        """Test apply_auth does nothing when no token."""
        handler = JWTAuthHandler("https://archidekt.com")

        session = MagicMock()
        handler.apply_auth(session)

        # Should not modify headers
        session.headers.update.assert_not_called()

    def test_apply_auth_custom_header_name(self):
        """Test apply_auth uses custom header name."""
        handler = JWTAuthHandler(
            "https://archidekt.com",
            auth_header_name="X-Auth-Token",
        )
        handler._access_token = "custom_token"

        session = MagicMock()
        handler.apply_auth(session)

        session.headers.update.assert_called_once_with(
            {"X-Auth-Token": "JWT custom_token"}
        )


class TestJWTAuthHandlerAuthenticate:
    """Tests for authenticate() method."""

    @patch("pymtg.auth.jwt.requests.Session")
    def test_authenticate_success(self, mock_session_class):
        """Test successful authentication with valid credentials."""
        # Setup mock response
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            json_data={
                "access_token": "access_token_123",
                "refresh_token": "refresh_token_456",
                "user": {"id": 123, "username": "test_user"},
                "token": "access_token_123",
            },
        )
        mock_session.post.return_value = mock_response

        # Authenticate
        handler = JWTAuthHandler("https://archidekt.com")
        handler.authenticate(username="test_user", password="test_pass")

        # Verify state
        assert handler.is_authenticated() is True
        assert handler.access_token == "access_token_123"
        assert handler.refresh_token == "refresh_token_456"

        # Verify credentials were cleared
        assert handler._username is None
        assert handler._password is None

        # Verify request was made correctly
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args.kwargs["timeout"] == 30.0

        # Check the JSON data sent
        call_kwargs = call_args.kwargs
        assert call_kwargs["json"] == {
            "username": "test_user",
            "password": "test_pass",
        }

    @patch("pymtg.auth.jwt.requests.Session")
    def test_authenticate_success_with_token_field(self, mock_session_class):
        """Test authentication when response uses 'token' field instead of 'access_token'."""
        # Setup mock response with 'token' field (not 'access_token')
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            json_data={
                "token": "token_from_field",
                "refresh_token": "refresh_token_789",
            },
        )
        mock_session.post.return_value = mock_response

        # Authenticate
        handler = JWTAuthHandler("https://archidekt.com")
        handler.authenticate(username="test_user", password="test_pass")

        # Should fallback to 'token' field
        assert handler.is_authenticated() is True
        assert handler.access_token == "token_from_field"
        assert handler.refresh_token == "refresh_token_789"

    @patch("pymtg.auth.jwt.requests.Session")
    def test_authenticate_failure_401(self, mock_session_class):
        """Test authentication failure with 401 Unauthorized."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=401,
            text="Unauthorized",
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(username="test_user", password="wrong_pass")

        assert exc_info.value.status_code == 401
        assert "Login failed: 401" in str(exc_info.value)
        assert handler.is_authenticated() is False
        assert handler.access_token is None
        assert handler._username is None
        assert handler._password is None

    @patch("pymtg.auth.jwt.requests.Session")
    def test_authenticate_failure_with_json_error(self, mock_session_class):
        """Test authentication failure with JSON error message in response."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=400,
            json_data={"detail": "Invalid credentials"},
            text='{"detail": "Invalid credentials"}',
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(username="test_user", password="wrong_pass")

        assert exc_info.value.status_code == 400
        assert "Invalid credentials" in str(exc_info.value)

    @patch("pymtg.auth.jwt.requests.Session")
    def test_authenticate_failure_no_token_in_response(self, mock_session_class):
        """Test authentication failure when response has no token."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            json_data={"message": "Success", "user_id": 123},
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(username="test_user", password="test_pass")

        assert "No valid access token in authentication response" in str(exc_info.value)

    @patch("pymtg.auth.jwt.requests.Session")
    def test_authenticate_network_error(self, mock_session_class):
        """Test authentication with network error."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.post.side_effect = requests.exceptions.Timeout()

        handler = JWTAuthHandler("https://archidekt.com")

        with pytest.raises(NetworkError) as exc_info:
            handler.authenticate(username="test_user", password="test_pass")

        assert exc_info.value.message == "Network error during authentication"
        assert handler.is_authenticated() is False
        assert handler.access_token is None
        assert handler._username is None
        assert handler._password is None

    @patch("pymtg.auth.jwt.requests.Session")
    def test_authenticate_invalid_json_response(self, mock_session_class):
        """Test authentication with invalid JSON response."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            text="not valid json",
        )
        # Make json() raise an exception
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(username="test_user", password="test_pass")

        assert "Failed to parse authentication response" in str(exc_info.value)
        assert handler._username is None
        assert handler._password is None


class TestJWTAuthHandlerRefresh:
    """Tests for refresh() method."""

    @patch("pymtg.auth.jwt.requests.Session")
    def test_refresh_no_token_no_credentials(self, mock_session_class):
        """Test refresh fails when no refresh token and no credentials."""
        handler = JWTAuthHandler("https://archidekt.com")

        with pytest.raises(AuthenticationError) as exc_info:
            handler.refresh()

        assert "no refresh token stored" in str(exc_info.value)

    @patch("pymtg.auth.jwt.requests.Session")
    def test_refresh_with_token_success(self, mock_session_class):
        """Test refresh succeeds using a stored refresh token."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            json_data={"access": "new_access_token"},
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")
        handler._access_token = "old_access_token"
        handler._refresh_token = "old_refresh_token"
        handler._authenticated = True

        handler.refresh()

        assert handler.is_authenticated() is True
        assert handler.access_token == "new_access_token"
        # Refresh token unchanged when no rotation
        assert handler.refresh_token == "old_refresh_token"

        # Verify the refresh endpoint was called
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/rest-auth/token/refresh/" in call_args.args[0]
        assert call_args.kwargs["json"] == {"refresh": "old_refresh_token"}

    @patch("pymtg.auth.jwt.requests.Session")
    def test_refresh_with_token_rotation(self, mock_session_class):
        """Test refresh handles token rotation (new access + refresh)."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            json_data={
                "access": "new_access_token",
                "refresh": "new_refresh_token",
            },
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")
        handler._access_token = "old_access_token"
        handler._refresh_token = "old_refresh_token"
        handler._authenticated = True

        handler.refresh()

        assert handler.is_authenticated() is True
        assert handler.access_token == "new_access_token"
        # Refresh token should be updated when rotation is on
        assert handler.refresh_token == "new_refresh_token"

    @patch("pymtg.auth.jwt.requests.Session")
    def test_refresh_token_expired(self, mock_session_class):
        """Test refresh fails when the refresh token is expired (401)."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=401,
            json_data={"detail": "Token is invalid or expired"},
            text='{"detail": "Token is invalid or expired"}',
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")
        handler._access_token = "old_access_token"
        handler._refresh_token = "old_refresh_token"
        handler._authenticated = True

        with pytest.raises(AuthenticationError) as exc_info:
            handler.refresh()

        assert "Token refresh failed" in str(exc_info.value)
        assert exc_info.value.status_code == 401
        # Tokens should be cleared on failure
        assert handler.is_authenticated() is False
        assert handler.access_token is None
        assert handler.refresh_token is None

    @patch("pymtg.auth.jwt.requests.Session")
    def test_refresh_network_error(self, mock_session_class):
        """Test refresh with network error raises NetworkError."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.post.side_effect = requests.exceptions.Timeout()

        handler = JWTAuthHandler("https://archidekt.com")
        handler._refresh_token = "old_refresh_token"
        handler._authenticated = True

        with pytest.raises(NetworkError) as exc_info:
            handler.refresh()

        assert "Network error during token refresh" in str(exc_info.value)

    @patch("pymtg.auth.jwt.requests.Session")
    def test_refresh_response_missing_access(self, mock_session_class):
        """Test refresh fails when response has no access token."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            json_data={"unexpected": "field"},
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")
        handler._refresh_token = "old_refresh_token"
        handler._authenticated = True

        with pytest.raises(AuthenticationError) as exc_info:
            handler.refresh()

        assert "did not contain a valid access token" in str(exc_info.value)

    @patch("pymtg.auth.jwt.requests.Session")
    def test_refresh_fallback_to_credentials(self, mock_session_class):
        """Test refresh falls back to re-auth with credentials.

        When no refresh token is stored, refresh() should use the provided
        username/password to do a full re-authentication.
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_response = _make_mock_response(
            status_code=200,
            json_data={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "token": "new_access_token",
            },
        )
        mock_session.post.return_value = mock_response

        handler = JWTAuthHandler("https://archidekt.com")

        # No refresh token stored, provide credentials
        handler.refresh(username="test_user", password="test_pass")

        assert handler.is_authenticated() is True
        assert handler.access_token == "new_access_token"
        assert handler.refresh_token == "new_refresh_token"

        # Verify the login endpoint was called (not the refresh endpoint)
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/rest-auth/login/" in call_args.args[0]
        assert handler._password is None


class TestJWTAuthHandlerSecurity:
    """Tests for security-related functionality."""

    def test_pickle_excludes_credentials(self):
        """Test __getstate__ excludes credentials from pickle."""
        handler = JWTAuthHandler("https://archidekt.com")

        # Set up authenticated state with credentials
        handler._access_token = "secret_access_token"
        handler._refresh_token = "secret_refresh_token"
        handler._username = "secret_username"
        handler._password = "secret_password"
        handler._authenticated = True

        # Get pickle state
        state = handler.__getstate__()

        # Verify sensitive data is excluded
        assert state["_access_token"] is None
        assert state["_refresh_token"] is None
        assert state["_username"] is None
        assert state["_password"] is None
        assert state["_authenticated"] is False

        # Verify other data is preserved
        assert state["base_url"] == "https://archidekt.com"
        assert state["login_endpoint"] == "/api/rest-auth/login/"
        assert state["refresh_endpoint"] == "/api/rest-auth/token/refresh/"

    def test_pickle_roundtrip_removes_secrets(self):
        """Test that pickle and unpickle removes secrets."""
        handler = JWTAuthHandler("https://archidekt.com")

        # Set up authenticated state
        handler._access_token = "secret_token"
        handler._username = "secret_user"
        handler._password = "secret_pass"
        handler._authenticated = True

        # Pickle and unpickle
        pickled = pickle.dumps(handler)
        unpickled_handler = pickle.loads(pickled)

        # Verify secrets are not present
        assert unpickled_handler._access_token is None
        assert unpickled_handler._username is None
        assert unpickled_handler._password is None
        assert unpickled_handler._authenticated is False
        assert unpickled_handler.is_authenticated() is False

    def test_authenticate_clears_password_immediately(self):
        """Test that password is cleared from memory after authentication."""
        mock_session = MagicMock()
        mock_response = _make_mock_response(
            status_code=200,
            json_data={
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "token": "test_token",
            },
        )
        mock_session.post.return_value = mock_response

        with patch("pymtg.auth.jwt.requests.Session", return_value=mock_session):
            handler = JWTAuthHandler("https://archidekt.com")
            handler.authenticate(username="test_user", password="test_pass")

            # Password should be cleared after successful auth
            assert handler._password is None
            assert handler._username is None

    def test_failed_auth_clears_credentials(self):
        """Test that credentials are cleared on authentication failure."""
        mock_session = MagicMock()
        mock_response = _make_mock_response(status_code=401)
        mock_session.post.return_value = mock_response

        with patch("pymtg.auth.jwt.requests.Session", return_value=mock_session):
            handler = JWTAuthHandler("https://archidekt.com")

            try:
                handler.authenticate(username="test_user", password="test_pass")
            except AuthenticationError:
                pass  # Expected

            # Credentials should be cleared on failure
            assert handler._username is None
            assert handler._password is None
            assert handler.is_authenticated() is False


class TestJWTAuthHandlerProperties:
    """Tests for property accessors."""

    def test_access_token_property(self):
        """Test access_token property returns the token."""
        handler = JWTAuthHandler("https://archidekt.com")
        handler._access_token = "test_access_token"

        assert handler.access_token == "test_access_token"

    def test_access_token_property_none(self):
        """Test access_token property returns None when not set."""
        handler = JWTAuthHandler("https://archidekt.com")
        assert handler.access_token is None

    def test_refresh_token_property(self):
        """Test refresh_token property returns the token."""
        handler = JWTAuthHandler("https://archidekt.com")
        handler._refresh_token = "test_refresh_token"

        assert handler.refresh_token == "test_refresh_token"

    def test_refresh_token_property_none(self):
        """Test refresh_token property returns None when not set."""
        handler = JWTAuthHandler("https://archidekt.com")
        assert handler.refresh_token is None
