# Rate Limiting Specification

This specification defines the rate limiting requirements for the Archidekt provider, based on reverse-engineered API analysis and known Archidekt API behavior.

## ADDED Requirements

### Requirement: Provider SHALL track request counts

The provider SHALL track the number of requests made to the Archidekt API to enforce rate limits.

**Known rate limit**: Archidekt API allows approximately 60 requests per minute per IP address.

#### Scenario: Track successful requests
- **WHEN** provider makes successful API request
- **THEN** provider increments request counter
- **AND** provider records timestamp of request

#### Scenario: Track failed requests
- **WHEN** provider makes request that fails (network error, API error)
- **THEN** provider still increments request counter (request was made)
- **AND** provider records timestamp of request

---

### Requirement: Provider SHALL implement rate limit checking

The provider SHALL check rate limits before making requests and delay if necessary.

#### Scenario: Check rate limit before request
- **WHEN** user makes API request
- **THEN** provider checks if rate limit would be exceeded
- **AND** if under limit, provider proceeds with request immediately
- **AND** if at or over limit, provider delays request or raises RateLimitError

#### Scenario: Rate limit window tracking
- **WHEN** tracking requests
- **THEN** provider uses 60-second sliding window
- **AND** provider removes requests older than 60 seconds from count

---

### Requirement: Provider SHALL respect Retry-After header

When the API returns HTTP 429 (Too Many Requests), it MAY include a Retry-After header specifying when to retry. The provider SHALL respect this header.

#### Scenario: Respect Retry-After header with seconds
- **WHEN** API returns 429 with `Retry-After: 30` header
- **THEN** provider parses Retry-After as seconds
- **AND** provider waits at least 30 seconds before retrying

#### Scenario: Respect Retry-After header with date
- **WHEN** API returns 429 with `Retry-After: <HTTP-date>` header
- **THEN** provider parses Retry-After as date
- **AND** provider calculates wait time from date difference
- **AND** provider waits until specified time

#### Scenario: Default wait time when Retry-After missing
- **WHEN** API returns 429 without Retry-After header
- **THEN** provider uses default wait time (60 seconds)

---

### Requirement: Provider SHALL provide rate limit status

The provider SHALL expose the current rate limit status to users.

#### Scenario: Get rate limit status
- **WHEN** user calls `get_rate_limit_status()`
- **THEN** provider returns dictionary with rate limit information
- **AND** dictionary includes:
  - `remaining`: Number of requests remaining in current window
  - `reset`: Timestamp when rate limit window resets
  - `limit`: Maximum requests per window (60)
  - `window`: Window duration in seconds (60)

---

### Requirement: Provider SHALL support configurable rate limits

The provider SHALL allow configuration of rate limit parameters through provider initialization.

#### Scenario: Configure custom rate limit
- **WHEN** user initializes provider with custom rate limit
- **THEN** provider uses custom limit instead of default 60

#### Scenario: Configure custom window size
- **WHEN** user initializes provider with custom window size
- **THEN** provider uses custom window size instead of default 60 seconds

---

### Requirement: Provider SHALL implement automatic rate limiting

The provider SHALL automatically delay requests when approaching rate limits, without requiring explicit user intervention.

#### Scenario: Automatic delay when approaching limit
- **WHEN** provider has made 55 requests in last 60 seconds
- **AND** user makes new request
- **THEN** provider delays request by 5 seconds to stay under limit

#### Scenario: No delay when under limit
- **WHEN** provider has made 10 requests in last 60 seconds
- **AND** user makes new request
- **THEN** provider proceeds immediately without delay

---

### Requirement: Provider SHALL implement token bucket algorithm

The provider SHALL use a token bucket or similar algorithm for rate limiting, allowing bursts of requests up to the limit.

#### Scenario: Burst requests allowed
- **WHEN** provider has not made any requests recently
- **AND** user makes 10 rapid requests
- **THEN** all 10 requests succeed (under limit of 60)

#### Scenario: Sustained rate limiting
- **WHEN** provider makes requests at sustained rate of 1 per second
- **THEN** provider allows all requests (60 per minute is sustained rate)

---

### Requirement: Provider SHALL handle rate limit errors gracefully

When the API returns 429, the provider SHALL handle it appropriately.

#### Scenario: Raise RateLimitError on 429
- **WHEN** API returns 429 status code
- **THEN** provider raises `RateLimitError`
- **AND** error includes retry-after information if available

#### Scenario: Automatic retry on 429 with Retry-After
- **WHEN** API returns 429 with Retry-After header
- **AND** provider is configured for automatic retries
- **THEN** provider waits for Retry-After period
- **AND** provider retries request automatically

---

### Requirement: Provider SHALL log rate limit events

The provider SHALL log rate limit related events for debugging.

#### Scenario: Log rate limit approaching
- **WHEN** request count reaches 80% of limit (48 requests in 60 seconds)
- **THEN** provider logs warning message
- **AND** log includes remaining requests and time until reset

#### Scenario: Log rate limit exceeded
- **WHEN** provider receives 429 response
- **THEN** provider logs error message
- **AND** log includes Retry-After information if available

#### Scenario: Log rate limit reset
- **WHEN** rate limit window resets
- **THEN** provider logs debug message
- **AND** log indicates request count has been reset

---

### Requirement: Provider SHALL support per-endpoint rate limiting

The provider MAY implement different rate limits for different endpoint types (e.g., search vs. deck operations).

#### Scenario: Different limits for different endpoints
- **WHEN** provider is configured with endpoint-specific limits
- **THEN** provider tracks requests separately for each endpoint type
- **AND** provider applies appropriate limit for each request

---

### Requirement: Provider SHALL support rate limit sharing across instances

In multi-threaded or async environments, the provider SHALL ensure rate limit tracking is shared across all instances.

#### Scenario: Thread-safe rate limiting
- **WHEN** multiple threads make requests simultaneously
- **THEN** provider uses thread-safe counter for rate limit tracking
- **AND** rate limits are enforced correctly across all threads

#### Scenario: Async-safe rate limiting
- **WHEN** multiple async tasks make requests simultaneously
- **THEN** provider uses async-safe counter for rate limit tracking
- **AND** rate limits are enforced correctly across all tasks
