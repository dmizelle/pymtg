"""Tests for the BaseProvider class and common provider functionality.

This module tests the base provider functionality including response handling,
rate limiting, and error conditions that are common across all providers.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pymtg.config import ProviderConfig
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)
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

    def authenticate(self, **kwargs) -> None:
        """Mock authentication."""
        pass

    def is_authenticated(self) -> bool:
        """Mock authentication check."""
        return True

    def refresh(self) -> None:
        """Mock refresh."""
        pass

    def search(self, query: str, **kwargs) -> list:
        """Mock search."""
        return []

    def search_syntax(self, query: str, **kwargs) -> dict:
        """Mock syntax search."""
        return {}

    def get_card(self, card_id: str, **kwargs) -> dict:
        """Mock get_card."""
        return {}

    def get_pricing(self, card_id: str, **kwargs) -> dict:
        """Mock get_pricing."""
        return {}

    def autocomplete(self, query: str, **kwargs) -> list:
        """Mock autocomplete."""
        return []


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

    def test_handle_response_404_raises_not_found(self):
        """Test that 404 status code raises NotFoundError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 404
        response.headers = {}

        with pytest.raises(NotFoundError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 404

    def test_handle_response_401_raises_authentication_error(self):
        """Test that 401 status code raises AuthenticationError."""
        provider = MockProvider()
        response = MagicMock()
        response.status_code = 401
        response.headers = {}

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

        # Use a dynamically generated future date to avoid flakiness
        future_date = datetime.utcnow() + timedelta(days=1)
        http_date = future_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
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

        with pytest.raises(APIError) as exc_info:
            provider._handle_response(response)

        assert exc_info.value.provider == "test"
        assert exc_info.value.status_code == 500
