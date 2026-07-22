"""Archidekt-specific exceptions for the pymtg library.

This module provides Archidekt-specific exception classes that inherit from
the base pymtg exception hierarchy. These exceptions provide more specific
information about errors that occur when interacting with the Archidekt API.
"""

from typing import Any

from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NotFoundError,
    PyMTGError,
    RateLimitError,
)


class ArchidektError(PyMTGError):
    """Base exception for Archidekt-specific errors.

    This is the base exception class for all Archidekt-specific errors.
    All Archidekt exceptions inherit from this.

    Attributes:
        message: A human-readable description of the error.
        provider: Always "archidekt".
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
        """Initialize an ArchidektError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
                Defaults to "archidekt".
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
        """
        super().__init__(message, provider or "archidekt", status_code, details)


class ArchidektAuthenticationError(ArchidektError, AuthenticationError):
    """Authentication error specific to Archidekt.

    Raised when authentication with Archidekt fails. This could be due to
    invalid credentials, expired tokens, or other authentication-related issues.

    This class multiply inherits from :class:`ArchidektError` and
    :class:`AuthenticationError` so it is catchable both as
    ``ArchidektError`` and as ``AuthenticationError``.

    Attributes:
        auth_type: The type of authentication that failed (default: "jwt").
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        auth_type: str | None = "jwt",
    ) -> None:
        """Initialize an ArchidektAuthenticationError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
                Defaults to "archidekt".
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            auth_type: The type of authentication that failed. Defaults to
                "jwt".
        """
        super().__init__(message, provider or "archidekt", status_code, details)
        self.auth_type = auth_type


class ArchidektNotFoundError(ArchidektError, NotFoundError):
    """Not found error specific to Archidekt.

    Raised when a requested resource (card, deck, etc.) is not found on Archidekt.

    This class multiply inherits from :class:`ArchidektError` and
    :class:`NotFoundError` so it is catchable both as ``ArchidektError``
    and as ``NotFoundError``.

    Attributes:
        resource_type: The type of resource that was not found.
        resource_id: The identifier of the resource that was not found, or None.
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
        """Initialize an ArchidektNotFoundError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
                Defaults to "archidekt".
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            resource_type: The type of resource that was not found.
            resource_id: The identifier of the resource that was not found.
        """
        super().__init__(message, provider or "archidekt", status_code, details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ArchidektRateLimitError(ArchidektError, RateLimitError):
    """Rate limit error specific to Archidekt.

    Raised when Archidekt's rate limit has been exceeded. See Archidekt's
    official API documentation for the current rate limit.

    This class multiply inherits from :class:`ArchidektError` and
    :class:`RateLimitError` so it is catchable both as ``ArchidektError``
    and as ``RateLimitError``.

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
        """Initialize an ArchidektRateLimitError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
                Defaults to "archidekt".
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            retry_after: Number of seconds to wait before retrying.
        """
        super().__init__(message, provider or "archidekt", status_code, details)
        self.retry_after = retry_after


class ArchidektAPIError(ArchidektError, APIError):
    """API error specific to Archidekt.

    Raised when the Archidekt API returns an error that doesn't fit into
    a more specific category. This could be due to server errors, invalid
    API usage, or other unexpected issues.

    This class multiply inherits from :class:`ArchidektError` and
    :class:`APIError` so it is catchable both as ``ArchidektError`` and
    as ``APIError``.

    Attributes:
        message: A human-readable description of the error.
        provider: Always "archidekt".
        status_code: The HTTP status code if applicable.
        details: Additional details about the error.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize an ArchidektAPIError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
                Defaults to "archidekt".
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
        """
        super().__init__(message, provider or "archidekt", status_code, details)


class ArchidektValidationError(ArchidektError, InvalidQueryError):
    """Validation error specific to Archidekt.

    Raised when validation of parameters or queries for Archidekt fails.
    This could be due to invalid search parameters, missing required fields,
    or other validation issues.

    This class multiply inherits from :class:`ArchidektError` and
    :class:`InvalidQueryError` so it is catchable both as
    ``ArchidektError`` and as ``InvalidQueryError``.

    Attributes:
        query: The invalid query string, or None.
        provider_specific_message: Archidekt-specific error message, or None.
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
        """Initialize an ArchidektValidationError.

        Args:
            message: A human-readable description of the error.
            provider: The name of the provider where the error occurred.
                Defaults to "archidekt".
            status_code: The HTTP status code if applicable.
            details: Additional details about the error.
            query: The invalid query string.
            provider_specific_message: Archidekt-specific error message.
        """
        super().__init__(message, provider or "archidekt", status_code, details)
        self.query = query
        self.provider_specific_message = provider_specific_message
