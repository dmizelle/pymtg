"""Tests for pymtg.utils.http module.

This module tests the HTTPClient class including URL validation,
header handling, and request building.
"""

import unittest

from pymtg.utils.http import HTTPClient


class TestHTTPClient(unittest.TestCase):
    """Tests for the HTTPClient class."""

    def test_http_client_creation_valid_base_url(self) -> None:
        """Test HTTPClient creation with valid base URLs."""
        client = HTTPClient("https://api.example.com")
        self.assertEqual(client.base_url, "https://api.example.com")

        client = HTTPClient("http://api.example.com/")
        self.assertEqual(client.base_url, "http://api.example.com")

        client = HTTPClient("http://api.example.com:8080")
        self.assertEqual(client.base_url, "http://api.example.com:8080")

    def test_http_client_creation_invalid_base_url(self) -> None:
        """Test HTTPClient raises ValueError for invalid base URLs."""
        with self.assertRaises(
            ValueError,
            msg="base_url must be a valid URL starting with http:// or https://",
        ):
            HTTPClient("not-a-url")

        with self.assertRaises(
            ValueError,
            msg="base_url must be a valid URL starting with http:// or https://",
        ):
            HTTPClient("")

        with self.assertRaises(
            ValueError,
            msg="base_url must be a valid URL starting with http:// or https://",
        ):
            HTTPClient("ftp://api.example.com")

    def test_http_client_creation_trailing_slash_stripped(self) -> None:
        """Test HTTPClient strips trailing slashes from base_url."""
        client = HTTPClient("https://api.example.com///")
        self.assertEqual(client.base_url, "https://api.example.com")

    def test_http_client_creation_whitespace_stripped(self) -> None:
        """Test HTTPClient strips whitespace from base_url."""
        client = HTTPClient("  https://api.example.com  ")
        self.assertEqual(client.base_url, "https://api.example.com")

    def test_http_client_creation_non_string_base_url(self) -> None:
        """Test HTTPClient raises ValueError for non-string base_url."""
        with self.assertRaises(ValueError, msg="base_url must be a string"):
            HTTPClient(123)  # type: ignore[arg-type]

        with self.assertRaises(ValueError, msg="base_url must be a string"):
            HTTPClient(None)  # type: ignore[arg-type]

    def test_http_client_default_timeout(self) -> None:
        """Test HTTPClient default timeout value."""
        client = HTTPClient("https://api.example.com")
        self.assertEqual(client.timeout, 30)

    def test_http_client_custom_timeout(self) -> None:
        """Test HTTPClient custom timeout value."""
        client = HTTPClient("https://api.example.com", timeout=60)
        self.assertEqual(client.timeout, 60)

    def test_http_client_default_user_agent(self) -> None:
        """Test HTTPClient uses default User-Agent."""
        client = HTTPClient("https://api.example.com")
        self.assertIsNotNone(client.user_agent)

    def test_http_client_custom_user_agent(self) -> None:
        """Test HTTPClient uses custom User-Agent."""
        client = HTTPClient("https://api.example.com", user_agent="custom/1.0")
        self.assertEqual(client.user_agent, "custom/1.0")

    def test_build_url_with_relative_endpoint(self) -> None:
        """Test _build_url with relative endpoint."""
        client = HTTPClient("https://api.example.com")
        url = client._build_url("/cards")
        self.assertEqual(url, "https://api.example.com/cards")

    def test_build_url_with_endpoint_no_leading_slash(self) -> None:
        """Test _build_url with endpoint that has no leading slash."""
        client = HTTPClient("https://api.example.com")
        url = client._build_url("cards")
        self.assertEqual(url, "https://api.example.com/cards")

    def test_build_url_with_full_url_endpoint(self) -> None:
        """Test _build_url with absolute URL endpoint."""
        client = HTTPClient("https://api.example.com")
        url = client._build_url("https://other.com/cards")
        self.assertEqual(url, "https://other.com/cards")

    def test_build_url_with_empty_endpoint(self) -> None:
        """Test _build_url raises ValueError for empty endpoint."""
        client = HTTPClient("https://api.example.com")
        with self.assertRaises(ValueError, msg="endpoint must be a non-empty string"):
            client._build_url("")

    def test_build_url_with_whitespace_only_endpoint(self) -> None:
        """Test _build_url raises ValueError for whitespace-only endpoint."""
        client = HTTPClient("https://api.example.com")
        with self.assertRaises(ValueError, msg="endpoint must be a non-empty string"):
            client._build_url("   ")

    def test_build_url_with_none_endpoint(self) -> None:
        """Test _build_url raises ValueError for None endpoint."""
        client = HTTPClient("https://api.example.com")
        with self.assertRaises(ValueError, msg="endpoint must be a string"):
            client._build_url(None)  # type: ignore[arg-type]

    def test_build_url_with_non_string_endpoint(self) -> None:
        """Test _build_url raises ValueError for non-string endpoint."""
        client = HTTPClient("https://api.example.com")
        with self.assertRaises(ValueError, msg="endpoint must be a string"):
            client._build_url(123)  # type: ignore[arg-type]
