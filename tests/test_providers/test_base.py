"""Tests for the BaseProvider class and common provider functionality.

This module tests the base provider functionality including response handling,
rate limiting, and error conditions that are common across all providers.
"""

import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from pymtg.config import ProviderConfig
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.card import Card
from pymtg.models.enums import Color
from pymtg.providers.base import BaseProvider
from pymtg.utils.http import HTTPClient


class MockProvider(BaseProvider):
    """Concrete implementation of BaseProvider for testing.

    Note: We cannot call super().__init__() because BaseProvider.__init__()
    looks up config from PROVIDER_CONFIGS using self.__class__.__name__.lower(),
    which would be "mockprovider" - not a valid provider. We manually initialize
    all required attributes instead.
    """

    def __init__(self, name: str = "test", base_url: str = "https://test.com"):
        """Initialize mock provider.

        Args:
            name: Provider name.
            base_url: Base URL for the provider.
        """
        self.name = name
        self.base_url = base_url
        self.config = ProviderConfig(name="test")
        self.http_client: HTTPClient | None = None
        self.rate_limit: dict[str, Any] = {}
        self._lock = threading.Lock()

    def authenticate(self) -> None:
        """Mock authentication."""
        pass

    def is_authenticated(self) -> bool:
        """Mock authentication check."""
        return True

    def refresh(self) -> None:
        """Mock refresh."""
        pass

    def search(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
    ) -> list[Card]:
        """Mock search. Required by BaseProvider abstract interface."""
        return []

    def search_syntax(
        self,
        query: str,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
    ) -> list[Card]:
        """Mock search_syntax. Required by BaseProvider abstract interface."""
        return []

    def get_card(self, card_id: str) -> None:
        """Mock get_card. Required by BaseProvider abstract interface."""
        return None


class TestHandleResponse:
    """Tests for the _handle_response method."""

    def test_handle_response_200_ok(self):
        """Test that 200 status code returns without error."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = {"data": "test"}

        result = provider._handle_response(response)
        assert result == {"data": "test"}

    def test_handle_response_201_ok(self):
        """Test that other 2xx status codes also return parsed JSON."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 201
        response.headers = {}
        response.json.return_value = {"data": "created"}

        result = provider._handle_response(response)
        assert result == {"data": "created"}

    def test_handle_response_json_fallback_to_text(self):
        """Test that a JSON parse failure returns response.text instead."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.json.side_effect = ValueError("invalid JSON")
        response.text = "<html>not json</html>"

        result = provider._handle_response(response)
        assert result == "<html>not json</html>"

    def test_handle_response_404_raises_not_found(self):
        """Test that 404 status code raises NotFoundError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 404
        response.headers = {}
        response.json.return_value = {"error": "not found"}
        response.text = "not found"

        with pytest.raises(NotFoundError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 404

    def test_handle_response_404_with_resource_type(self):
        """Test that resource_type propagates onto NotFoundError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 404
        response.headers = {}
        response.json.return_value = {"error": "not found"}
        response.text = "not found"

        with pytest.raises(NotFoundError) as exc_info:
            provider._handle_response(response, resource_type="card")

        assert exc_info.value.resource_type == "card"

    def test_handle_response_401_raises_authentication_error(self):
        """Test that 401 status code raises AuthenticationError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 401
        response.headers = {}
        response.json.return_value = {"detail": "Unauthorized"}
        response.text = "Unauthorized"

        with pytest.raises(AuthenticationError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 401

    def test_handle_response_403_raises_authentication_error(self):
        """Test that 403 status code raises AuthenticationError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 403
        response.headers = {}
        response.json.return_value = {"detail": "Forbidden"}
        response.text = "Forbidden"

        with pytest.raises(AuthenticationError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 403

    def test_handle_response_429_with_numeric_retry_after(self):
        """Test that 429 status code with numeric Retry-After raises RateLimitError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "60"}

        with pytest.raises(RateLimitError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 60

    def test_handle_response_429_with_zero_retry_after(self):
        """Test that 429 status code with 0 Retry-After raises RateLimitError with None."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "0"}

        with pytest.raises(RateLimitError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after is None

    def test_handle_response_429_with_http_date_retry_after(self):
        """Test that 429 status code with HTTP-date Retry-After parses date correctly."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 429

        # Use a dynamically generated future date and format it with
        # email.utils.format_datetime to guarantee RFC 2822-compliant,
        # English-locale output regardless of the runtime locale.
        from email.utils import format_datetime

        future_date = datetime.now(timezone.utc) + timedelta(days=1)
        http_date = format_datetime(future_date, usegmt=True)
        response.headers = {"Retry-After": http_date}

        with pytest.raises(RateLimitError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after is not None
        assert exc_info.value.retry_after > 0

        # Verify the parsed date is correct by comparing with expected delta
        # Allow 1 second tolerance for execution time
        expected_retry_after = int(timedelta(days=1).total_seconds())
        assert abs(exc_info.value.retry_after - expected_retry_after) <= 1

    def test_handle_response_429_without_retry_after(self):
        """Test that 429 status code without Retry-After uses default 0."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 429
        response.headers = {}

        with pytest.raises(RateLimitError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after is None

    def test_handle_response_400_raises_api_error(self):
        """Test that 400 status code raises APIError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 400
        response.headers = {}
        response.json.return_value = {"error": "bad request"}
        response.text = "bad request"

        with pytest.raises(APIError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 400

    def test_handle_response_500_raises_api_error(self):
        """Test that 500 status code raises APIError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 500
        response.headers = {}
        response.json.return_value = {"error": "server error"}
        response.text = "server error"

        with pytest.raises(APIError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 500


class TestClose:
    """Tests for the close() method."""

    def test_close_with_http_client(self):
        """Test that close() calls http_client.close() when http_client exists."""
        provider = MockProvider()
        provider.http_client = MagicMock()

        provider.close()

        provider.http_client.close.assert_called_once()

    def test_close_without_http_client(self):
        """Test that close() handles None http_client gracefully."""
        provider = MockProvider()
        provider.http_client = None

        # Should not raise AttributeError
        provider.close()
