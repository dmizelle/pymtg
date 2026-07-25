"""Tests for Archidekt-specific exceptions.

This module tests the Archidekt-specific exception classes in
pymtg.providers.archidekt.exceptions, covering all the requirements
specified in the task list including:
- Exception hierarchy (isinstance checks)
- Exception messages are properly set
- Exception attributes (provider, status_code, etc.)
"""

from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NotFoundError,
    PyMTGError,
    RateLimitError,
)
from pymtg.providers.archidekt.exceptions import (
    ArchidektAPIError,
    ArchidektAuthenticationError,
    ArchidektError,
    ArchidektNotFoundError,
    ArchidektRateLimitError,
    ArchidektValidationError,
)


class TestArchidektExceptionHierarchy:
    """Tests for the Archidekt exception hierarchy."""

    def test_archidekt_error_inherits_from_pymtg_error(self):
        """Test ArchidektError inherits from PyMTGError."""
        error = ArchidektError("Test error")
        assert isinstance(error, PyMTGError)
        assert isinstance(error, Exception)

    def test_archidekt_authentication_error_inherits_from_authentication_error(self):
        """Test ArchidektAuthenticationError inherits from AuthenticationError."""
        error = ArchidektAuthenticationError("Test auth error")
        assert isinstance(error, AuthenticationError)
        assert isinstance(error, PyMTGError)
        assert isinstance(error, Exception)

    def test_archidekt_not_found_error_inherits_from_not_found_error(self):
        """Test ArchidektNotFoundError inherits from NotFoundError."""
        error = ArchidektNotFoundError("Test not found error")
        assert isinstance(error, NotFoundError)
        assert isinstance(error, PyMTGError)
        assert isinstance(error, Exception)

    def test_archidekt_rate_limit_error_inherits_from_rate_limit_error(self):
        """Test ArchidektRateLimitError inherits from RateLimitError."""
        error = ArchidektRateLimitError("Test rate limit error")
        assert isinstance(error, RateLimitError)
        assert isinstance(error, PyMTGError)
        assert isinstance(error, Exception)

    def test_archidekt_api_error_inherits_from_api_error(self):
        """Test ArchidektAPIError inherits from APIError."""
        error = ArchidektAPIError("Test API error")
        assert isinstance(error, APIError)
        assert isinstance(error, PyMTGError)
        assert isinstance(error, Exception)

    def test_archidekt_validation_error_inherits_from_invalid_query_error(self):
        """Test ArchidektValidationError inherits from InvalidQueryError."""
        error = ArchidektValidationError("Test validation error")
        assert isinstance(error, InvalidQueryError)
        assert isinstance(error, PyMTGError)
        assert isinstance(error, Exception)


class TestArchidektExceptionMessages:
    """Tests for exception message handling."""

    def test_archidekt_error_message(self):
        """Test ArchidektError message is set correctly."""
        message = "Test error message"
        error = ArchidektError(message)
        assert str(error).startswith("[archidekt]")
        assert message in str(error)

    def test_archidekt_authentication_error_message(self):
        """Test ArchidektAuthenticationError message is set correctly."""
        message = "Authentication failed"
        error = ArchidektAuthenticationError(message)
        assert str(error).startswith("[archidekt]")
        assert message in str(error)

    def test_archidekt_not_found_error_message(self):
        """Test ArchidektNotFoundError message is set correctly."""
        message = "Deck not found"
        error = ArchidektNotFoundError(message)
        assert str(error).startswith("[archidekt]")
        assert message in str(error)

    def test_archidekt_rate_limit_error_message(self):
        """Test ArchidektRateLimitError message is set correctly."""
        message = "Rate limit exceeded"
        error = ArchidektRateLimitError(message)
        assert str(error).startswith("[archidekt]")
        assert message in str(error)

    def test_archidekt_api_error_message(self):
        """Test ArchidektAPIError message is set correctly."""
        message = "API error occurred"
        error = ArchidektAPIError(message)
        assert str(error).startswith("[archidekt]")
        assert message in str(error)

    def test_archidekt_validation_error_message(self):
        """Test ArchidektValidationError message is set correctly."""
        message = "Invalid query parameters"
        error = ArchidektValidationError(message)
        assert str(error).startswith("[archidekt]")
        assert message in str(error)


class TestArchidektExceptionAttributes:
    """Tests for exception attributes."""

    def test_archidekt_error_provider_default(self):
        """Test ArchidektError has provider set to 'archidekt' by default."""
        error = ArchidektError("Test error")
        assert error.provider == "archidekt"

    def test_archidekt_error_provider_custom(self):
        """Test ArchidektError can have custom provider."""
        error = ArchidektError("Test error", provider="custom_provider")
        assert error.provider == "custom_provider"

    def test_archidekt_error_status_code(self):
        """Test ArchidektError stores status_code."""
        error = ArchidektError("Test error", status_code=404)
        assert error.status_code == 404

    def test_archidekt_error_details(self):
        """Test ArchidektError stores details."""
        details = {"field": "value"}
        error = ArchidektError("Test error", details=details)
        assert error.details == details

    def test_archidekt_authentication_error_auth_type(self):
        """Test ArchidektAuthenticationError stores auth_type."""
        error = ArchidektAuthenticationError("Test error", auth_type="jwt")
        assert error.auth_type == "jwt"

    def test_archidekt_authentication_error_auth_type_default(self):
        """Test ArchidektAuthenticationError has default auth_type of 'jwt'."""
        error = ArchidektAuthenticationError("Test error")
        assert error.auth_type == "jwt"

    def test_archidekt_not_found_error_resource_type(self):
        """Test ArchidektNotFoundError stores resource_type."""
        error = ArchidektNotFoundError("Test error", resource_type="deck")
        assert error.resource_type == "deck"

    def test_archidekt_not_found_error_resource_id(self):
        """Test ArchidektNotFoundError stores resource_id."""
        error = ArchidektNotFoundError("Test error", resource_id="12345")
        assert error.resource_id == "12345"

    def test_archidekt_rate_limit_error_retry_after(self):
        """Test ArchidektRateLimitError stores retry_after."""
        error = ArchidektRateLimitError("Test error", retry_after=30)
        assert error.retry_after == 30

    def test_archidekt_validation_error_query(self):
        """Test ArchidektValidationError stores query."""
        error = ArchidektValidationError("Test error", query="name:test")
        assert error.query == "name:test"

    def test_archidekt_validation_error_provider_specific_message(self):
        """Test ArchidektValidationError stores provider_specific_message."""
        error = ArchidektValidationError(
            "Test error", provider_specific_message="Invalid syntax"
        )
        assert error.provider_specific_message == "Invalid syntax"


class TestArchidektExceptionStrRepresentation:
    """Tests for string representation of exceptions."""

    def test_archidekt_error_str_includes_status_code(self):
        """Test ArchidektError __str__ includes status code."""
        error = ArchidektError("Test error", status_code=500)
        error_str = str(error)
        assert "500" in error_str
        assert "status code" in error_str

    def test_archidekt_rate_limit_error_str_includes_retry_after(self):
        """Test ArchidektRateLimitError __str__ includes retry_after."""
        error = ArchidektRateLimitError("Test error", retry_after=60)
        error_str = str(error)
        assert "Retry after" in error_str
        assert "60s" in error_str

    def test_archidekt_not_found_error_str_includes_resource(self):
        """Test ArchidektNotFoundError __str__ includes resource info."""
        error = ArchidektNotFoundError(
            "Test error", resource_type="card", resource_id="123"
        )
        error_str = str(error)
        assert "Resource" in error_str
        assert "card" in error_str
        assert "123" in error_str

    def test_archidekt_authentication_error_str_includes_auth_type(self):
        """Test ArchidektAuthenticationError __str__ includes auth_type."""
        error = ArchidektAuthenticationError("Test error", auth_type="jwt")
        error_str = str(error)
        assert "Auth type" in error_str
        assert "jwt" in error_str


class TestArchidektExceptionRepr:
    """Tests for repr representation of exceptions."""

    def test_archidekt_error_repr(self):
        """Test ArchidektError __repr__ includes all attributes."""
        error = ArchidektError("Test error", status_code=404, details={"key": "value"})
        error_repr = repr(error)
        assert "ArchidektError" in error_repr
        assert "Test error" in error_repr
        assert "archidekt" in error_repr

    def test_archidekt_authentication_error_repr(self):
        """Test ArchidektAuthenticationError __repr__ includes auth_type."""
        error = ArchidektAuthenticationError("Test error", auth_type="jwt")
        error_repr = repr(error)
        assert "ArchidektAuthenticationError" in error_repr
        assert "jwt" in error_repr

    def test_archidekt_rate_limit_error_repr(self):
        """Test ArchidektRateLimitError __repr__ includes retry_after."""
        error = ArchidektRateLimitError("Test error", retry_after=30)
        error_repr = repr(error)
        assert "ArchidektRateLimitError" in error_repr
        assert "30" in error_repr


class TestArchidektExceptionEquality:
    """Tests for exception equality and hashing."""

    def test_archidekt_errors_are_not_equal_to_other_exceptions(self):
        """Test that Archidekt exceptions are not equal to base exceptions."""
        archidekt_error = ArchidektError("Test error")
        pymtg_error = PyMTGError("Test error")

        assert archidekt_error != pymtg_error
        assert type(archidekt_error) is not type(pymtg_error)

    def test_archidekt_authentication_error_not_equal_to_base(self):
        """Test ArchidektAuthenticationError is not equal to AuthenticationError."""
        archidekt_error = ArchidektAuthenticationError("Test error")
        auth_error = AuthenticationError("Test error")

        assert type(archidekt_error) is not type(auth_error)

    def test_same_type_same_attributes_identity_equality(self):
        """Test same-type ArchidektError instances use identity equality.

        ArchidektError does not define ``__eq__``, so equality is
        identity-based: two distinct instances with identical attributes
        are not equal, while an instance equals itself.
        """
        error1 = ArchidektError("Test error", status_code=404, details={"key": "value"})
        error2 = ArchidektError("Test error", status_code=404, details={"key": "value"})
        assert error1 != error2
        assert error1 == error1

    def test_same_type_different_attributes_identity_equality(self):
        """Test same-type instances with differing attributes are not equal."""
        error1 = ArchidektError("Test error", status_code=404)
        error2 = ArchidektError("Test error", status_code=500)
        assert error1 != error2
