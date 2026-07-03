## ADDED Requirements

### API Verification Context
Based on subagent investigation (July 2026), actual rate limits are:
- **Scryfall**: 2 req/s for search endpoints, 10 req/s for all other endpoints
- **Archidekt**: 40-80 req/min (soft throttling)
- **Moxfield (Parse.bot)**: 5 req/min (Free), 20 req/min (Hobby), 100 req/min (Developer)
- **TCGPlayer**: 10 req/s
- **Cardmarket**: 30,000 req/day (Standard), 100,000 req/day (Professional)
- **Deckbox**: N/A (no public API)

### Requirement: Providers SHALL document their rate limits
Each provider MUST have documented rate limits that users can reference.

#### Scenario: Scryfall rate limits
- **WHEN** user checks Scryfall rate limits
- **THEN** system indicates 2 requests/second for search endpoints, 10/second for others

#### Scenario: Archidekt rate limits
- **WHEN** user checks Archidekt rate limits
- **THEN** system indicates ~60 requests/minute (unofficial)

#### Scenario: Moxfield rate limits
- **WHEN** user checks Moxfield rate limits
- **THEN** system indicates ~100 requests/minute (unofficial)

---

### Requirement: Providers SHALL respect rate limits
Each provider MUST track request timing and respect its documented rate limits.

#### Scenario: Rate limit tracking
- **WHEN** user makes requests to a provider
- **THEN** system tracks the timestamp of each request

#### Scenario: Rate limit enforcement
- **WHEN** user would exceed rate limit
- **THEN** system either waits, warns, or raises an error based on configuration

---

### Requirement: Providers SHALL handle 429 responses
When a provider returns HTTP 429 (Too Many Requests), the provider MUST handle it appropriately.

#### Scenario: 429 response with Retry-After
- **WHEN** provider returns 429 with Retry-After header
- **THEN** system raises RateLimitError with retry_after populated

#### Scenario: 429 response without Retry-After
- **WHEN** provider returns 429 without Retry-After header
- **THEN** system raises RateLimitError with retry_after=None

#### Scenario: Temporary ban after repeated 429
- **WHEN** provider temporarily bans the IP after repeated rate limit violations
- **THEN** system raises RateLimitError indicating temporary ban

---

### Requirement: RateLimitError SHALL include retry information
The RateLimitError exception MUST include all available information to help users handle the error.

#### Scenario: Retry-After header
- **WHEN** provider specifies Retry-After: 60
- **THEN** RateLimitError.retry_after = 60

#### Scenario: No Retry-After header
- **WHEN** provider returns 429 without Retry-After
- **THEN** RateLimitError.retry_after = None

---

### Requirement: Providers SHALL log rate limit warnings
When approaching rate limits, providers MUST log warnings to help users understand they are near the limit.

#### Scenario: Approaching rate limit
- **WHEN** user has made 8 of 10 allowed requests in the last second
- **THEN** system logs a warning about approaching rate limit

#### Scenario: Rate limit hit
- **WHEN** user hits rate limit
- **THEN** system logs an error with details

---

### Requirement: Rate limit configuration SHALL be provider-specific
Each provider MUST have its own rate limit configuration that can be customized.

#### Scenario: Custom rate limit
- **WHEN** user wants to be more conservative than default
- **THEN** system allows configuration of custom rate limit values

#### Scenario: Disable rate limiting
- **WHEN** user wants to handle rate limiting themselves
- **THEN** system allows disabling built-in rate limiting

---

### Requirement: Providers SHALL use separate rate limit tracking per instance
Each provider instance MUST track its rate limits separately from other instances.

#### Scenario: Multiple provider instances
- **WHEN** user creates two Scryfall instances
- **THEN** each instance tracks its own rate limit independently

#### Scenario: Shared session
- **WHEN** user wants to share rate limit tracking across instances
- **THEN** system allows configuration to share tracking (future enhancement)

---

### Requirement: Rate limit information SHALL be accessible
Users MUST be able to check the current rate limit status for each provider.

#### Scenario: Check remaining requests
- **WHEN** user calls provider.get_rate_limit_status()
- **THEN** system returns current rate limit status (remaining requests, reset time, etc.)

#### Scenario: Check if rate limited
- **WHEN** user calls provider.is_rate_limited()
- **THEN** system returns True if currently rate limited

---

### Requirement: Bulk operations SHALL respect rate limits
When performing operations that would make multiple requests (bulk card lookup, deck aggregation), the system MUST respect rate limits across all requests.

#### Scenario: Bulk card lookup
- **WHEN** user looks up 100 cards in bulk
- **THEN** system makes requests at a rate that respects provider rate limits

#### Scenario: Deck with many cards
- **WHEN** user retrieves a deck with 200 cards
- **THEN** system fetches all cards while respecting rate limits

---

### Requirement: Rate limit errors SHALL be recoverable
When a RateLimitError is raised, users MUST be able to recover by waiting and retrying.

#### Scenario: Wait and retry
- **WHEN** user catches RateLimitError with retry_after=60
- **THEN** user can wait 60 seconds and retry the operation

#### Scenario: Exponential backoff
- **WHEN** user wants to implement retry logic
- **THEN** system provides utilities for exponential backoff (future enhancement)
