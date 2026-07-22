"""Custom exception hierarchy for the pymtg library.

This module provides a comprehensive exception hierarchy that allows for
consistent error handling across all providers. Each exception type
provides specific information about the error that occurred.

All ``__str__`` methods use a standardized format for additional
information: string values are rendered with ``!r`` for clarity and
to handle edge cases like empty strings or whitespace. Numeric and
dict values use their default string representation.
"""

from typing import Any


class PyMTGError(Exception):
    """Base exception for all pymtg errors.

    This is the root exception class for all errors raised by the pymtg library.
    All provider-specific and library-specific exceptions inherit from this.

    Attributes:
        provider: The name of the provider where the error occurred, or None.
        message: A human-readable description of the error.
        status_code: The HTTP status code if applicable, or None.
        details: Additional details about the error, or None.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a PyMTGError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
        """
        super().__init__(message)
        self.provider = provider
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def __str__(self) -> str:
        """Return a string representation of the error.

        Returns:
            A formatted string containing the error details.
        """
        class_name = self.__class__.__name__
        parts = [f"{class_name}: {self.message}"]
        if self.provider is not None:
            parts[0] = f"[{self.provider}] {parts[0]}"
        if self.status_code is not None:
            parts.append(f"(status code: {self.status_code})")
        if self.details:
            parts.append(f"Details: {self.details}")
        return " ".join(parts)

    def __repr__(self) -> str:
        """Return a detailed representation of the error.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r})"
        )


class RateLimitError(PyMTGError):
    """Rate limit exceeded error.

    Raised when a provider's rate limit has been exceeded.

    Attributes:
        retry_after: Number of seconds to wait before retrying, or None.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        """Initialize a RateLimitError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            retry_after: Number of seconds to wait before retrying.
        """
        super().__init__(message, provider, status_code, details)
        self.retry_after = retry_after

    def __str__(self) -> str:
        """Return a string representation of the error.

        Returns:
            A formatted string containing the error details.
        """
        base = super().__str__()
        if self.retry_after is not None:
            base += f" Retry after: {self.retry_after}s"
        return base

    def __repr__(self) -> str:
        """Return a detailed representation of the error.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r}, "
            f"retry_after={self.retry_after!r})"
        )


class NotFoundError(PyMTGError):
    """Resource not found error.

    Raised when a requested resource (card, deck, set, etc.) is not found.

    Attributes:
        resource_type: The type of resource that was not found
            (e.g., 'card', 'deck').
        resource_id: The identifier of the resource that was not found,
            or None.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        resource_type: str = "unknown",
        resource_id: str | None = None,
    ) -> None:
        """Initialize a NotFoundError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            resource_type: The type of resource that was not found.
            resource_id: The identifier of the resource that was not found.
        """
        super().__init__(message, provider, status_code, details)
        self.resource_type = resource_type
        self.resource_id = resource_id

    def __str__(self) -> str:
        """Return a string representation of the error.

        Returns:
            A formatted string containing the error details.
        """
        base = super().__str__()
        base += f" Resource: {self.resource_type!r}"
        if self.resource_id is not None:
            base += f" (id: {self.resource_id!r})"
        return base

    def __repr__(self) -> str:
        """Return a detailed representation of the error.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r}, "
            f"resource_type={self.resource_type!r}, "
            f"resource_id={self.resource_id!r})"
        )


class AuthenticationError(PyMTGError):
    """Authentication failed error.

    Raised when authentication with a provider fails.

    Attributes:
        auth_type: The type of authentication that failed
            (e.g., 'session', 'oauth2').
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        auth_type: str | None = None,
    ) -> None:
        """Initialize an AuthenticationError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            auth_type: The type of authentication that failed.
        """
        super().__init__(message, provider, status_code, details)
        self.auth_type = auth_type

    def __str__(self) -> str:
        """Return a string representation of the error.

        Returns:
            A formatted string containing the error details.
        """
        base = super().__str__()
        if self.auth_type is not None:
            base += f" Auth type: {self.auth_type!r}"
        return base

    def __repr__(self) -> str:
        """Return a detailed representation of the error.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r}, "
            f"auth_type={self.auth_type!r})"
        )


class InvalidQueryError(PyMTGError):
    """Invalid query syntax error.

    Raised when a query string or parameters are invalid.

    Attributes:
        query: The invalid query string, or None.
        provider_specific_message: Provider-specific error message, or None.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        query: str | None = None,
        provider_specific_message: str | None = None,
    ) -> None:
        """Initialize an InvalidQueryError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            query: The invalid query string.
            provider_specific_message: Provider-specific error message.
        """
        super().__init__(message, provider, status_code, details)
        self.query = query
        self.provider_specific_message = provider_specific_message

    def __str__(self) -> str:
        """Return a string representation of the error.

        Returns:
            A formatted string containing the error details.
        """
        base = super().__str__()
        if self.query is not None:
            base += f" Query: {self.query!r}"
        if self.provider_specific_message is not None:
            base += f" Provider message: {self.provider_specific_message!r}"
        return base

    def __repr__(self) -> str:
        """Return a detailed representation of the error.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r}, "
            f"query={self.query!r}, "
            f"provider_specific_message={self.provider_specific_message!r})"
        )


class APIError(PyMTGError):
    """Generic API error.

    Raised when a provider returns an error that doesn't fit into a more
    specific category.
    """

    pass


class NetworkError(PyMTGError):
    """Network-related error.

    Raised when there are network issues such as connection failures,
        timeouts, or DNS resolution errors.

    Attributes:
        original_exception: The original exception that caused this error,
            or None.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        """Initialize a NetworkError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            original_exception: The original exception that caused this error.
        """
        super().__init__(message, provider, status_code, details)
        self.original_exception = original_exception

    def __str__(self) -> str:
        """Return a string representation of the error.

        Returns:
            A formatted string containing the error details.
        """
        base = super().__str__()
        if self.original_exception is not None:
            base += f" Original: {self.original_exception!r}"
        return base

    def __repr__(self) -> str:
        """Return a detailed representation of the error.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r}, "
            f"original_exception={self.original_exception!r})"
        )


class ParsingError(PyMTGError):
    """Data parsing error.

    Raised when data from a provider cannot be parsed into the expected
    model objects.

    Attributes:
        raw_data: The raw data that failed to parse, or None.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        raw_data: dict | str | list | None = None,
    ) -> None:
        """Initialize a ParsingError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            raw_data: The raw data that failed to parse.
        """
        super().__init__(message, provider, status_code, details)
        self.raw_data = raw_data

    def __str__(self) -> str:
        """Return a string representation of the error.

        Returns:
            A formatted string containing the error details.
        """
        base = super().__str__()
        if self.raw_data is not None:
            raw_data_str = repr(self.raw_data)
            if len(raw_data_str) > 200:
                raw_data_str = raw_data_str[:200] + "..."
            base += f" Raw data: {raw_data_str}"
        return base

    def __repr__(self) -> str:
        """Return a detailed representation of the error.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"status_code={self.status_code!r}, "
            f"details={self.details!r}, "
            f"raw_data={self.raw_data!r})"
        )
