"""HAR (HTTP Archive) logging utility for debugging HTTP requests.

This module provides HAR logging functionality for capturing and exporting
HTTP request and response data in the standard HAR format (version 1.2).
This is useful for debugging API interactions and understanding request/response
cycles.

HAR format specification: http://www.softwareishard.com/blog/har-12-spec/
"""

import copy
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HARRequest:
    """Represents an HTTP request entry in HAR format.

    Attributes:
        method: HTTP method (GET, POST, PUT, etc.).
        url: The full URL of the request.
        http_version: HTTP version (e.g., "HTTP/1.1").
        headers: List of header dictionaries with name and value.
        query_string: List of query parameter dictionaries.
        cookies: List of cookie dictionaries.
        post_data: Post data information.
        body_size: Size of the request body in bytes.
        headers_size: Size of the request headers in bytes.
    """

    method: str
    url: str
    http_version: str = "HTTP/1.1"
    headers: list[dict[str, str]] = field(default_factory=list)
    query_string: list[dict[str, str]] = field(default_factory=list)
    cookies: list[dict[str, str]] = field(default_factory=list)
    post_data: dict[str, Any] = field(default_factory=dict)
    body_size: int = 0
    headers_size: int = 0


@dataclass
class HARResponse:
    """Represents an HTTP response entry in HAR format.

    Attributes:
        status: HTTP status code.
        status_text: HTTP status text.
        http_version: HTTP version.
        headers: List of header dictionaries with name and value.
        cookies: List of cookie dictionaries.
        content: Content information including size, mime_type, and text.
        redirect_url: Redirect URL if any.
        headers_size: Size of the response headers in bytes.
        body_size: Size of the response body in bytes.
    """

    status: int
    status_text: str = ""
    http_version: str = "HTTP/1.1"
    headers: list[dict[str, str]] = field(default_factory=list)
    cookies: list[dict[str, str]] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    redirect_url: str = ""
    headers_size: int = 0
    body_size: int = 0


@dataclass
class HAREntry:
    """Represents a single entry (request + response) in HAR format.

    Attributes:
        pageref: Reference to the page that initiated this request.
        started_date_time: ISO 8601 formatted date/time when the request started.
        time: Total time for the request in milliseconds.
        request: The HARRequest object.
        response: The HARResponse object (None if no response yet).
        cache: Cache information.
        timings: Timing information for the request.
    """

    pageref: str = ""
    started_date_time: str = ""
    time: float = 0.0
    request: HARRequest | None = None
    response: HARResponse | None = None
    cache: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the entry to a dictionary for JSON serialization.

        Returns:
            Dictionary representation of the HAR entry.
        """
        result: dict[str, Any] = {
            "pageref": self.pageref,
            "startedDateTime": self.started_date_time,
            "time": self.time,
            "cache": self.cache,
            "timings": self.timings,
        }

        if self.request:
            result["request"] = {
                "method": self.request.method,
                "url": self.request.url,
                "httpVersion": self.request.http_version,
                "headers": self.request.headers,
                "queryString": self.request.query_string,
                "cookies": self.request.cookies,
                "postData": self.request.post_data,
                "headersSize": self.request.headers_size,
                "bodySize": self.request.body_size,
            }

        if self.response:
            result["response"] = {
                "status": self.response.status,
                "statusText": self.response.status_text,
                "httpVersion": self.response.http_version,
                "headers": self.response.headers,
                "cookies": self.response.cookies,
                "content": self.response.content,
                "redirectURL": self.response.redirect_url,
                "headersSize": self.response.headers_size,
                "bodySize": self.response.body_size,
            }

        return result


class HARLogger:
    """HAR (HTTP Archive) logger for capturing HTTP request/response data.

    This class captures HTTP requests and responses in the standard HAR format
    (version 1.2) for debugging and analysis purposes. It supports enabling/disabling
    logging, sanitizing sensitive data, and exporting to HAR files.

    The HAR format is commonly used by web debugging tools and can be imported
    into various analysis tools.

    Attributes:
        entries: List of captured HAR entries.
        enabled: Whether logging is currently enabled.
        sanitize_fields: List of field names to sanitize in request/response bodies.
        sanitize_headers: List of header names to sanitize.
        page_id: ID for the current "page" (used for pageref).
        sanitized_value: Value to use when sanitizing sensitive data.
    """

    # Headers that should be sanitized by default
    DEFAULT_SANITIZE_HEADERS: frozenset[str] = frozenset(
        {
            "authorization",
            "cookie",
            "set-cookie",
            "x-csrftoken",
            "csrftoken",
            "x-api-key",
            "api-key",
            "www-authenticate",
            "proxy-authorization",
        }
    )

    # Field names that should be sanitized in JSON bodies
    DEFAULT_SANITIZE_FIELDS: frozenset[str] = frozenset(
        {
            "password",
            "username",
            "email",
            "token",
            "access_token",
            "refresh_token",
            "secret",
            "api_key",
            "credentials",
        }
    )

    def __init__(
        self,
        enabled: bool = False,
        sanitize_headers: frozenset[str] | None = None,
        sanitize_fields: frozenset[str] | None = None,
        sanitized_value: str = "[REDACTED]",
        page_id: str = "page_1",
        preserve_binary: bool = False,
    ) -> None:
        """Initialize the HARLogger.

        Args:
            enabled: Whether logging is enabled by default.
            sanitize_headers: Set of header names to sanitize.
                Defaults to DEFAULT_SANITIZE_HEADERS.
            sanitize_fields: Set of field names to sanitize in JSON bodies.
                Defaults to DEFAULT_SANITIZE_FIELDS.
            sanitized_value: Value to use when sanitizing sensitive data.
            page_id: ID for the current page (used for pageref).
            preserve_binary: If True, preserve binary body content instead of
                sanitizing it. Defaults to False for security.
        """
        self.entries: list[HAREntry] = []
        self._enabled = enabled
        self.sanitize_headers = sanitize_headers or self.DEFAULT_SANITIZE_HEADERS
        self.sanitize_fields = sanitize_fields or self.DEFAULT_SANITIZE_FIELDS
        self.sanitized_value = sanitized_value
        self.page_id = page_id
        self.preserve_binary = preserve_binary

    def enable(self) -> None:
        """Enable HAR logging."""
        self._enabled = True
        logger.debug("HAR logging enabled")

    def disable(self) -> None:
        """Disable HAR logging."""
        self._enabled = False
        logger.debug("HAR logging disabled")

    @property
    def enabled(self) -> bool:
        """Check if HAR logging is currently enabled.

        Returns:
            True if logging is enabled, False otherwise.
        """
        return self._enabled

    def clear(self) -> None:
        """Clear all captured entries."""
        self.entries.clear()
        logger.debug("HAR entries cleared")

    def log_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | bytes | dict | None = None,
        http_version: str = "HTTP/1.1",
        query_params: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> str | None:
        """Log an HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, etc.).
            url: The full URL of the request.
            headers: Dictionary of request headers.
            body: Request body (string, bytes, or dict).
            http_version: HTTP version.
            query_params: Dictionary of query parameters.
            cookies: Dictionary of cookies.

        Returns:
            The entry ID if logging is enabled and the request was logged,
            or None if logging is disabled.
        """
        if not self._enabled:
            return None

        # Create request entry
        entry = HAREntry(
            pageref=self.page_id,
            started_date_time=datetime.now(timezone.utc).isoformat(),
            time=0.0,  # Will be updated when response is logged
        )

        # Process headers
        processed_headers = self._process_headers(headers or {})

        # Process body
        processed_body, body_size = self._process_body(body)

        # Process query string
        query_string = self._process_query_params(query_params or {})

        # Process cookies
        processed_cookies = self._process_cookies(cookies or {})

        # Create HAR request
        entry.request = HARRequest(
            method=method.upper(),
            url=url,
            http_version=http_version,
            headers=processed_headers,
            query_string=query_string,
            cookies=processed_cookies,
            post_data=processed_body,
            body_size=body_size,
            headers_size=sum(
                len(f"{h['name']}: {h['value']}") for h in processed_headers
            )
            + 2,  # +2 for CRLF
        )

        self.entries.append(entry)
        return entry.started_date_time

    def log_response(
        self,
        status: int,
        status_text: str = "",
        headers: dict[str, str] | None = None,
        body: str | bytes | dict | None = None,
        http_version: str = "HTTP/1.1",
        cookies: dict[str, str] | None = None,
        redirect_url: str = "",
    ) -> HAREntry | None:
        """Log an HTTP response for the most recent request.

        Args:
            status: HTTP status code.
            status_text: HTTP status text.
            headers: Dictionary of response headers.
            body: Response body (string, bytes, or dict).
            http_version: HTTP version.
            cookies: Dictionary of cookies.
            redirect_url: Redirect URL if any.

        Returns:
            The HAREntry that was updated with the response, or None if
            no request was logged or logging is disabled.
        """
        if not self._enabled or not self.entries:
            return None

        # Find the most recent entry without a response
        # Consider using a request ID or timestamp for more robust matching
        for entry in reversed(self.entries):
            if entry.response is None:
                return self._update_entry_with_response(
                    entry,
                    status,
                    status_text,
                    headers,
                    body,
                    http_version,
                    cookies,
                    redirect_url,
                )

        # No entry without a response found
        return None

    def _update_entry_with_response(
        self,
        entry: HAREntry,
        status: int,
        status_text: str,
        headers: dict[str, str] | None,
        body: str | bytes | dict | None,
        http_version: str,
        cookies: dict[str, str] | None,
        redirect_url: str,
    ) -> HAREntry:
        """Helper method to update an entry with response data."""
        # Process headers
        processed_headers = self._process_headers(headers or {})

        # Process body
        processed_body, body_size = self._process_body(body)

        # Process cookies
        processed_cookies = self._process_cookies(cookies or {})

        # Create HAR response
        entry.response = HARResponse(
            status=status,
            status_text=status_text,
            http_version=http_version,
            headers=processed_headers,
            cookies=processed_cookies,
            content={
                "size": body_size,
                "mimeType": self._get_mime_type(headers or {}),
                "text": processed_body if isinstance(processed_body, str) else "",
            },
            redirect_url=redirect_url,
            headers_size=sum(
                len(f"{h['name']}: {h['value']}") for h in processed_headers
            )
            + 2,
            body_size=body_size,
        )

        # Update timing with actual elapsed time
        try:
            started = datetime.fromisoformat(entry.started_date_time)
            elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            entry.time = max(1, elapsed_ms)  # Ensure at least 1ms
        except (ValueError, TypeError):
            # Fallback if date parsing fails
            entry.time = max(1, entry.time)

        return entry

    def _process_headers(self, headers: dict[str, str]) -> list[dict[str, str]]:
        """Process headers for HAR format.

        Header names are preserved in their original casing. Sanitization
        matching is performed case-insensitively against ``sanitize_headers``.

        Args:
            headers: Dictionary of headers.

        Returns:
            List of header dictionaries with name and value, sanitized.
        """
        result = []
        for name, value in headers.items():
            processed_value = value

            # Sanitize sensitive headers (case-insensitive match)
            if name.lower() in self.sanitize_headers:
                processed_value = self.sanitized_value

            result.append({"name": name, "value": processed_value})

        return result

    def _process_body(self, body: str | bytes | dict | None) -> tuple[Any, int]:
        """Process request/response body for HAR format.

        Args:
            body: The body content.

        Returns:
            Tuple of (processed_body, body_size).
        """
        if body is None:
            return {}, 0

        if isinstance(body, bytes):
            if self.preserve_binary:
                try:
                    processed_body = body.decode("utf-8")
                except UnicodeDecodeError:
                    processed_body = self.sanitized_value
            else:
                processed_body = self.sanitized_value
            body_size = len(body)
        elif isinstance(body, dict):
            processed_body = self._sanitize_dict(copy.deepcopy(body))
            body_size = len(json.dumps(processed_body).encode("utf-8"))
        else:  # string
            processed_body = body
            body_size = len(body.encode("utf-8"))

        return processed_body, body_size

    def _process_query_params(self, params: dict[str, str]) -> list[dict[str, str]]:
        """Process query parameters for HAR format.

        Sensitive query parameters (e.g. ``api_key``, ``token``) are
        redacted using the same field-name-based matching as dict bodies.

        Args:
            params: Dictionary of query parameters.

        Returns:
            List of query parameter dictionaries.
        """
        result = []
        for name, value in params.items():
            processed_name = name.lower()
            if any(sf in processed_name for sf in self.sanitize_fields):
                value = self.sanitized_value
            result.append({"name": name, "value": value})
        return result

    def _process_cookies(self, cookies: dict[str, str]) -> list[dict[str, str]]:
        """Process cookies for HAR format.

        Args:
            cookies: Dictionary of cookies.

        Returns:
            List of cookie dictionaries.
        """
        result = []
        for name, value in cookies.items():
            # Sanitize cookie values if the cookie name is sensitive or by default
            # Common sensitive cookie names
            sensitive_cookie_names = {
                "session",
                "sessionid",
                "auth",
                "token",
                "jwt",
                "csrf",
            }
            should_sanitize = name.lower() in self.sanitize_headers or any(
                sensitive_name in name.lower()
                for sensitive_name in sensitive_cookie_names
            )
            result.append(
                {
                    "name": name,
                    "value": self.sanitized_value if should_sanitize else value,
                }
            )
        return result

    def _sanitize_dict(
        self,
        data: dict | list | tuple | set,
        _seen: set[int] | None = None,
    ) -> dict | list | tuple | set | str:
        """Recursively sanitize sensitive fields in a dictionary or other iterable types.

        Field names are matched exactly (case-insensitively) against
        ``sanitize_fields`` to avoid false-positive redaction of unrelated
        fields that merely contain a sensitive substring.

        Args:
            data: Dictionary, list, tuple, or set to sanitize.
            _seen: Internal set of object IDs to track visited objects for circular
                reference detection.

        Returns:
            Sanitized data with sensitive fields redacted.
        """
        # Primitives are returned as-is; only track container objects for
        # circular-reference detection.
        if not isinstance(data, (dict, list, tuple, set)):
            return data

        # Initialize seen set for tracking circular references
        if _seen is None:
            _seen = set()

        # Get object ID to detect circular references
        obj_id = id(data)

        # Check for circular reference
        if obj_id in _seen:
            return "[CIRCULAR]"

        # Add to seen set
        _seen.add(obj_id)

        if isinstance(data, dict):
            result: dict[str, Any] = {}
            for key, value in data.items():
                processed_key = key.lower() if isinstance(key, str) else key

                # Check if this field should be sanitized (exact match)
                if processed_key in self.sanitize_fields:
                    result[key] = self.sanitized_value
                else:
                    result[key] = self._sanitize_dict(value, _seen)

            return result
        elif isinstance(data, list):
            return [self._sanitize_dict(item, _seen) for item in data]
        elif isinstance(data, (tuple, set)):
            return type(data)(self._sanitize_dict(item, _seen) for item in data)
        else:
            return data

    def _get_mime_type(self, headers: dict[str, str]) -> str:
        """Get the MIME type from headers.

        Args:
            headers: Response headers.

        Returns:
            The MIME type from Content-Type header, or "application/octet-stream".
        """
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        if content_type:
            # Extract just the MIME type (before semicolon if present)
            return content_type.split(";")[0].strip()
        return "application/octet-stream"

    def export(self, filepath: str | None = None) -> str:
        """Export captured entries to a HAR file.

        Args:
            filepath: Path to write the HAR file. If None, returns the HAR
                JSON string without writing to a file.

        Returns:
            The HAR JSON string.

        Raises:
            ValueError: If no entries have been captured.
        """
        if not self.entries:
            raise ValueError("No HAR entries to export")

        # Build the HAR structure
        har_data = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "pymtg",
                    "version": "1.0.0",
                },
                "pages": [{"id": self.page_id, "title": "pymtg HAR Export"}],
                "entries": [entry.to_dict() for entry in self.entries],
            }
        }

        # Convert to JSON with custom serializer for non-serializable objects
        def default_serializer(obj):
            from datetime import date, datetime

            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, bytes):
                try:
                    return obj.decode("utf-8")
                except UnicodeDecodeError:
                    return f"<bytes: {len(obj)} bytes>"
            return str(obj)

        har_json = json.dumps(har_data, indent=2, default=default_serializer)

        # Write to file if filepath provided
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(har_json)
            logger.info("HAR export written to %s", filepath)

        return har_json

    def add_complete_entry(
        self,
        method: str,
        url: str,
        request_headers: dict[str, str] | None = None,
        request_body: str | bytes | dict | None = None,
        response_status: int = 200,
        response_headers: dict[str, str] | None = None,
        response_body: str | bytes | dict | None = None,
        http_version: str = "HTTP/1.1",
    ) -> HAREntry | None:
        """Convenience method to log a complete request/response pair.

        Args:
            method: HTTP method.
            url: Request URL.
            request_headers: Request headers.
            request_body: Request body.
            response_status: Response status code.
            response_headers: Response headers.
            response_body: Response body.
            http_version: HTTP version.

        Returns:
            The HAREntry that was created, or None if logging is disabled.
        """
        if not self._enabled:
            return None

        # Log the request
        request_id = self.log_request(
            method=method,
            url=url,
            headers=request_headers,
            body=request_body,
            http_version=http_version,
        )

        if request_id is None:
            return None

        # Log the response
        return self.log_response(
            status=response_status,
            headers=response_headers,
            body=response_body,
            http_version=http_version,
        )

    def __len__(self) -> int:
        """Return the number of captured entries.

        Returns:
            The number of entries in the logger.
        """
        return len(self.entries)

    def __repr__(self) -> str:
        """Return a string representation of the HARLogger.

        Returns:
            String representation including enabled status and entry count.
        """
        return f"HARLogger(enabled={self._enabled}, entries={len(self.entries)})"

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickle serialization to exclude sensitive data from entries.

        Returns:
            Dictionary of attributes to pickle, with sanitized entries.
        """
        state = self.__dict__.copy()

        # Warn users that entries are excluded from pickle state
        if self.entries:
            logger.warning(
                "HARLogger entries are excluded from pickle state to avoid sensitive data "
                "leakage. All captured entries will be lost during pickling."
            )

        # Don't pickle entries as they may contain sensitive data
        state["entries"] = []

        # Exclude sanitization configuration from pickle state to prevent
        # accidental exposure or inconsistency when unpickling.
        # These will be reset to class defaults on unpickle.
        state.pop("sanitize_headers", None)
        state.pop("sanitize_fields", None)
        state.pop("sanitized_value", None)

        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Custom unpickle deserialization to restore default sanitization settings.

        Args:
            state: Dictionary of attributes from pickle.
        """
        self.__dict__.update(state)
        # Restore default sanitization settings
        self.sanitize_headers = self.DEFAULT_SANITIZE_HEADERS
        self.sanitize_fields = self.DEFAULT_SANITIZE_FIELDS
        self.sanitized_value = "[REDACTED]"
