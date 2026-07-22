"""Tests for pymtg exception hierarchy.

This module contains comprehensive tests for all pymtg exception classes including:
- PyMTGError (base exception)
- RateLimitError
- NotFoundError
- AuthenticationError
- InvalidQueryError
- APIError
- NetworkError
- ParsingError

Tests cover:
- Exception inheritance hierarchy
- Exception creation with various parameters
- Exception string representations
- Exception attribute access
- Stack trace preservation
"""

import pytest

from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
    ParsingError,
    PyMTGError,
    RateLimitError,
)


class TestPyMTGError:
    """Tests for the base PyMTGError exception."""

    def test_pymtg_error_inheritance(self) -> None:
        """Test that PyMTGError inherits from Exception."""
        assert issubclass(PyMTGError, Exception)

    def test_pymtg_error_creation_basic(self) -> None:
        """Test PyMTGError creation with message only."""
        error = PyMTGError("Test error message")
        assert error.message == "Test error message"
        assert error.provider is None
        assert error.status_code is None
        assert error.details == {}

    def test_pymtg_error_creation_full(self) -> None:
        """Test PyMTGError creation with all parameters."""
        error = PyMTGError(
            message="Test error",
            provider="scryfall",
            status_code=404,
            details={"key": "value"},
        )
        assert error.message == "Test error"
        assert error.provider == "scryfall"
        assert error.status_code == 404
        assert error.details == {"key": "value"}

    def test_pymtg_error_str_basic(self) -> None:
        """Test PyMTGError string representation without provider."""
        error = PyMTGError("Test error")
        str_repr = str(error)
        assert "PyMTGError: Test error" in str_repr

    def test_pymtg_error_str_with_provider(self) -> None:
        """Test PyMTGError string representation with provider."""
        error = PyMTGError("Test error", provider="scryfall")
        str_repr = str(error)
        assert "[scryfall]" in str_repr
        assert "PyMTGError: Test error" in str_repr

    def test_pymtg_error_str_with_status_code(self) -> None:
        """Test PyMTGError string representation with status code."""
        error = PyMTGError("Test error", status_code=404)
        str_repr = str(error)
        assert "(status code: 404)" in str_repr

    def test_pymtg_error_str_with_details(self) -> None:
        """Test PyMTGError string representation with details."""
        error = PyMTGError("Test error", details={"key": "value"})
        str_repr = str(error)
        assert "Details:" in str_repr
        assert "key" in str_repr

    def test_pymtg_error_str_all_parameters(self) -> None:
        """Test PyMTGError string representation with all parameters set.

        Verifies the complete formatted output when message, provider,
        status_code, and details are all provided simultaneously, ensuring
        each component appears in the correct order and format.
        """
        error = PyMTGError(
            message="Test error",
            provider="scryfall",
            status_code=404,
            details={"key": "value"},
        )
        str_repr = str(error)
        assert str_repr == (
            "[scryfall] PyMTGError: Test error "
            "(status code: 404) Details: {'key': 'value'}"
        )

    def test_pymtg_error_repr(self) -> None:
        """Test PyMTGError repr representation."""
        error = PyMTGError(
            "Test error",
            provider="scryfall",
            status_code=404,
            details={"key": "value"},
        )
        repr_str = repr(error)
        assert "PyMTGError" in repr_str
        assert "message='Test error'" in repr_str
        assert "provider='scryfall'" in repr_str
        assert "status_code=404" in repr_str


class TestRateLimitError:
    """Tests for the RateLimitError exception."""

    def test_rate_limit_error_inheritance(self) -> None:
        """Test that RateLimitError inherits from PyMTGError."""
        assert issubclass(RateLimitError, PyMTGError)

    def test_rate_limit_error_creation_basic(self) -> None:
        """Test RateLimitError creation with message only."""
        error = RateLimitError("Rate limit exceeded")
        assert error.message == "Rate limit exceeded"
        assert error.retry_after is None

    def test_rate_limit_error_creation_full(self) -> None:
        """Test RateLimitError creation with all parameters."""
        error = RateLimitError(
            message="Rate limit exceeded",
            provider="scryfall",
            status_code=429,
            details={"retry_after": "60"},
            retry_after=60,
        )
        assert error.message == "Rate limit exceeded"
        assert error.provider == "scryfall"
        assert error.status_code == 429
        assert error.retry_after == 60

    def test_rate_limit_error_str_with_retry_after(self) -> None:
        """Test RateLimitError string representation with retry_after."""
        error = RateLimitError("Rate limit exceeded", retry_after=60)
        str_repr = str(error)
        assert "Retry after: 60s" in str_repr

    def test_rate_limit_error_str_without_retry_after(self) -> None:
        """Test RateLimitError string representation without retry_after."""
        error = RateLimitError("Rate limit exceeded")
        str_repr = str(error)
        assert "Retry after:" not in str_repr

    def test_rate_limit_error_str_all_parameters(self) -> None:
        """Test RateLimitError string representation with all parameters set.

        Verifies the complete formatted output when message, provider,
        status_code, details, and retry_after are all provided simultaneously,
        ensuring each component appears in the correct order and format.
        """
        error = RateLimitError(
            message="Rate limit exceeded",
            provider="scryfall",
            status_code=429,
            details={"retry_after": "60"},
            retry_after=60,
        )
        str_repr = str(error)
        assert str_repr == (
            "[scryfall] RateLimitError: Rate limit exceeded "
            "(status code: 429) Details: {'retry_after': '60'} "
            "Retry after: 60s"
        )

    def test_rate_limit_error_repr(self) -> None:
        """Test RateLimitError repr representation."""
        error = RateLimitError("Rate limit exceeded", retry_after=60)
        repr_str = repr(error)
        assert "RateLimitError" in repr_str
        assert "retry_after=60" in repr_str


class TestNotFoundError:
    """Tests for the NotFoundError exception."""

    def test_not_found_error_inheritance(self) -> None:
        """Test that NotFoundError inherits from PyMTGError."""
        assert issubclass(NotFoundError, PyMTGError)

    def test_not_found_error_creation_basic(self) -> None:
        """Test NotFoundError creation with message only."""
        error = NotFoundError("Card not found")
        assert error.message == "Card not found"
        assert error.resource_type == "unknown"
        assert error.resource_id is None

    def test_not_found_error_creation_full(self) -> None:
        """Test NotFoundError creation with all parameters."""
        error = NotFoundError(
            message="Card not found",
            provider="scryfall",
            status_code=404,
            details={"id": "123"},
            resource_type="card",
            resource_id="scryfall-card-123",
        )
        assert error.message == "Card not found"
        assert error.resource_type == "card"
        assert error.resource_id == "scryfall-card-123"

    def test_not_found_error_str(self) -> None:
        """Test NotFoundError string representation."""
        error = NotFoundError(
            "Card not found",
            resource_type="card",
            resource_id="123",
        )
        str_repr = str(error)
        assert "Resource: 'card'" in str_repr
        assert "(id: '123')" in str_repr

    def test_not_found_error_str_without_id(self) -> None:
        """Test NotFoundError string representation without resource_id."""
        error = NotFoundError("Card not found", resource_type="card")
        str_repr = str(error)
        assert "Resource: 'card'" in str_repr
        assert "(id:" not in str_repr

    def test_not_found_error_str_all_parameters(self) -> None:
        """Test NotFoundError string representation with all parameters set.

        Verifies the complete formatted output when message, provider,
        status_code, details, resource_type, and resource_id are all provided
        simultaneously, ensuring each component appears in the correct order
        and format.
        """
        error = NotFoundError(
            message="Card not found",
            provider="scryfall",
            status_code=404,
            details={"id": "123"},
            resource_type="card",
            resource_id="scryfall-card-123",
        )
        str_repr = str(error)
        assert str_repr == (
            "[scryfall] NotFoundError: Card not found "
            "(status code: 404) Details: {'id': '123'} "
            "Resource: 'card' (id: 'scryfall-card-123')"
        )

    def test_not_found_error_repr(self) -> None:
        """Test NotFoundError repr representation."""
        error = NotFoundError("Card not found", resource_type="card", resource_id="123")
        repr_str = repr(error)
        assert "NotFoundError" in repr_str
        assert "resource_type='card'" in repr_str
        assert "resource_id='123'" in repr_str


class TestAuthenticationError:
    """Tests for the AuthenticationError exception."""

    def test_authentication_error_inheritance(self) -> None:
        """Test that AuthenticationError inherits from PyMTGError."""
        assert issubclass(AuthenticationError, PyMTGError)

    def test_authentication_error_creation_basic(self) -> None:
        """Test AuthenticationError creation with message only."""
        error = AuthenticationError("Invalid credentials")
        assert error.message == "Invalid credentials"
        assert error.auth_type is None

    def test_authentication_error_creation_full(self) -> None:
        """Test AuthenticationError creation with all parameters."""
        error = AuthenticationError(
            message="Invalid credentials",
            provider="archidekt",
            status_code=401,
            details={"error": "invalid_token"},
            auth_type="session",
        )
        assert error.message == "Invalid credentials"
        assert error.auth_type == "session"

    def test_authentication_error_str(self) -> None:
        """Test AuthenticationError string representation."""
        error = AuthenticationError("Invalid credentials", auth_type="oauth2")
        str_repr = str(error)
        assert "Auth type: 'oauth2'" in str_repr

    def test_authentication_error_str_without_type(self) -> None:
        """Test AuthenticationError string representation without auth_type."""
        error = AuthenticationError("Invalid credentials")
        str_repr = str(error)
        assert "Auth type:" not in str_repr

    def test_authentication_error_str_all_parameters(self) -> None:
        """Test AuthenticationError string representation with all parameters.

        Verifies the complete formatted output when message, provider,
        status_code, details, and auth_type are all provided simultaneously,
        ensuring each component appears in the correct order and format.
        """
        error = AuthenticationError(
            message="Invalid credentials",
            provider="archidekt",
            status_code=401,
            details={"error": "invalid_token"},
            auth_type="oauth2",
        )
        str_repr = str(error)
        assert str_repr == (
            "[archidekt] AuthenticationError: Invalid credentials "
            "(status code: 401) Details: {'error': 'invalid_token'} "
            "Auth type: 'oauth2'"
        )

    def test_authentication_error_repr(self) -> None:
        """Test AuthenticationError repr representation."""
        error = AuthenticationError("Invalid credentials", auth_type="session")
        repr_str = repr(error)
        assert "AuthenticationError" in repr_str
        assert "auth_type='session'" in repr_str


class TestInvalidQueryError:
    """Tests for the InvalidQueryError exception."""

    def test_invalid_query_error_inheritance(self) -> None:
        """Test that InvalidQueryError inherits from PyMTGError."""
        assert issubclass(InvalidQueryError, PyMTGError)

    def test_invalid_query_error_creation_basic(self) -> None:
        """Test InvalidQueryError creation with message only."""
        error = InvalidQueryError("Invalid query syntax")
        assert error.message == "Invalid query syntax"
        assert error.query is None
        assert error.provider_specific_message is None

    def test_invalid_query_error_creation_full(self) -> None:
        """Test InvalidQueryError creation with all parameters."""
        error = InvalidQueryError(
            message="Invalid query syntax",
            provider="scryfall",
            status_code=400,
            details={"query": "invalid"},
            query="invalid query",
            provider_specific_message="Syntax error at position 5",
        )
        assert error.message == "Invalid query syntax"
        assert error.query == "invalid query"
        assert error.provider_specific_message == "Syntax error at position 5"

    def test_invalid_query_error_str(self) -> None:
        """Test InvalidQueryError string representation."""
        error = InvalidQueryError(
            "Invalid query",
            query="invalid",
            provider_specific_message="Error message",
        )
        str_repr = str(error)
        assert "Query: 'invalid'" in str_repr
        assert "Provider message: 'Error message'" in str_repr

    def test_invalid_query_error_str_minimal(self) -> None:
        """Test InvalidQueryError string representation with minimal info."""
        error = InvalidQueryError("Invalid query")
        str_repr = str(error)
        assert "Query:" not in str_repr
        assert "Provider message:" not in str_repr

    def test_invalid_query_error_str_all_parameters(self) -> None:
        """Test InvalidQueryError string representation with all parameters.

        Verifies the complete formatted output when message, provider,
        status_code, details, query, and provider_specific_message are all
        provided simultaneously, ensuring each component appears in the
        correct order and format.
        """
        error = InvalidQueryError(
            message="Invalid query syntax",
            provider="scryfall",
            status_code=400,
            details={"query": "invalid"},
            query="invalid query",
            provider_specific_message="Syntax error at position 5",
        )
        str_repr = str(error)
        assert str_repr == (
            "[scryfall] InvalidQueryError: Invalid query syntax "
            "(status code: 400) Details: {'query': 'invalid'} "
            "Query: 'invalid query' Provider message: 'Syntax error "
            "at position 5'"
        )

    def test_invalid_query_error_repr(self) -> None:
        """Test InvalidQueryError repr representation."""
        error = InvalidQueryError(
            "Invalid query",
            query="test",
            provider_specific_message="msg",
        )
        repr_str = repr(error)
        assert "InvalidQueryError" in repr_str
        assert "query='test'" in repr_str
        assert "provider_specific_message='msg'" in repr_str


class TestAPIError:
    """Tests for the APIError exception."""

    def test_api_error_inheritance(self) -> None:
        """Test that APIError inherits from PyMTGError."""
        assert issubclass(APIError, PyMTGError)

    def test_api_error_creation(self) -> None:
        """Test APIError creation."""
        error = APIError("Generic API error")
        assert error.message == "Generic API error"

    def test_api_error_str(self) -> None:
        """Test APIError string representation."""
        error = APIError("Generic API error", provider="test", status_code=500)
        str_repr = str(error)
        assert "APIError: Generic API error" in str_repr
        assert "[test]" in str_repr
        assert "(status code: 500)" in str_repr

    def test_api_error_str_all_parameters(self) -> None:
        """Test APIError string representation with all parameters set.

        Verifies the complete formatted output when message, provider,
        status_code, and details are all provided simultaneously. APIError
        inherits __str__ from PyMTGError without override, so the output
        should match the base class format with the APIError class name.
        """
        error = APIError(
            message="Generic API error",
            provider="test",
            status_code=500,
            details={"code": "INTERNAL"},
        )
        str_repr = str(error)
        assert str_repr == (
            "[test] APIError: Generic API error "
            "(status code: 500) Details: {'code': 'INTERNAL'}"
        )

    def test_api_error_repr(self) -> None:
        """Test APIError repr representation.

        APIError inherits ``__repr__`` from PyMTGError without override,
        so the repr should include the APIError class name and all four
        base attributes (message, provider, status_code, details).
        """
        error = APIError(
            message="Generic API error",
            provider="test",
            status_code=500,
            details={"code": "INTERNAL"},
        )
        repr_str = repr(error)
        assert repr_str == (
            "APIError(message='Generic API error', "
            "provider='test', "
            "status_code=500, "
            "details={'code': 'INTERNAL'})"
        )


class TestNetworkError:
    """Tests for the NetworkError exception."""

    def test_network_error_inheritance(self) -> None:
        """Test that NetworkError inherits from PyMTGError."""
        assert issubclass(NetworkError, PyMTGError)

    def test_network_error_creation_basic(self) -> None:
        """Test NetworkError creation with message only."""
        error = NetworkError("Connection failed")
        assert error.message == "Connection failed"
        assert error.original_exception is None

    def test_network_error_creation_full(self) -> None:
        """Test NetworkError creation with all parameters."""
        original_exc = ConnectionError("Connection refused")
        error = NetworkError(
            message="Connection failed",
            provider="scryfall",
            status_code=None,
            details={},
            original_exception=original_exc,
        )
        assert error.message == "Connection failed"
        assert error.original_exception == original_exc

    def test_network_error_str_with_original_exception(self) -> None:
        """Test NetworkError string representation with original exception."""
        original_exc = ConnectionError("Connection refused")
        error = NetworkError("Connection failed", original_exception=original_exc)
        str_repr = str(error)
        assert "Original:" in str_repr
        assert "ConnectionError" in str_repr
        assert "Connection refused" in str_repr

    def test_network_error_str_without_original_exception(self) -> None:
        """Test NetworkError string representation without original exception."""
        error = NetworkError("Connection failed")
        str_repr = str(error)
        assert "Original:" not in str_repr

    def test_network_error_str_all_parameters(self) -> None:
        """Test NetworkError string representation with all parameters set.

        Verifies the complete formatted output when message, provider,
        status_code, details, and original_exception are all provided
        simultaneously, ensuring each component appears in the correct order
        and format.
        """
        original_exc = ConnectionError("Connection refused")
        error = NetworkError(
            message="Connection failed",
            provider="scryfall",
            status_code=503,
            details={"timeout": 30},
            original_exception=original_exc,
        )
        str_repr = str(error)
        assert str_repr == (
            "[scryfall] NetworkError: Connection failed "
            "(status code: 503) Details: {'timeout': 30} "
            "Original: ConnectionError('Connection refused')"
        )

    def test_network_error_repr(self) -> None:
        """Test NetworkError repr representation."""
        original_exc = ConnectionError("Connection refused")
        error = NetworkError("Connection failed", original_exception=original_exc)
        repr_str = repr(error)
        assert "NetworkError" in repr_str
        assert "original_exception=" in repr_str


class TestParsingError:
    """Tests for the ParsingError exception."""

    def test_parsing_error_inheritance(self) -> None:
        """Test that ParsingError inherits from PyMTGError."""
        assert issubclass(ParsingError, PyMTGError)

    def test_parsing_error_creation_basic(self) -> None:
        """Test ParsingError creation with message only."""
        error = ParsingError("Failed to parse card")
        assert error.message == "Failed to parse card"
        assert error.provider is None
        assert error.status_code is None
        assert error.details == {}
        assert error.raw_data is None

    def test_parsing_error_creation_full(self) -> None:
        """Test ParsingError creation with all parameters."""
        raw = {"id": 123, "name": "Bad Card"}
        error = ParsingError(
            message="Failed to parse card",
            provider="scryfall",
            status_code=500,
            details={"field": "name"},
            raw_data=raw,
        )
        assert error.message == "Failed to parse card"
        assert error.provider == "scryfall"
        assert error.status_code == 500
        assert error.details == {"field": "name"}
        assert error.raw_data == raw

    def test_parsing_error_str_without_raw_data(self) -> None:
        """Test ParsingError string representation without raw data."""
        error = ParsingError("Failed to parse", provider="scryfall")
        str_repr = str(error)
        assert "Raw data:" not in str_repr
        assert "[scryfall] ParsingError: Failed to parse" in str_repr

    def test_parsing_error_str_with_raw_data(self) -> None:
        """Test ParsingError string representation includes raw data."""
        error = ParsingError(
            "Failed to parse",
            provider="scryfall",
            raw_data={"bad": "data"},
        )
        str_repr = str(error)
        assert "Raw data:" in str_repr
        assert "{'bad': 'data'}" in str_repr

    def test_parsing_error_str_truncates_long_raw_data(self) -> None:
        """Test that long raw_data is truncated to 200 chars plus ellipsis."""
        long_raw = "x" * 500
        error = ParsingError("Failed to parse", raw_data=long_raw)
        str_repr = str(error)
        assert "Raw data:" in str_repr
        assert "..." in str_repr
        # The repr of the raw data string is truncated to 200 chars.
        raw_section = str_repr.split("Raw data: ", 1)[1]
        assert len(raw_section) <= 203  # 200 + "..."

    def test_parsing_error_str_raw_data_none_omitted(self) -> None:
        """Test that raw_data=None omits the Raw data section."""
        error = ParsingError("Failed to parse", raw_data=None)
        assert "Raw data:" not in str(error)

    def test_parsing_error_repr(self) -> None:
        """Test ParsingError repr representation."""
        error = ParsingError(
            message="Failed to parse",
            provider="scryfall",
            status_code=500,
            details={"field": "name"},
            raw_data={"bad": "data"},
        )
        repr_str = repr(error)
        assert repr_str == (
            "ParsingError(message='Failed to parse', "
            "provider='scryfall', "
            "status_code=500, "
            "details={'field': 'name'}, "
            "raw_data={'bad': 'data'})"
        )


class TestExceptionHierarchy:
    """Tests for the complete exception hierarchy."""

    def test_all_exceptions_inherit_from_pymtg_error(self) -> None:
        """Test that all specific exceptions inherit from PyMTGError."""
        exceptions = [
            RateLimitError,
            NotFoundError,
            AuthenticationError,
            InvalidQueryError,
            APIError,
            NetworkError,
            ParsingError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, PyMTGError)

    def test_all_exceptions_inherit_from_exception(self) -> None:
        """Test that all exceptions ultimately inherit from Exception."""
        exceptions = [
            PyMTGError,
            RateLimitError,
            NotFoundError,
            AuthenticationError,
            InvalidQueryError,
            APIError,
            NetworkError,
            ParsingError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, Exception)

    def test_isinstance_checks(self) -> None:
        """Test isinstance checks for exception hierarchy."""
        rate_error = RateLimitError("Rate limit")
        not_found_error = NotFoundError("Not found")
        auth_error = AuthenticationError("Auth failed")
        query_error = InvalidQueryError("Invalid query")
        api_error = APIError("API error")
        network_error = NetworkError("Network error")
        parsing_error = ParsingError("Parsing error")

        # All should be instances of PyMTGError
        assert isinstance(rate_error, PyMTGError)
        assert isinstance(not_found_error, PyMTGError)
        assert isinstance(auth_error, PyMTGError)
        assert isinstance(query_error, PyMTGError)
        assert isinstance(api_error, PyMTGError)
        assert isinstance(network_error, PyMTGError)
        assert isinstance(parsing_error, PyMTGError)

        # All should be instances of Exception
        assert isinstance(rate_error, Exception)
        assert isinstance(not_found_error, Exception)
        assert isinstance(auth_error, Exception)
        assert isinstance(query_error, Exception)
        assert isinstance(api_error, Exception)
        assert isinstance(network_error, Exception)
        assert isinstance(parsing_error, Exception)

        # Specific type checks
        assert isinstance(rate_error, RateLimitError)
        assert not isinstance(rate_error, NotFoundError)
        assert isinstance(not_found_error, NotFoundError)
        assert not isinstance(not_found_error, RateLimitError)


class TestExceptionStackTrace:
    """Tests for stack trace preservation in exceptions."""

    def test_exception_raises_properly(self) -> None:
        """Test that exceptions can be raised and caught properly."""
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError("Rate limit exceeded", retry_after=60)

        assert exc_info.value.message == "Rate limit exceeded"
        assert exc_info.value.retry_after == 60

    def test_exception_with_traceback(self) -> None:
        """Test that exceptions preserve traceback information."""

        def inner_function() -> None:
            """Inner function that raises a NotFoundError for testing."""
            raise NotFoundError("Card not found", resource_type="card")

        def outer_function() -> None:
            """Outer function that calls inner_function for testing."""
            inner_function()

        with pytest.raises(NotFoundError) as exc_info:
            outer_function()

        # Check that the exception was raised correctly
        assert exc_info.value.message == "Card not found"
        assert exc_info.value.resource_type == "card"

        # Check that traceback is available
        assert exc_info.traceback is not None

    def test_exception_chaining(self) -> None:
        """Test exception chaining with NetworkError."""
        original_exc = ConnectionError("Connection refused")

        with pytest.raises(NetworkError) as exc_info:
            try:
                raise original_exc
            except ConnectionError as e:
                raise NetworkError(
                    "Connection failed",
                    original_exception=e,
                ) from e

        assert exc_info.value.original_exception == original_exc


class TestExceptionEquality:
    """Tests for exception equality and comparison."""

    def test_exception_equality(self) -> None:
        """Test exceptions with same attributes: identity-based equality.

        PyMTGError does not define ``__eq__``, so equality falls back to
        identity comparison. Two distinct instances with identical
        attributes are therefore not equal, while an instance is equal
        to itself.
        """
        error1 = PyMTGError("Error", provider="test", status_code=400)
        error2 = PyMTGError("Error", provider="test", status_code=400)
        assert error1.message == error2.message
        assert error1.provider == error2.provider
        assert error1.status_code == error2.status_code
        # No __eq__ defined; equality is identity-based.
        assert error1 != error2
        assert error1 == error1

    def test_exception_inequality(self) -> None:
        """Test that exceptions with different attributes are not equal."""
        error1 = PyMTGError("Error1", provider="test")
        error2 = PyMTGError("Error2", provider="test")
        assert error1.message != error2.message


class TestExceptionAttributes:
    """Tests for exception attribute access and modification."""

    def test_attribute_access(self) -> None:
        """Test that all exception attributes are accessible."""
        error = NotFoundError(
            message="Not found",
            provider="scryfall",
            status_code=404,
            details={"id": "123"},
            resource_type="card",
            resource_id="456",
        )

        assert error.message == "Not found"
        assert error.provider == "scryfall"
        assert error.status_code == 404
        assert error.details == {"id": "123"}
        assert error.resource_type == "card"
        assert error.resource_id == "456"

    def test_attribute_modification(self) -> None:
        """Test that exception attributes can be modified after creation."""
        error = PyMTGError("Original message")
        error.message = "Modified message"
        assert error.message == "Modified message"

    def test_default_values(self) -> None:
        """Test that exception attributes have correct default values."""
        error = PyMTGError("Test")
        assert error.provider is None
        assert error.status_code is None
        assert error.details == {}

        rate_error = RateLimitError("Test")
        assert rate_error.retry_after is None

        not_found_error = NotFoundError("Test")
        assert not_found_error.resource_type == "unknown"
        assert not_found_error.resource_id is None

        auth_error = AuthenticationError("Test")
        assert auth_error.auth_type is None

        query_error = InvalidQueryError("Test")
        assert query_error.query is None
        assert query_error.provider_specific_message is None

        network_error = NetworkError("Test")
        assert network_error.original_exception is None

        parsing_error = ParsingError("Test")
        assert parsing_error.raw_data is None
