"""Tests for the HAR logger utility.

This module tests pymtg.utils.har_logger.HARLogger, covering all the requirements
specified in the task list including:
- Enable/disable functionality
- Request logging captures all fields
- Response logging captures all fields
- Export creates valid HAR file
- Sensitive data is sanitized in export
- clear() removes all entries
- HAR file contains correct structure (version 1.2)
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from pymtg.utils.har_logger import HAREntry, HARLogger, HARRequest, HARResponse


class TestHARLoggerInitialization:
    """Tests for HARLogger initialization."""

    def test_init_default_values(self):
        """Test HARLogger initializes with default values."""
        logger = HARLogger()

        assert logger.enabled is False
        assert len(logger.entries) == 0
        assert logger.sanitized_value == "[REDACTED]"
        assert logger.page_id == "page_1"
        assert "authorization" in logger.sanitize_headers
        assert "password" in logger.sanitize_fields

    def test_init_enabled(self):
        """Test HARLogger can be initialized with enabled=True."""
        logger = HARLogger(enabled=True)
        assert logger.enabled is True

    def test_init_custom_sanitize_headers(self):
        """Test HARLogger can be initialized with custom sanitize headers."""
        custom_headers = frozenset({"x-custom-header"})
        logger = HARLogger(sanitize_headers=custom_headers)
        assert logger.sanitize_headers == custom_headers

    def test_init_custom_sanitize_fields(self):
        """Test HARLogger can be initialized with custom sanitize fields."""
        custom_fields = frozenset({"custom_field"})
        logger = HARLogger(sanitize_fields=custom_fields)
        assert logger.sanitize_fields == custom_fields

    def test_init_custom_sanitized_value(self):
        """Test HARLogger can be initialized with custom sanitized value."""
        logger = HARLogger(sanitized_value="***HIDDEN***")
        assert logger.sanitized_value == "***HIDDEN***"

    def test_init_custom_page_id(self):
        """Test HARLogger can be initialized with custom page ID."""
        logger = HARLogger(page_id="custom_page")
        assert logger.page_id == "custom_page"


class TestHARLoggerEnableDisable:
    """Tests for enable/disable functionality."""

    def test_enable_disable(self):
        """Test enable and disable methods work correctly."""
        logger = HARLogger()

        assert logger.enabled is False

        logger.enable()
        assert logger.enabled is True

        logger.disable()
        assert logger.enabled is False

    def test_logging_disabled_by_default(self):
        """Test that logging is disabled by default."""
        logger = HARLogger()

        # Try to log when disabled
        result = logger.log_request("GET", "https://example.com")
        assert result is None
        assert len(logger.entries) == 0

    def test_logging_when_enabled(self):
        """Test that logging works when enabled."""
        logger = HARLogger(enabled=True)

        result = logger.log_request("GET", "https://example.com")
        assert result is not None
        assert len(logger.entries) == 1


class TestHARLoggerClear:
    """Tests for clear() functionality."""

    def test_clear_removes_all_entries(self):
        """Test clear() removes all entries."""
        logger = HARLogger(enabled=True)

        # Add some entries
        logger.log_request("GET", "https://example.com/1")
        logger.log_request("GET", "https://example.com/2")
        assert len(logger.entries) == 2

        # Clear entries
        logger.clear()
        assert len(logger.entries) == 0

    def test_clear_when_empty(self):
        """Test clear() works when no entries exist."""
        logger = HARLogger()
        logger.clear()  # Should not raise an error
        assert len(logger.entries) == 0


class TestHARLoggerRequestLogging:
    """Tests for request logging functionality."""

    def test_log_request_basic(self):
        """Test logging a basic request."""
        logger = HARLogger(enabled=True)

        logger.log_request("GET", "https://example.com")

        assert len(logger.entries) == 1
        entry = logger.entries[0]
        assert entry.request is not None
        assert entry.request.method == "GET"
        assert entry.request.url == "https://example.com"
        assert entry.response is None

    def test_log_request_with_headers(self):
        """Test logging a request with headers."""
        logger = HARLogger(enabled=True)

        headers = {"Content-Type": "application/json", "User-Agent": "test"}
        logger.log_request("POST", "https://example.com", headers=headers)

        entry = logger.entries[0]
        assert entry.request is not None
        assert len(entry.request.headers) == 2
        header_dicts = {h["name"]: h["value"] for h in entry.request.headers}
        assert header_dicts["Content-Type"] == "application/json"
        assert header_dicts["User-Agent"] == "test"

    def test_log_request_with_string_body(self):
        """Test logging a request with string body."""
        logger = HARLogger(enabled=True)

        body = '{"key": "value"}'
        logger.log_request("POST", "https://example.com", body=body)

        entry = logger.entries[0]
        assert entry.request is not None
        assert entry.request.post_data == body
        assert entry.request.body_size == len(body)

    def test_log_request_with_dict_body(self):
        """Test logging a request with dict body."""
        logger = HARLogger(enabled=True)

        body = {"key": "value", "nested": {"a": 1}}
        logger.log_request("POST", "https://example.com", body=body)

        entry = logger.entries[0]
        assert entry.request is not None
        assert isinstance(entry.request.post_data, dict)
        assert entry.request.post_data["key"] == "value"
        assert entry.request.post_data["nested"]["a"] == 1

    def test_log_request_with_query_params(self):
        """Test logging a request with query parameters."""
        logger = HARLogger(enabled=True)

        params = {"page": "1", "limit": "10"}
        logger.log_request("GET", "https://example.com", query_params=params)

        entry = logger.entries[0]
        assert entry.request is not None
        assert len(entry.request.query_string) == 2
        param_dicts = {p["name"]: p["value"] for p in entry.request.query_string}
        assert param_dicts["page"] == "1"
        assert param_dicts["limit"] == "10"

    def test_log_request_with_cookies(self):
        """Test logging a request with cookies."""
        logger = HARLogger(enabled=True)

        cookies = {"session_id": "12345", "user_pref": "dark_mode"}
        logger.log_request("GET", "https://example.com", cookies=cookies)

        entry = logger.entries[0]
        assert entry.request is not None
        assert len(entry.request.cookies) == 2
        cookie_dicts = {c["name"]: c["value"] for c in entry.request.cookies}
        assert (
            cookie_dicts["session_id"] == "[REDACTED]"
        )  # session cookies should be sanitized
        assert cookie_dicts["user_pref"] == "dark_mode"

    def test_log_request_sanitizes_authorization_header(self):
        """Test that authorization header is sanitized in request logging."""
        logger = HARLogger(enabled=True)

        headers = {
            "Authorization": "JWT secret_token_123",
            "Content-Type": "application/json",
        }
        logger.log_request("GET", "https://example.com", headers=headers)

        entry = logger.entries[0]
        assert entry.request is not None
        header_dicts = {h["name"]: h["value"] for h in entry.request.headers}
        assert header_dicts["Authorization"] == "[REDACTED]"
        assert header_dicts["Content-Type"] == "application/json"

    def test_log_request_sanitizes_sensitive_body_fields(self):
        """Test that sensitive fields are sanitized in request body."""
        logger = HARLogger(enabled=True)

        body = {
            "username": "test_user",
            "password": "secret_password",
            "email": "user@example.com",
            "token": "jwt_token_here",
            "safe_field": "safe_value",
        }
        logger.log_request("POST", "https://example.com", body=body)

        entry = logger.entries[0]
        assert entry.request is not None
        processed_body = entry.request.post_data

        assert processed_body["username"] == "[REDACTED]"
        assert processed_body["password"] == "[REDACTED]"
        assert processed_body["email"] == "[REDACTED]"
        assert processed_body["token"] == "[REDACTED]"
        assert processed_body["safe_field"] == "safe_value"

    def test_log_request_nested_sanitization(self):
        """Test that nested sensitive fields are sanitized."""
        logger = HARLogger(enabled=True)

        body = {
            "user": {
                "name": "John",
                "credentials": {
                    "password": "nested_secret",
                },
            },
            "settings": {
                "api_key": "key_123",
            },
        }
        logger.log_request("POST", "https://example.com", body=body)

        entry = logger.entries[0]
        assert entry.request is not None
        processed_body = entry.request.post_data

        # The entire credentials dict should be sanitized because "credentials" is in sanitize_fields
        assert processed_body["user"]["credentials"] == "[REDACTED]"
        # api_key field should be sanitized individually
        assert processed_body["settings"]["api_key"] == "[REDACTED]"
        assert processed_body["user"]["name"] == "John"


class TestHARLoggerResponseLogging:
    """Tests for response logging functionality."""

    def test_log_response_basic(self):
        """Test logging a basic response."""
        logger = HARLogger(enabled=True)

        # First log a request
        logger.log_request("GET", "https://example.com")

        # Then log a response
        entry = logger.log_response(status=200)

        assert entry is not None
        assert entry.response is not None
        assert entry.response.status == 200

    def test_log_response_with_headers(self):
        """Test logging a response with headers."""
        logger = HARLogger(enabled=True)

        logger.log_request("GET", "https://example.com")

        headers = {"Content-Type": "application/json", "Server": "nginx"}
        logger.log_response(status=200, headers=headers)

        entry = logger.entries[0]
        assert entry.response is not None
        header_dicts = {h["name"]: h["value"] for h in entry.response.headers}
        assert header_dicts["Content-Type"] == "application/json"
        assert header_dicts["Server"] == "nginx"

    def test_log_response_with_string_body(self):
        """Test logging a response with string body."""
        logger = HARLogger(enabled=True)

        logger.log_request("GET", "https://example.com")

        body = '{"result": "success"}'
        logger.log_response(status=200, body=body)

        entry = logger.entries[0]
        assert entry.response is not None
        assert entry.response.content["text"] == body
        assert entry.response.body_size == len(body)

    def test_log_response_sanitizes_authorization_header(self):
        """Test that authorization header is sanitized in response logging."""
        logger = HARLogger(enabled=True)

        logger.log_request("GET", "https://example.com")

        headers = {"WWW-Authenticate": "Bearer token=" + "a" * 100}
        logger.log_response(status=401, headers=headers)

        entry = logger.entries[0]
        assert entry.response is not None
        header_dicts = {h["name"]: h["value"] for h in entry.response.headers}
        assert header_dicts["WWW-Authenticate"] == "[REDACTED]"

    def test_log_response_without_request(self):
        """Test log_response returns None when no request was logged."""
        logger = HARLogger(enabled=True)

        # No request logged yet
        result = logger.log_response(status=200)
        assert result is None


class TestHARLoggerExport:
    """Tests for export functionality."""

    def test_export_basic_structure(self):
        """Test that export creates valid HAR structure with version 1.2."""
        logger = HARLogger(enabled=True)

        logger.add_complete_entry(
            method="GET",
            url="https://example.com",
            response_status=200,
        )

        har_json = logger.export()
        har_data = json.loads(har_json)

        assert "log" in har_data
        assert har_data["log"]["version"] == "1.2"
        assert "creator" in har_data["log"]
        assert "entries" in har_data["log"]
        assert len(har_data["log"]["entries"]) == 1

    def test_export_multiple_entries(self):
        """Test export with multiple entries."""
        logger = HARLogger(enabled=True)

        logger.add_complete_entry("GET", "https://example.com/1", response_status=200)
        logger.add_complete_entry("POST", "https://example.com/2", response_status=201)

        har_json = logger.export()
        har_data = json.loads(har_json)

        assert len(har_data["log"]["entries"]) == 2

    def test_export_to_file(self):
        """Test export to a file."""
        logger = HARLogger(enabled=True)

        logger.add_complete_entry("GET", "https://example.com", response_status=200)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".har", delete=False) as f:
            filepath = f.name

        try:
            har_json = logger.export(filepath)

            # Verify file was created
            assert os.path.exists(filepath)

            # Verify file content
            with open(filepath, "r") as f:
                file_content = f.read()

            har_data = json.loads(file_content)
            assert "log" in har_data
            assert har_data["log"]["version"] == "1.2"
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_empty_entries_raises_error(self):
        """Test that export raises ValueError when no entries exist."""
        logger = HARLogger()

        with pytest.raises(ValueError) as exc_info:
            logger.export()

        assert "No HAR entries to export" in str(exc_info.value)

    def test_export_sanitizes_sensitive_data(self):
        """Test that export sanitizes sensitive data."""
        logger = HARLogger(enabled=True)

        request_headers = {"Authorization": "Bearer secret_token"}
        request_body = {"password": "secret123", "username": "test_user"}

        logger.log_request(
            "POST",
            "https://example.com/login",
            headers=request_headers,
            body=request_body,
        )

        response_body = {
            "access_token": "jwt_token_here",
            "user": {"email": "user@example.com"},
        }
        logger.log_response(
            status=200,
            body=response_body,
        )

        har_json = logger.export()
        har_data = json.loads(har_json)

        entry = har_data["log"]["entries"][0]

        # Check that sensitive request headers are sanitized
        request_headers_in_har = {
            h["name"]: h["value"] for h in entry["request"]["headers"]
        }
        assert request_headers_in_har.get("Authorization") == "[REDACTED]"

        # Check that sensitive request body fields are sanitized
        request_body_in_har = entry["request"]["postData"]
        assert request_body_in_har["password"] == "[REDACTED]"
        assert request_body_in_har["username"] == "[REDACTED]"

        # Check that sensitive response body fields are not leaked in the export
        response_content_text = entry["response"]["content"].get("text", "")
        assert "jwt_token_here" not in response_content_text
        assert "user@example.com" not in response_content_text

    def test_export_includes_all_required_fields(self):
        """Test that export includes all required HAR fields."""
        logger = HARLogger(enabled=True)

        logger.add_complete_entry(
            method="POST",
            url="https://example.com/api",
            request_headers={"Content-Type": "application/json"},
            request_body={"test": "data"},
            response_status=200,
            response_headers={"Server": "test"},
            response_body={"result": "success"},
        )

        har_json = logger.export()
        har_data = json.loads(har_json)

        entry = har_data["log"]["entries"][0]

        # Check request fields
        assert "request" in entry
        assert "method" in entry["request"]
        assert "url" in entry["request"]
        assert "headers" in entry["request"]
        assert "bodySize" in entry["request"]

        # Check response fields
        assert "response" in entry
        assert "status" in entry["response"]
        assert "headers" in entry["response"]
        assert "content" in entry["response"]
        assert "bodySize" in entry["response"]

        # Check other entry fields
        assert "startedDateTime" in entry
        assert "time" in entry


class TestHARLoggerAddCompleteEntry:
    """Tests for add_complete_entry convenience method."""

    def test_add_complete_entry_basic(self):
        """Test adding a complete request/response pair."""
        logger = HARLogger(enabled=True)

        entry = logger.add_complete_entry(
            method="GET",
            url="https://example.com",
            response_status=200,
        )

        assert entry is not None
        assert len(logger.entries) == 1
        assert entry.request is not None
        assert entry.response is not None
        assert entry.response.status == 200

    def test_add_complete_entry_disabled(self):
        """Test add_complete_entry returns None when disabled."""
        logger = HARLogger(enabled=False)

        entry = logger.add_complete_entry(
            method="GET",
            url="https://example.com",
            response_status=200,
        )

        assert entry is None
        assert len(logger.entries) == 0

    def test_add_complete_entry_all_fields(self):
        """Test add_complete_entry with all fields."""
        logger = HARLogger(enabled=True)

        entry = logger.add_complete_entry(
            method="POST",
            url="https://example.com/api",
            request_headers={"Content-Type": "application/json"},
            request_body={"key": "value"},
            response_status=201,
            response_headers={"Location": "/resource/1"},
            response_body={"id": 1, "status": "created"},
        )

        assert entry is not None
        assert entry.request is not None
        assert entry.response is not None
        assert entry.request.method == "POST"
        assert entry.request.url == "https://example.com/api"
        assert entry.response.status == 201


class TestHARLoggerSecurity:
    """Tests for security-related functionality."""

    def test_pickle_excludes_entries(self):
        """Test __getstate__ excludes entries from pickle."""
        import pickle

        logger = HARLogger(enabled=True)
        logger.add_complete_entry("GET", "https://example.com", response_status=200)

        # Get pickle state
        state = logger.__getstate__()

        # Entries should be empty in pickle state
        assert state["entries"] == []

        # Pickle and unpickle
        pickled = pickle.dumps(logger)
        unpickled_logger = pickle.loads(pickled)

        # Entries should not be present after unpickling
        assert len(unpickled_logger.entries) == 0

    def test_sanitize_all_sensitive_headers(self):
        """Test that all default sensitive headers are sanitized."""
        logger = HARLogger(enabled=True)

        sensitive_headers = {
            "Authorization": "Bearer token",
            "Cookie": "session=123",
            "Set-Cookie": "auth=456",
            "X-CSRFToken": "csrf_token",
            "csrftoken": "csrf_token_2",
            "X-API-Key": "api_key_123",
            "api-key": "api_key_456",
        }

        logger.log_request("GET", "https://example.com", headers=sensitive_headers)

        entry = logger.entries[0]
        assert entry.request is not None
        header_dicts = {h["name"]: h["value"] for h in entry.request.headers}

        # All sensitive headers should be sanitized
        for header_name in sensitive_headers:
            assert header_dicts.get(header_name) == "[REDACTED]"

    def test_case_insensitive_header_sanitization(self):
        """Test that header sanitization is case-insensitive."""
        logger = HARLogger(enabled=True)

        headers = {
            "AUTHORIZATION": "Bearer token",
            "authorization": "Bearer token2",
            "Authorization": "Bearer token3",
        }

        logger.log_request("GET", "https://example.com", headers=headers)

        entry = logger.entries[0]
        assert entry.request is not None
        header_dicts = {h["name"]: h["value"] for h in entry.request.headers}

        # All variations should be sanitized
        for header_name, value in header_dicts.items():
            if header_name.lower() == "authorization":
                assert value == "[REDACTED]"


class TestHARDataClasses:
    """Tests for the HAR data classes."""

    def test_har_request_defaults(self):
        """Test HARRequest has correct defaults."""
        request = HARRequest(method="GET", url="https://example.com")

        assert request.method == "GET"
        assert request.url == "https://example.com"
        assert request.http_version == "HTTP/1.1"
        assert request.headers == []
        assert request.query_string == []
        assert request.cookies == []
        assert request.post_data == {}
        assert request.body_size == 0
        assert request.headers_size == 0

    def test_har_response_defaults(self):
        """Test HARResponse has correct defaults."""
        response = HARResponse(status=200)

        assert response.status == 200
        assert response.status_text == ""
        assert response.http_version == "HTTP/1.1"
        assert response.headers == []
        assert response.cookies == []
        assert response.content == {}
        assert response.redirect_url == ""
        assert response.headers_size == 0
        assert response.body_size == 0

    def test_har_entry_defaults(self):
        """Test HAREntry has correct defaults."""
        entry = HAREntry()

        assert entry.pageref == ""
        assert entry.started_date_time == ""
        assert entry.time == 0.0
        assert entry.request is None
        assert entry.response is None
        assert entry.cache == {}
        assert entry.timings == {}

    def test_har_entry_to_dict(self):
        """Test HAREntry.to_dict() method."""
        request = HARRequest(method="GET", url="https://example.com")
        response = HARResponse(status=200)

        entry = HAREntry(
            pageref="page_1",
            started_date_time="2024-01-01T00:00:00.000Z",
            time=100.0,
            request=request,
            response=response,
        )

        result = entry.to_dict()

        assert result["pageref"] == "page_1"
        assert result["startedDateTime"] == "2024-01-01T00:00:00.000Z"
        assert result["time"] == 100.0
        assert "request" in result
        assert "response" in result
        assert result["request"]["method"] == "GET"
        assert result["response"]["status"] == 200


class TestHARLoggerRepr:
    """Tests for HARLogger string representation."""

    def test_repr_disabled_no_entries(self):
        """Test __repr__ with disabled logger and no entries."""
        logger = HARLogger()
        repr_str = repr(logger)
        assert "HARLogger" in repr_str
        assert "enabled=False" in repr_str
        assert "entries=0" in repr_str

    def test_repr_enabled_with_entries(self):
        """Test __repr__ with enabled logger and entries."""
        logger = HARLogger(enabled=True)
        logger.add_complete_entry("GET", "https://example.com", response_status=200)
        logger.add_complete_entry("POST", "https://example.com", response_status=201)

        repr_str = repr(logger)
        assert "enabled=True" in repr_str
        assert "entries=2" in repr_str

    def test_len(self):
        """Test __len__ method."""
        logger = HARLogger(enabled=True)

        assert len(logger) == 0

        logger.add_complete_entry("GET", "https://example.com/1", response_status=200)
        assert len(logger) == 1

        logger.add_complete_entry("GET", "https://example.com/2", response_status=200)
        assert len(logger) == 2
