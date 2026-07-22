# API Error Handling Specification

This specification defines the error handling requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR file at `/tmp/archidekt.har`.

## ADDED Requirements

### Requirement: Provider SHALL raise appropriate exceptions for HTTP errors

The provider SHALL map HTTP status codes to appropriate pymtg exception types for consistent error handling across all providers.

#### Scenario: HTTP 401 Unauthorized
- **WHEN** API returns 401 status code
- **THEN** provider raises `AuthenticationError`
- **AND** error message indicates authentication failure
- **AND** error includes provider name "archidekt"

#### Scenario: HTTP 403 Forbidden
- **WHEN** API returns 403 status code
- **THEN** provider raises `AuthenticationError`
- **AND** error message indicates permission denied

#### Scenario: HTTP 404 Not Found
- **WHEN** API returns 404 status code for card request
- **THEN** provider raises `NotFoundError`
- **AND** error includes resource type "card" and resource ID

#### Scenario: HTTP 404 Not Found for deck
- **WHEN** API returns 404 status code for deck request
- **THEN** provider raises `NotFoundError`
- **AND** error includes resource type "deck" and resource ID

#### Scenario: HTTP 429 Too Many Requests
- **WHEN** API returns 429 status code
- **THEN** provider raises `RateLimitError`
- **AND** error includes retry-after information if available in headers

#### Scenario: HTTP 500 Internal Server Error
- **WHEN** API returns 500 status code
- **THEN** provider raises `APIError`
- **AND** error message indicates server error

---

### Requirement: Provider SHALL parse error response bodies

The provider SHALL extract and include error details from the response body when available.

**Evidence from HAR file**: All error responses include a JSON body with error details.

#### Scenario: Parse error detail from response
- **WHEN** API returns 400 with JSON body `{"detail": "Invalid credentials"}`
- **THEN** provider extracts "Invalid credentials" from response
- **AND** provider includes detail in error message

#### Scenario: Handle non-JSON error response
- **WHEN** API returns error with non-JSON body
- **THEN** provider attempts to extract error message from response text
- **AND** provider includes response text in error message
- **AND** provider does not raise exception for failed JSON parsing

---

### Requirement: Provider SHALL include provider context in errors

All exceptions raised by the provider SHALL include the provider name for context.

#### Scenario: Authentication error includes provider name
- **WHEN** authentication fails
- **THEN** raised `AuthenticationError` includes `provider="archidekt"`

#### Scenario: Not found error includes provider name
- **WHEN** card not found
- **THEN** raised `NotFoundError` includes `provider="archidekt"`

#### Scenario: Rate limit error includes provider name
- **WHEN** rate limit exceeded
- **THEN** raised `RateLimitError` includes `provider="archidekt"`

---

### Requirement: Provider SHALL handle network errors

The provider SHALL properly handle network-level errors (timeouts, connection errors) and raise appropriate exceptions.

#### Scenario: Connection timeout
- **WHEN** request times out
- **THEN** provider raises `NetworkError`
- **AND** error includes original exception

#### Scenario: Connection refused
- **WHEN** connection to API is refused
- **THEN** provider raises `NetworkError`
- **AND** error includes original exception

#### Scenario: DNS resolution failure
- **WHEN** DNS resolution fails
- **THEN** provider raises `NetworkError`
- **AND** error includes original exception

---

### Requirement: Provider SHALL handle invalid response data

The provider SHALL handle cases where the API returns valid HTTP status but malformed or unexpected data.

#### Scenario: Invalid JSON response
- **WHEN** API returns 200 with invalid JSON
- **THEN** provider attempts to parse JSON
- **AND** if parsing fails, provider raises `APIError` with parsing error details

#### Scenario: Missing required fields in response
- **WHEN** API returns 200 but response missing required field (e.g., card id)
- **THEN** provider raises `APIError` with message about missing field

#### Scenario: Unexpected response structure
- **WHEN** API returns 200 with unexpected response structure
- **THEN** provider attempts to parse what it can
- **AND** provider raises `APIError` if critical fields are missing

---

### Requirement: Provider SHALL create Archidekt-specific exception classes

The provider SHALL define Archidekt-specific exception classes that inherit from the base pymtg exceptions for better error identification.

#### Scenario: ArchidektAuthenticationError
- **WHEN** authentication-specific error occurs
- **THEN** provider raises `ArchidektAuthenticationError` (subclass of `AuthenticationError`)

#### Scenario: ArchidektNotFoundError
- **WHEN** resource not found error occurs
- **THEN** provider raises `ArchidektNotFoundError` (subclass of `NotFoundError`)

#### Scenario: ArchidektRateLimitError
- **WHEN** rate limit error occurs
- **THEN** provider raises `ArchidektRateLimitError` (subclass of `RateLimitError`)

#### Scenario: ArchidektAPIError
- **WHEN** general API error occurs
- **THEN** provider raises `ArchidektAPIError` (subclass of `APIError`)

---

### Requirement: Provider SHALL log errors appropriately

The provider SHALL log errors with appropriate severity levels for debugging.

#### Scenario: Log authentication errors
- **WHEN** authentication fails
- **THEN** provider logs error with details (without credentials)
- **AND** log level is ERROR

#### Scenario: Log validation errors
- **WHEN** validation error occurs
- **THEN** provider logs error with field and message
- **AND** log level is ERROR

#### Scenario: Log network errors
- **WHEN** network error occurs
- **THEN** provider logs error with URL and error details
- **AND** log level is ERROR

#### Scenario: Log API errors
- **WHEN** API returns error status
- **THEN** provider logs error with status code and response details
- **AND** log level is ERROR

---

### Requirement: Provider SHALL sanitize error messages

The provider SHALL ensure that error messages do not contain sensitive information like credentials or tokens.

#### Scenario: Authentication error without credentials
- **WHEN** authentication fails
- **THEN** error message does not include username or password
- **AND** error message does not include token values

#### Scenario: Request logging without sensitive data
- **WHEN** request fails and is logged
- **THEN** log does not include Authorization header value
- **AND** log does not include any token values

---

### Requirement: Provider SHALL support retry for transient errors

The provider MAY support automatic retry for transient errors (network timeouts, rate limits).

#### Scenario: Retry on network timeout
- **WHEN** request times out
- **AND** provider is configured for retries
- **THEN** provider retries request up to configured maximum

#### Scenario: No retry on authentication error
- **WHEN** authentication error occurs
- **THEN** provider does not retry (credentials are invalid)
- **AND** error is raised immediately

#### Scenario: Retry with exponential backoff
- **WHEN** transient error occurs and retry is configured
- **THEN** provider waits increasing time between retries
- **AND** provider respects Retry-After header for 429 errors
