"""Tests for the OAuth2 client credentials authentication handler.

This module tests pymtg.auth.oauth2.OAuth2ClientCredentialsHandler, focusing
on the atomicity of authenticate() state updates: a parsing failure midway
through token processing must not leave the handler in a half-authenticated
state where apply_auth() would use a token but is_authenticated() returns
False.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from pymtg.auth.oauth2 import OAuth2ClientCredentialsHandler
from pymtg.exceptions import AuthenticationError, NetworkError


def _make_success_response(
    access_token: str = "test_token",
    token_type: str = "Bearer",
    expires_in: int | None = 3600,
) -> MagicMock:
    """Build a mock 200 response with the given token fields.

    Args:
        access_token: The access_token value in the response body.
        token_type: The token_type value in the response body.
        expires_in: The expires_in value in the response body.

    Returns:
        A MagicMock simulating a successful OAuth2 token response.
    """
    response = MagicMock()
    response.status_code = 200
    body: dict[str, object] = {
        "access_token": access_token,
        "token_type": token_type,
    }
    if expires_in is not None:
        body["expires_in"] = expires_in
    response.json.return_value = body
    return response


class TestOAuth2AtomicStateUpdate:
    """Tests that authenticate() updates state atomically.

    A parsing failure (e.g. invalid expires_in type) must not leave
    access_token/token_type set while _authenticated remains False.
    """

    def test_successful_authenticate_sets_all_fields(self):
        """Test that a successful authenticate() sets every related field.

        Verifies access_token, token_type, expires_at, and _authenticated
        are all populated after a successful token request.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        mock_response = _make_success_response(
            access_token="abc123", token_type="Bearer", expires_in=3600
        )
        with patch("pymtg.auth.oauth2.requests.post", return_value=mock_response):
            handler.authenticate()

        assert handler.access_token == "abc123"
        assert handler.token_type == "Bearer"
        assert handler.expires_at is not None
        assert handler._authenticated is True
        assert handler.is_authenticated() is True

    def test_expires_in_string_does_not_corrupt_state(self):
        """Test that a non-numeric expires_in leaves state fully clean.

        This is the core scenario from issue #180: if expires_in is a
        string, timedelta(seconds=expires_in) raises TypeError. The fix
        catches this and raises AuthenticationError instead, so the
        method's documented contract is honored. All instance attributes
        must remain at their pre-authenticate defaults.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        mock_response = _make_success_response(expires_in=3600)
        # Override expires_in with a string to trigger TypeError in timedelta.
        mock_response.json.return_value["expires_in"] = "not_a_number"

        with patch("pymtg.auth.oauth2.requests.post", return_value=mock_response):
            # The TypeError from timedelta is now caught and re-raised as
            # AuthenticationError, consistent with the method's contract.
            with pytest.raises(AuthenticationError):
                handler.authenticate()

        # All state fields must remain at their pre-authenticate defaults.
        assert handler.access_token is None
        assert handler.token_type is None
        assert handler.expires_at is None
        assert handler._authenticated is False
        assert handler.is_authenticated() is False

    def test_apply_auth_does_not_apply_token_after_failed_parse(self):
        """Test that apply_auth is a no-op after a failed authenticate().

        Because the atomic update pattern prevents access_token from being
        set when parsing fails, apply_auth() (which checks access_token and
        token_type) must not modify the session.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        mock_response = _make_success_response(expires_in=3600)
        mock_response.json.return_value["expires_in"] = "bad"

        with patch("pymtg.auth.oauth2.requests.post", return_value=mock_response):
            with pytest.raises(AuthenticationError):
                handler.authenticate()

        session = MagicMock()
        handler.apply_auth(session)
        # apply_auth() must not modify the session when no token is set.
        session.headers.update.assert_not_called()

    def test_missing_expires_in_authenticates_without_expiry(self):
        """Test that a missing expires_in field authenticates successfully.

        When the token response omits expires_in, expires_at is set to None
        and the handler is still authenticated.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        mock_response = _make_success_response(expires_in=None)

        with patch("pymtg.auth.oauth2.requests.post", return_value=mock_response):
            handler.authenticate()

        assert handler.access_token == "test_token"
        assert handler.token_type == "Bearer"
        assert handler.expires_at is None
        assert handler._authenticated is True
        assert handler.is_authenticated() is True

    def test_zero_expires_in_authenticates(self):
        """Test that expires_in=0 sets an immediately-expired token.

        A zero expires_in means the token is expired now, so expires_at
        should be set to (approximately) the current time and
        is_authenticated() should return False.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        mock_response = _make_success_response(expires_in=0)

        with patch("pymtg.auth.oauth2.requests.post", return_value=mock_response):
            handler.authenticate()

        assert handler._authenticated is True
        assert handler.expires_at is not None
        assert handler.is_authenticated() is False

    def test_failed_http_response_does_not_set_state(self):
        """Test that a non-200 response leaves all state untouched.

        An AuthenticationError is raised and no instance attributes are
        modified.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "invalid_client"}

        with patch("pymtg.auth.oauth2.requests.post", return_value=mock_response):
            with pytest.raises(AuthenticationError):
                handler.authenticate()

        assert handler.access_token is None
        assert handler.token_type is None
        assert handler.expires_at is None
        assert handler._authenticated is False
        assert handler.is_authenticated() is False

    def test_network_error_does_not_set_state(self):
        """Test that a network error leaves all state untouched.

        A NetworkError is raised and no instance attributes are modified.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        with patch(
            "pymtg.auth.oauth2.requests.post",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            with pytest.raises(NetworkError):
                handler.authenticate()

        assert handler.access_token is None
        assert handler.token_type is None
        assert handler.expires_at is None
        assert handler._authenticated is False

    def test_reauthenticate_after_failure_succeeds(self):
        """Test that a failed authenticate() can be retried successfully.

        Because the failed attempt left no partial state, a subsequent
        successful authenticate() works normally.
        """
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        # First attempt: bad expires_in causes AuthenticationError.
        bad_response = _make_success_response(expires_in=3600)
        bad_response.json.return_value["expires_in"] = "bad"
        with patch("pymtg.auth.oauth2.requests.post", return_value=bad_response):
            with pytest.raises(AuthenticationError):
                handler.authenticate()
        assert handler.is_authenticated() is False

        # Second attempt: valid response succeeds.
        good_response = _make_success_response(expires_in=3600)
        with patch("pymtg.auth.oauth2.requests.post", return_value=good_response):
            handler.authenticate()
        assert handler.is_authenticated() is True
        assert handler.access_token == "test_token"


class TestOAuth2HandlerInterface:
    """Tests for OAuth2ClientCredentialsHandler interface behavior."""

    def test_is_authenticated_false_when_not_authenticated(self):
        """Test that a fresh handler is not authenticated."""
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        assert handler.is_authenticated() is False

    def test_is_authenticated_false_when_expired(self):
        """Test that an expired token is not authenticated."""
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        handler._authenticated = True
        handler.access_token = "token"
        handler.expires_at = datetime.now() - timedelta(seconds=1)
        assert handler.is_authenticated() is False

    def test_authenticate_requires_credentials(self):
        """Test that authenticate() raises without client credentials."""
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
        )
        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate()
        assert "Client ID and client secret are required" in str(exc_info.value)

    def test_clear_auth_resets_all_state(self):
        """Test that clear_auth() resets every authentication field."""
        handler = OAuth2ClientCredentialsHandler(
            token_url="https://example.com/token",
            client_id="cid",
            client_secret="csecret",
        )
        handler.access_token = "token"
        handler.token_type = "Bearer"
        handler.expires_at = datetime.now() + timedelta(seconds=60)
        handler._authenticated = True

        handler.clear_auth()

        assert handler.access_token is None
        assert handler.token_type is None
        assert handler.expires_at is None
        assert handler._authenticated is False
        assert handler.is_authenticated() is False
