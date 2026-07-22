# HAR Logging Specification

This specification defines the HAR (HTTP Archive) logging requirements for the Archidekt provider, enabling debugging and API traffic analysis based on the provided HAR file at `/tmp/archidekt.har`.

## ADDED Requirements

### Requirement: Provider SHALL support optional HAR logging

The provider SHALL allow users to enable HAR logging to capture all HTTP requests and responses for debugging purposes.

#### Scenario: Enable HAR logging
- **WHEN** user enables HAR logging via provider method
- **THEN** provider starts capturing all subsequent requests and responses
- **AND** provider stores request/response data in memory

#### Scenario: Disable HAR logging
- **WHEN** user disables HAR logging
- **THEN** provider stops capturing new requests
- **AND** provider retains previously captured data

---

### Requirement: Provider SHALL capture complete request information

When HAR logging is enabled, the provider SHALL capture complete request details for each HTTP request.

**Reference**: HAR file format version 1.2 as seen in the provided file.

#### Scenario: Capture request method and URL
- **WHEN** HAR logging is enabled and provider makes request
- **THEN** provider captures request method (GET, POST, PATCH, etc.)
- **AND** provider captures full request URL including query parameters

#### Scenario: Capture request headers
- **WHEN** HAR logging is enabled and provider makes request
- **THEN** provider captures all request headers
- **AND** provider sanitizes Authorization header value (replaces token with placeholder)

#### Scenario: Capture request body for POST/PATCH
- **WHEN** HAR logging is enabled and provider makes POST or PATCH request
- **THEN** provider captures request body content
- **AND** provider captures Content-Type header
- **AND** provider sanitizes sensitive data in body (credentials, tokens)

#### Scenario: Capture query parameters
- **WHEN** HAR logging is enabled and provider makes request with query parameters
- **THEN** provider captures all query parameters
- **AND** provider preserves parameter values

---

### Requirement: Provider SHALL capture complete response information

When HAR logging is enabled, the provider SHALL capture complete response details for each HTTP response.

#### Scenario: Capture response status
- **WHEN** HAR logging is enabled and provider receives response
- **THEN** provider captures HTTP status code
- **AND** provider captures status text/reason phrase

#### Scenario: Capture response headers
- **WHEN** HAR logging is enabled and provider receives response
- **THEN** provider captures all response headers
- **AND** provider captures Content-Type, Content-Length, etc.

#### Scenario: Capture response body
- **WHEN** HAR logging is enabled and provider receives response
- **THEN** provider captures response body content
- **AND** provider records body size in bytes

---

### Requirement: Provider SHALL generate valid HAR file format

The provider SHALL generate HAR files that conform to the HAR 1.2 specification.

**Reference**: The provided HAR file uses version 1.2 and contains:
- `log` object with `version`, `creator`, `entries` array
- Each entry has `request`, `response`, `startedDateTime`, `time` fields

#### Scenario: Generate HAR file structure
- **WHEN** user exports HAR data
- **THEN** provider generates file with structure:
  ```json
  {
    "log": {
      "version": "1.2",
      "creator": {
        "name": "pymtg Archidekt Provider",
        "version": "<pymtg version>"
      },
      "entries": [...]
    }
  }
  ```

#### Scenario: Generate entry structure
- **WHEN** provider exports HAR entry
- **THEN** each entry contains:
  - `request`: Object with method, url, httpVersion, headers, queryString, etc.
  - `response`: Object with status, statusText, httpVersion, headers, content, etc.
  - `startedDateTime`: ISO 8601 timestamp
  - `time`: Time taken in milliseconds

---

### Requirement: Provider SHALL export HAR data to file

The provider SHALL allow users to export captured HAR data to a file.

#### Scenario: Export HAR to file
- **WHEN** user calls export method with filename
- **THEN** provider writes HAR JSON to specified file
- **AND** provider uses pretty-print formatting for readability
- **AND** provider includes all captured entries

#### Scenario: Export empty HAR
- **WHEN** user exports HAR before making any requests
- **THEN** provider creates file with empty entries array

---

### Requirement: Provider SHALL sanitize sensitive data in HAR output

The provider SHALL ensure that HAR files do not contain sensitive credentials or tokens.

#### Scenario: Sanitize Authorization header
- **WHEN** HAR logging captures request with Authorization header
- **THEN** provider replaces JWT token value with placeholder like "JWT <redacted>"
- **AND** provider preserves header name

#### Scenario: Sanitize request body with credentials
- **WHEN** HAR logging captures login request with username/password
- **THEN** provider replaces password value with placeholder
- **AND** provider may replace username with placeholder or keep it

#### Scenario: Sanitize session cookies
- **WHEN** HAR logging captures request with cookies
- **THEN** provider replaces cookie values with placeholders
- **AND** provider preserves cookie names

---

### Requirement: Provider SHALL timestamp all entries

The provider SHALL include accurate timestamps for all HAR entries.

#### Scenario: Timestamp requests
- **WHEN** HAR logging captures request
- **THEN** provider records `startedDateTime` as ISO 8601 string
- **AND** timestamp is in UTC with 'Z' suffix

#### Scenario: Timestamp responses
- **WHEN** HAR logging captures response
- **THEN** provider calculates `time` field as milliseconds between request start and response end

---

### Requirement: Provider SHALL support context manager for HAR logging

The provider SHALL support using HAR logging as a context manager for scoped logging.

#### Scenario: Use HAR logging as context manager
- **WHEN** user uses provider as context manager with HAR logging enabled
- **THEN** HAR logging is automatically enabled on enter
- **AND** HAR logging is automatically disabled on exit (but data is preserved)
- **AND** user can export captured data after context exits

---

### Requirement: Provider SHALL clear HAR data after export

The provider MAY clear captured HAR data after export to free memory, or may retain it for multiple exports.

#### Scenario: Clear HAR data after export
- **WHEN** user exports HAR data
- **AND** provider is configured to clear after export
- **THEN** provider clears captured entries from memory
- **AND** subsequent export would be empty

#### Scenario: Retain HAR data after export
- **WHEN** user exports HAR data
- **AND** provider is configured to retain after export
- **THEN** provider keeps captured entries in memory
- **AND** subsequent export includes all entries

---

### Requirement: Provider SHALL handle HAR logging with authentication

The provider SHALL properly handle HAR logging for both authenticated and unauthenticated requests.

#### Scenario: HAR logging with authenticated requests
- **WHEN** HAR logging is enabled and user makes authenticated request
- **THEN** provider captures request with sanitized Authorization header
- **AND** provider captures response with full data

#### Scenario: HAR logging with unauthenticated requests
- **WHEN** HAR logging is enabled and user makes unauthenticated request
- **THEN** provider captures request without Authorization header
- **AND** provider captures response with full data
