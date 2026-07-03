## ADDED Requirements

### Requirement: All errors SHALL inherit from PyMTGError
All custom exceptions in the library MUST inherit from the base PyMTGError exception.

#### Scenario: Base error inheritance
- **WHEN** any pymtg error is raised
- **THEN** the error is an instance of PyMTGError

#### Scenario: Catching all pymtg errors
- **WHEN** user executes code in a try/except block catching PyMTGError
- **THEN** all pymtg-related errors are caught

---

### Requirement: PyMTGError SHALL include provider and message
The PyMTGError base exception MUST include provider name and error message as minimum fields.

#### Scenario: Error with provider context
- **WHEN** an error occurs with Scryfall provider
- **THEN** PyMTGError.provider = "scryfall" and PyMTGError.message describes the error

#### Scenario: Generic error creation
- **WHEN** PyMTGError is instantiated
- **THEN** it requires provider and message parameters

---

### Requirement: PyMTGError SHALL include optional details
PyMTGError MUST support optional fields: status_code, details (dict), and any provider-specific information.

#### Scenario: Error with status code
- **WHEN** HTTP error occurs with status code 404
- **THEN** PyMTGError.status_code = 404

#### Scenario: Error with raw response
- **WHEN** provider returns error response
- **THEN** PyMTGError.details contains the raw response for debugging

---

### Requirement: RateLimitError SHALL extend PyMTGError
RateLimitError MUST be a subclass of PyMTGError for rate limit specific errors.

#### Scenario: Rate limit error type
- **WHEN** rate limit is exceeded
- **THEN** system raises RateLimitError which is a PyMTGError

#### Scenario: RateLimitError with retry_after
- **WHEN** provider returns Retry-After header
- **THEN** RateLimitError.retry_after contains the seconds to wait

---

### Requirement: NotFoundError SHALL extend PyMTGError
NotFoundError MUST be a subclass of PyMTGError for resource not found errors.

#### Scenario: Card not found
- **WHEN** a card is not found by ID
- **THEN** system raises NotFoundError with resource_type="card" and resource_id

#### Scenario: Deck not found
- **WHEN** a deck is not found by ID
- **THEN** system raises NotFoundError with resource_type="deck" and resource_id

---

### Requirement: AuthenticationError SHALL extend PyMTGError
AuthenticationError MUST be a subclass of PyMTGError for authentication-related errors.

#### Scenario: Invalid credentials
- **WHEN** authentication fails due to invalid credentials
- **THEN** system raises AuthenticationError with appropriate message

#### Scenario: Expired session
- **WHEN** session has expired
- **THEN** system raises AuthenticationError indicating session expired

---

### Requirement: InvalidQueryError SHALL extend PyMTGError
InvalidQueryError MUST be a subclass of PyMTGError for invalid query errors.

#### Scenario: Invalid syntax
- **WHEN** user provides invalid query syntax
- **THEN** system raises InvalidQueryError with the invalid query string

#### Scenario: Provider-specific message
- **WHEN** provider returns a specific error message
- **THEN** InvalidQueryError.provider_specific_message contains the message

---

### Requirement: APIError SHALL extend PyMTGError
APIError MUST be a subclass of PyMTGError for general API errors.

#### Scenario: 500 server error
- **WHEN** provider returns 500 Internal Server Error
- **THEN** system raises APIError with status_code=500

#### Scenario: Unexpected error
- **WHEN** provider returns unexpected error
- **THEN** system raises APIError with details

---

### Requirement: NetworkError SHALL extend PyMTGError
NetworkError MUST be a subclass of PyMTGError for network-related errors.

#### Scenario: Connection error
- **WHEN** network connection fails
- **THEN** system raises NetworkError

#### Scenario: Timeout error
- **WHEN** request times out
- **THEN** system raises NetworkError with timeout information

---

### Requirement: Providers SHALL use appropriate error types
Each provider MUST raise the most specific error type appropriate for the error condition.

#### Scenario: Card not found
- **WHEN** Scryfall returns 404 for a card lookup
- **THEN** system raises NotFoundError (not APIError or generic exception)

#### Scenario: Rate limited
- **WHEN** Scryfall returns 429
- **THEN** system raises RateLimitError (not APIError)

#### Scenario: Invalid query
- **WHEN** Scryfall returns 400 for invalid query syntax
- **THEN** system raises InvalidQueryError (not APIError)

---

### Requirement: Errors SHALL include actionable messages
All error messages MUST be actionable - they should tell the user what went wrong and how to fix it where possible.

#### Scenario: Clear error message
- **WHEN** rate limit is hit
- **THEN** error message includes "Rate limit exceeded. Wait X seconds before retrying."

#### Scenario: Authentication error message
- **WHEN** authentication fails
- **THEN** error message indicates whether credentials are invalid, session expired, or other specific issue

---

### Requirement: Errors SHALL be logged
When errors occur, they MUST be logged with appropriate severity levels.

#### Scenario: Debug logging for errors
- **WHEN** an error occurs
- **THEN** system logs the error with DEBUG level (or higher based on severity)

#### Scenario: Error logging includes context
- **WHEN** an error is logged
- **THEN** the log includes provider, error type, message, and any relevant context

---

### Requirement: Errors SHALL preserve stack traces
Custom exceptions MUST preserve the original stack trace when wrapping lower-level exceptions.

#### Scenario: Wrapped exception
- **WHEN** PyMTGError wraps a requests.HTTPError
- **THEN** the original stack trace is preserved

#### Scenario: Debugging with stack trace
- **WHEN** user encounters an error
- **THEN** they can see the full call stack to identify where the error originated

---

### Requirement: Errors SHALL be stringifiable
All custom exceptions MUST have clear string representations for debugging and logging.

#### Scenario: String representation
- **WHEN** error is converted to string
- **THEN** it includes provider, error type, and message

#### Scenario: Print error
- **WHEN** user prints an error
- **THEN** they see a clear, readable description of what went wrong

---

### Requirement: Providers SHALL handle HTTP errors gracefully
Providers MUST catch HTTP errors from the underlying HTTP client and convert them to appropriate pymtg errors.

#### Scenario: 404 to NotFoundError
- **WHEN** HTTP client returns 404 response
- **THEN** provider catches it and raises NotFoundError

#### Scenario: 429 to RateLimitError
- **WHEN** HTTP client returns 429 response
- **THEN** provider catches it and raises RateLimitError with retry_after

#### Scenario: 401/403 to AuthenticationError
- **WHEN** HTTP client returns 401 or 403 response
- **THEN** provider catches it and raises AuthenticationError

#### Scenario: 5xx to APIError
- **WHEN** HTTP client returns 5xx response
- **THEN** provider catches it and raises APIError

---

### Requirement: Providers SHALL handle network errors gracefully
Providers MUST catch network-level errors (connection errors, timeouts) and convert them to NetworkError.

#### Scenario: Connection refused
- **WHEN** connection to provider fails
- **THEN** system raises NetworkError

#### Scenario: Request timeout
- **WHEN** request times out
- **THEN** system raises NetworkError with timeout details

---

### Requirement: Providers SHALL fail fast on errors
Providers MUST fail immediately when an error occurs, raising the appropriate exception rather than silently continuing or attempting automatic recovery (except for explicitly configured retry behavior).

#### Scenario: Network failure
- **WHEN** a network request fails
- **THEN** system raises NetworkError immediately

#### Scenario: HTTP error response
- **WHEN** a provider returns a 4xx or 5xx response
- **THEN** system raises the appropriate exception (NotFoundError, AuthenticationError, RateLimitError, APIError) immediately

#### Scenario: Provider unavailable
- **WHEN** a provider is temporarily unavailable
- **THEN** system raises NetworkError or APIError immediately

#### Scenario: Universal Search with provider failure
- **WHEN** Universal Search queries multiple providers and one fails
- **THEN** aggregator catches the error and includes it in the results dict with error information, but does NOT retry automatically

---

### Requirement: Providers SHALL handle JSON decode errors gracefully
Providers MUST catch JSON decode errors and convert them to APIError with helpful context.

#### Scenario: Invalid JSON response
- **WHEN** provider returns non-JSON response
- **THEN** system raises APIError with the raw response body

#### Scenario: Partial JSON response
- **WHEN** provider returns incomplete JSON
- **THEN** system raises APIError with details about what was expected vs received
