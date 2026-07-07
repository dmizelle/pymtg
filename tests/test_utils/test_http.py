"""Tests for pymtg.utils.http module.

This module tests the HTTPClient class including URL validation,
header handling, and request building.
"""

from pymtg.utils.http import HTTPClient


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
    try:
        HTTPClient("not-a-url")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert (
            str(e) == "base_url must be a valid URL starting with http:// or https://"
        )

    try:
        HTTPClient("")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert (
            str(e) == "base_url must be a valid URL starting with http:// or https://"
        )

    try:
        HTTPClient("ftp://api.example.com")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert (
            str(e) == "base_url must be a valid URL starting with http:// or https://"
        )


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
    try:
        HTTPClient(123)  # type: ignore[arg-type]
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "base_url must be a string"

    try:
        HTTPClient(None)  # type: ignore[arg-type]
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "base_url must be a string"


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


def test_http_client_default_user_agent() -> None:
    """Test HTTPClient uses default User-Agent."""
    client = HTTPClient("https://api.example.com")
    assert client.user_agent is not None


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


def test_build_url_with_full_url_endpoint() -> None:
    """Test _build_url with absolute URL endpoint."""
    client = HTTPClient("https://api.example.com")
    url = client._build_url("https://other.com/cards")
    assert url == "https://other.com/cards"


def test_build_url_with_empty_endpoint() -> None:
    """Test _build_url raises ValueError for empty endpoint."""
    client = HTTPClient("https://api.example.com")
    try:
        client._build_url("")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "endpoint must be a non-empty string"


def test_build_url_with_whitespace_only_endpoint() -> None:
    """Test _build_url raises ValueError for whitespace-only endpoint."""
    client = HTTPClient("https://api.example.com")
    try:
        client._build_url("   ")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "endpoint must be a non-empty string"


def test_build_url_with_none_endpoint() -> None:
    """Test _build_url raises ValueError for None endpoint."""
    client = HTTPClient("https://api.example.com")
    try:
        client._build_url(None)  # type: ignore[arg-type]
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "endpoint must be a string"


def test_build_url_with_non_string_endpoint() -> None:
    """Test _build_url raises ValueError for non-string endpoint."""
    client = HTTPClient("https://api.example.com")
    try:
        client._build_url(123)  # type: ignore[arg-type]
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "endpoint must be a string"
