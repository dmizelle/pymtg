"""Tests for pymtg.utils.http module.

This module tests the HTTPClient class including URL validation,
header handling, and request building.
"""

import pytest

from pymtg.utils.http import DEFAULT_USER_AGENT, HTTPClient


def test_http_client_creation_valid_base_url() -> None:
    """Test HTTPClient creation with valid base URLs."""
    client = HTTPClient("https://api.example.com")
    assert client.base_url == "https://api.example.com"

    client = HTTPClient("http://api.example.com/")
    assert client.base_url == "http://api.example.com"

    client = HTTPClient("http://api.example.com:8080")
    assert client.base_url == "http://api.example.com:8080"


def test_http_client_creation_invalid_base_url() -> None:
    """Test HTTPClient raises ValueError for invalid base URLs."""
    expected = "base_url must be a valid URL starting with http:// or https://"
    for invalid in ("not-a-url", "", "ftp://api.example.com"):
        with pytest.raises(ValueError, match=expected):
            HTTPClient(invalid)


def test_http_client_creation_trailing_slash_stripped() -> None:
    """Test HTTPClient strips trailing slashes from base_url."""
    client = HTTPClient("https://api.example.com///")
    assert client.base_url == "https://api.example.com"


def test_http_client_creation_whitespace_stripped() -> None:
    """Test HTTPClient strips whitespace from base_url."""
    client = HTTPClient("  https://api.example.com  ")
    assert client.base_url == "https://api.example.com"


def test_http_client_creation_non_string_base_url() -> None:
    """Test HTTPClient raises ValueError for non-string base_url."""
    with pytest.raises(ValueError, match="base_url must be a string"):
        HTTPClient(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="base_url must be a string"):
        HTTPClient(None)  # type: ignore[arg-type]


def test_http_client_default_timeout() -> None:
    """Test HTTPClient default timeout value."""
    client = HTTPClient("https://api.example.com")
    assert client.timeout == 30.0


def test_http_client_custom_timeout() -> None:
    """Test HTTPClient custom timeout value."""
    client = HTTPClient("https://api.example.com", timeout=60)
    assert client.timeout == 60


def test_http_client_float_timeout() -> None:
    """Test HTTPClient accepts float timeout for sub-second precision."""
    client = HTTPClient("https://api.example.com", timeout=0.5)
    assert client.timeout == 0.5

    client = HTTPClient("https://api.example.com", timeout=2.5)
    assert client.timeout == 2.5


def test_http_client_invalid_timeout_zero() -> None:
    """Test HTTPClient raises ValueError for zero timeout."""
    with pytest.raises(ValueError, match="timeout must be a positive number"):
        HTTPClient("https://api.example.com", timeout=0)


def test_http_client_invalid_timeout_negative() -> None:
    """Test HTTPClient raises ValueError for negative timeout."""
    with pytest.raises(ValueError, match="timeout must be a positive number"):
        HTTPClient("https://api.example.com", timeout=-1)


def test_http_client_invalid_timeout_boolean() -> None:
    """Test HTTPClient raises ValueError for boolean timeout."""
    with pytest.raises(ValueError, match="timeout must be a positive number"):
        HTTPClient("https://api.example.com", timeout=True)  # type: ignore[arg-type]


def test_http_client_invalid_timeout_non_numeric() -> None:
    """Test HTTPClient raises ValueError for non-numeric timeout."""
    with pytest.raises(ValueError, match="timeout must be a positive number"):
        HTTPClient("https://api.example.com", timeout="abc")  # type: ignore[arg-type]


def test_http_client_default_user_agent() -> None:
    """Test HTTPClient uses default User-Agent."""
    client = HTTPClient("https://api.example.com")
    assert client.user_agent == DEFAULT_USER_AGENT


def test_http_client_empty_user_agent_falls_back_to_default() -> None:
    """Test that an empty user_agent falls back to the default.

    The implementation uses ``user_agent or DEFAULT_USER_AGENT``, so a
    falsy value (empty string) must fall back to the default rather than
    leaving the User-Agent unset.
    """
    client = HTTPClient("https://api.example.com", user_agent="")
    assert client.user_agent == DEFAULT_USER_AGENT


def test_http_client_custom_user_agent() -> None:
    """Test HTTPClient uses custom User-Agent."""
    client = HTTPClient("https://api.example.com", user_agent="custom/1.0")
    assert client.user_agent == "custom/1.0"


def test_build_url_with_relative_endpoint() -> None:
    """Test _build_url with relative endpoint."""
    client = HTTPClient("https://api.example.com")
    url = client._build_url("/cards")
    assert url == "https://api.example.com/cards"


def test_build_url_with_endpoint_no_leading_slash() -> None:
    """Test _build_url with endpoint that has no leading slash."""
    client = HTTPClient("https://api.example.com")
    url = client._build_url("cards")
    assert url == "https://api.example.com/cards"


def test_build_url_rejects_full_url_endpoint() -> None:
    """Test _build_url rejects absolute URL endpoints to prevent SSRF."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="absolute URLs are not permitted"):
        client._build_url("https://other.com/cards")


def test_build_url_rejects_protocol_relative_url() -> None:
    """Test _build_url rejects protocol-relative URLs to prevent SSRF."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="protocol-relative URLs are not permitted"):
        client._build_url("//evil.com/cards")


def test_build_url_rejects_path_traversal() -> None:
    """Test _build_url rejects endpoints that escape the base path."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="escape the base path"):
        client._build_url("../../etc/passwd")
    with pytest.raises(ValueError, match="escape the base path"):
        client._build_url("../admin/secret")


def test_build_url_rejects_encoded_path_traversal() -> None:
    """Test _build_url rejects percent-encoded traversal sequences."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="escape the base path"):
        client._build_url("%2e%2e/%2e%2e/etc/passwd")
    with pytest.raises(ValueError, match="escape the base path"):
        client._build_url("..%2f..%2fadmin/secret")


def test_build_url_with_empty_endpoint() -> None:
    """Test _build_url raises ValueError for empty endpoint."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="endpoint must be a non-empty string"):
        client._build_url("")


def test_build_url_with_whitespace_only_endpoint() -> None:
    """Test _build_url raises ValueError for whitespace-only endpoint."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="endpoint must be a non-empty string"):
        client._build_url("   ")


def test_build_url_with_none_endpoint() -> None:
    """Test _build_url raises ValueError for None endpoint."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="endpoint must be a string"):
        client._build_url(None)  # type: ignore[arg-type]


def test_build_url_with_non_string_endpoint() -> None:
    """Test _build_url raises ValueError for non-string endpoint."""
    client = HTTPClient("https://api.example.com")
    with pytest.raises(ValueError, match="endpoint must be a string"):
        client._build_url(123)  # type: ignore[arg-type]
