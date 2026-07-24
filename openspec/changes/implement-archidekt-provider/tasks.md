# Implementation Tasks for Archidekt Provider

This task list breaks down the complete implementation of the Archidekt provider based on reverse-engineered API analysis from `/tmp/archidekt.har`.

## 0. Prerequisites and Setup

- [x] 0.1 Verify HAR file analysis is complete and documented
- [x] 0.2 Review existing pymtg architecture (base.py, models, other providers)
- [x] 0.3 Verify uv is installed and available in PATH
- [x] 0.4 Create feature branch: `git checkout -b feat/archidekt-jwt-provider`
- [x] 0.5 Run `uv sync` to ensure dependencies are up to date
- [x] 0.6 Verify existing tests pass: `uv run python -m pytest tests/ -x`

## 1. Create JWT Authentication Handler

This phase implements the JWT authentication handler that replaces SessionAuthHandler for Archidekt.

- [x] 1.1 Create `pymtg/auth/jwt.py` with Google-style docstrings
- [x] 1.2 Implement `JWTAuthHandler` class inheriting from `BaseAuthHandler`
  - [x] 1.2.1 Add `__init__` method accepting base_url and login_endpoint
  - [x] 1.2.2 Add `authenticate(username, password)` method that POSTs to `/api/rest-auth/login/`
  - [x] 1.2.3 Add `get_auth_header()` method returning `{"Authorization": "JWT <token>"}`
  - [x] 1.2.4 Add `is_authenticated()` method checking if access_token is present
  - [x] 1.2.5 Add `clear_auth()` method to clear tokens from memory
  - [x] 1.2.6 Add `refresh()` method to re-authenticate using stored credentials
- [x] 1.3 Add secure credential handling
  - [x] 1.3.1 Implement `__getstate__` to exclude credentials from pickle
  - [x] 1.3.2 Clear password from memory immediately after authentication
  - [x] 1.3.3 Store tokens in memory only (no disk persistence)
- [x] 1.4 Add unit tests for JWTAuthHandler
  - [x] 1.4.1 Test successful authentication with valid credentials
  - [x] 1.4.2 Test authentication failure with invalid credentials
  - [x] 1.4.3 Test authentication with network error
  - [x] 1.4.4 Test is_authenticated() returns True after auth
  - [x] 1.4.5 Test is_authenticated() returns False before auth
  - [x] 1.4.6 Test clear_auth() removes tokens
  - [x] 1.4.7 Test get_auth_header() returns correct format
  - [x] 1.4.8 Test get_auth_header() returns empty dict when not authenticated
  - [x] 1.4.9 Test `__getstate__` excludes credentials
- [x] 1.5 Verify JWTAuthHandler tests pass
- [x] 1.6 Update `pymtg/auth/__init__.py` to export JWTAuthHandler

## 2. Create Archidekt-Specific Exceptions

This phase creates Archidekt-specific exception classes for proper error handling.

- [x] 2.1 Create `pymtg/providers/archidekt/exceptions.py` (or add to existing file)
- [x] 2.2 Implement exception hierarchy
  - [x] 2.2.1 `ArchidektError` (base exception, inherits from Exception)
  - [x] 2.2.2 `ArchidektAuthenticationError` (inherits from AuthenticationError)
  - [x] 2.2.3 `ArchidektNotFoundError` (inherits from NotFoundError)
  - [x] 2.2.4 `ArchidektRateLimitError` (inherits from RateLimitError)
  - [x] 2.2.5 `ArchidektAPIError` (inherits from APIError)
  - [x] 2.2.6 `ArchidektValidationError` (inherits from InvalidQueryError)
- [x] 2.3 Add docstrings to all exception classes
- [x] 2.4 Add unit tests for exceptions
  - [x] 2.4.1 Test exception hierarchy (isinstance checks)
  - [x] 2.4.2 Test exception messages are properly set
  - [x] 2.4.3 Test exception attributes (provider, status_code, etc.)
- [x] 2.5 Verify exception tests pass

## 3. Create Rate Limiter

This phase implements the rate limiting functionality for Archidekt's ~60 requests/minute limit.

- [x] 3.1 Create `pymtg/utils/rate_limiter.py` (or add to existing utils)
- [x] 3.2 Implement `RateLimiter` class
  - [x] 3.2.1 Add `__init__` with max_requests (default 60) and window_seconds (default 60)
  - [x] 3.2.2 Add `wait_if_needed()` method that checks rate limit and waits if necessary
  - [x] 3.2.3 Add `get_status()` method returning current rate limit status
  - [x] 3.2.4 Use thread-safe data structure (deque with lock)
- [x] 3.3 Add docstrings
- [x] 3.4 Add unit tests for RateLimiter
  - [x] 3.4.1 Test first request allowed immediately
  - [x] 3.4.2 Test 60th request in window is allowed
  - [x] 3.4.3 Test 61st request in window causes delay
  - [x] 3.4.4 Test old requests are removed from window
  - [x] 3.4.5 Test get_status() returns correct information
- [x] 3.5 Verify RateLimiter tests pass

## 4. Create HAR Logging Utility

This phase implements the HAR logging functionality for debugging.

- [x] 4.1 Create `pymtg/utils/har_logger.py`
- [x] 4.2 Implement `HARLogger` class
  - [x] 4.2.1 Add `__init__` to initialize entries list
  - [x] 4.2.2 Add `log_request()` method to capture request details
  - [x] 4.2.3 Add `log_response()` method to capture response details
  - [x] 4.2.4 Add `enable()` and `disable()` methods
  - [x] 4.2.5 Add `export()` method to write to file
  - [x] 4.2.6 Add `clear()` method to reset entries
  - [x] 4.2.7 Implement sanitization for sensitive data (Authorization header, credentials)
- [x] 4.3 Add docstrings
- [x] 4.4 Add unit tests for HARLogger
  - [x] 4.4.1 Test enable/disable functionality
  - [x] 4.4.2 Test request logging captures all fields
  - [x] 4.4.3 Test response logging captures all fields
  - [x] 4.4.4 Test export creates valid HAR file
  - [x] 4.4.5 Test sensitive data is sanitized in export
  - [x] 4.4.6 Test clear() removes all entries
- [x] 4.5 Verify HARLogger tests pass

## 5. Update Archidekt Provider Implementation

This phase completely rewrites the Archidekt provider with the correct JWT authentication and API endpoints.

### 5.1 Provider Setup and Configuration

- [x] 5.1.1 Update `pymtg/providers/archidekt.py` to use JWT authentication
- [x] 5.1.2 Change base_url from `https://archidekt.com` to `https://archidekt.com/api/`
- [x] 5.1.3 Replace SessionAuthHandler with JWTAuthHandler
- [x] 5.1.4 Update `__init__` to accept username/password and authenticate on initialization
- [x] 5.1.5 Add `_initialize()` method for provider-specific setup
- [x] 5.1.6 Add `authenticate(username, password)` public method
- [x] 5.1.7 Add `is_authenticated()` method
- [x] 5.1.8 Add `clear_auth()` or `logout()` method
- [x] 5.1.9 Add HAR logging support methods (enable_har_logging, disable_har_logging, export_har)
- [x] 5.1.10 Add rate limiter instance

### 5.2 Card Search Implementation

- [x] 5.2.1 Implement `search()` method with generic parameters
- [x] 5.2.2 Implement `_build_search_params()` helper to map generic params to Archidekt params
- [x] 5.2.3 Implement `_parse_card()` method to convert Archidekt response to Card model
  - [x] 5.2.3.1 Parse nested oracleCard object
  - [x] 5.2.3.2 Parse edition information
  - [x] 5.2.3.3 Parse prices from various sources
  - [x] 5.2.3.4 Handle missing/null fields gracefully
- [x] 5.2.4 Implement `search_syntax()` method for Archidekt-specific queries
- [x] 5.2.5 Add support for pagination in search results

### 5.3 Card Retrieval Implementation

- [x] 5.3.1 Implement `get_card(card_id)` method
- [x] 5.3.2 Handle card ID as string (Archidekt uses integer IDs)
- [x] 5.3.3 Use same `_parse_card()` for consistency

### 5.4 Deck Management Implementation

- [x] 5.4.1 Implement `get_deck(deck_id)` method
- [x] 5.4.2 Implement `get_user_decks(user_id=None)` method
- [x] 5.4.3 Implement `create_deck(name, format, **kwargs)` method
  - [x] 5.4.3.1 Map Format enum to Archidekt format ID (3 = Commander, etc.)
  - [x] 5.4.3.2 Include required fields: name, deckFormat, game, parent_folder
  - [x] 5.4.3.3 Support optional fields: description, private, unlisted, etc.
  - [x] 5.4.3.4 Parse response into Deck model
- [x] 5.4.4 Implement `_parse_deck()` method to convert Archidekt response to Deck model
  - [x] 5.4.4.1 Parse owner information
  - [x] 5.4.4.2 Parse colors object into color identity
  - [x] 5.4.4.3 Parse timestamps (createdAt, updatedAt)
  - [x] 5.4.4.4 Parse cards if included in response

### 5.5 Deck Card Management Implementation

- [x] 5.5.1 Implement `add_card_to_deck()` method
  - [x] 5.5.1.1 Support adding by card ID
  - [x] 5.5.1.2 Support adding by card name (resolve via search)
  - [x] 5.5.1.3 Generate unique patchId for each operation
  - [x] 5.5.1.4 Track deckRelationId from response
  - [x] 5.5.1.5 Support quantity parameter
  - [x] 5.5.1.6 Support foil parameter (maps to modifier: "Foil")
  - [x] 5.5.1.7 Support categories parameter
- [x] 5.5.2 Implement `remove_card_from_deck()` method
  - [x] 5.5.2.1 Require deckRelationId from previous add
  - [x] 5.5.2.2 Support partial quantity removal
- [x] 5.5.3 Implement `modify_card_in_deck()` method
  - [x] 5.5.3.1 Require deckRelationId
  - [x] 5.5.3.2 Support changing quantity
  - [x] 5.5.3.3 Support changing modifier (Normal/Foil)
- [x] 5.5.4 Store deckRelationId mapping (for now, in-memory dict keyed by (deck_id, card_id))

### 5.6 Iteration Support

- [x] 5.6.1 Implement `iter_search()` method for paginated iteration
- [x] 5.6.2 Handle pagination using next/previous URLs or page numbers

### 5.7 Error Handling

- [x] 5.7.1 Override `_handle_response()` to map HTTP status codes to Archidekt exceptions
  - [x] 5.7.1.1 Map 401 to ArchidektAuthenticationError
  - [x] 5.7.1.2 Map 403 to ArchidektAuthenticationError
  - [x] 5.7.1.3 Map 404 to ArchidektNotFoundError
  - [x] 5.7.1.4 Map 429 to ArchidektRateLimitError
  - [x] 5.7.1.5 Map 500 to ArchidektAPIError
- [x] 5.7.2 Add validation for required parameters
  - [x] 5.7.2.1 Validate deck_id is provided for deck operations
  - [x] 5.7.2.2 Validate card_id or card_name is provided for card operations
  - [x] 5.7.2.3 Validate authentication before authenticated operations

### 5.8 Authentication Checks

- [x] 5.8.1 Add authentication check before all authenticated operations
- [x] 5.8.2 Raise ArchidektAuthenticationError if not authenticated

### 5.9 Security

- [x] 5.9.1 Implement `__getstate__` to exclude credentials from pickle
- [x] 5.9.2 Clear credentials from memory after use
- [x] 5.9.3 Ensure tokens are not logged or exposed in error messages

### 5.10 Docstrings and Type Annotations

- [x] 5.10.1 Add Google-style docstrings to all public methods
- [x] 5.10.2 Add type annotations to all method parameters and return values
- [x] 5.10.3 Add module-level docstring to archidekt.py
- [x] 5.10.4 Add class docstring to Archidekt class

## 6. Create Tests

This phase creates extensive tests using mock responses based on HAR file data.

### 6.1 Test Setup

- [x] 6.1.1 Create `tests/providers/test_archidekt.py`
- [x] 6.1.2 Create mock response data from HAR file (extract into `tests/fixtures/archidekt/`)
- [x] 6.1.3 Set up pytest fixtures for provider instances
- [x] 6.1.4 Create mock HTTP client that returns HAR-based responses

### 6.2 Authentication Tests

- [x] 6.2.1 Test successful JWT authentication
- [x] 6.2.2 Test authentication with invalid credentials
- [x] 6.2.3 Test authentication with network error
- [x] 6.2.4 Test is_authenticated() before auth
- [x] 6.2.5 Test is_authenticated() after auth
- [x] 6.2.6 Test is_authenticated() after clear_auth()
- [x] 6.2.7 Test auth header is included in authenticated requests
- [x] 6.2.8 Test auth header is not included in unauthenticated requests

### 6.3 Card Search Tests

- [x] 6.3.1 Test search by name (nameSearch parameter)
- [x] 6.3.2 Test search by exact name (name parameter)
- [x] 6.3.3 Test search with color filter
- [x] 6.3.4 Test search with color identity filter
- [x] 6.3.5 Test search with rarity filter
- [x] 6.3.6 Test search with format legality filter
- [x] 6.3.7 Test search with oracleCardIds parameter
- [x] 6.3.8 Test search with pagination (page parameter)
- [x] 6.3.9 Test search returns empty list when no results
- [x] 6.3.10 Test search with generic parameters from BaseProvider
- [x] 6.3.11 Test search_syntax with raw query string
- [x] 6.3.12 Test card parsing handles nested oracleCard correctly
- [x] 6.3.13 Test card parsing handles nested edition correctly
- [x] 6.3.14 Test card parsing handles prices correctly
- [x] 6.3.15 Test card parsing handles missing fields gracefully

### 6.4 Deck Management Tests

- [x] 6.4.1 Test get_deck() with valid deck ID
- [x] 6.4.2 Test get_deck() with invalid deck ID (404)
- [x] 6.4.3 Test get_deck() without authentication
- [x] 6.4.4 Test create_deck() with required parameters
- [x] 6.4.5 Test create_deck() with all optional parameters
- [x] 6.4.6 Test create_deck() without authentication
- [x] 6.4.7 Test deck parsing handles owner information correctly
- [x] 6.4.8 Test deck parsing handles colors object correctly
- [x] 6.4.9 Test deck parsing handles timestamps correctly
- [x] 6.4.10 Test get_user_decks() returns list of decks
- [x] 6.4.11 Test get_user_decks() with specific user_id

### 6.5 Deck Card Management Tests

- [x] 6.5.1 Test add_card_to_deck() by card ID
- [x] 6.5.2 Test add_card_to_deck() by card name
- [x] 6.5.3 Test add_card_to_deck() with quantity > 1
- [x] 6.5.4 Test add_card_to_deck() with foil=True
- [x] 6.5.5 Test add_card_to_deck() with categories
- [x] 6.5.6 Test add_card_to_deck() without authentication
- [x] 6.5.7 Test remove_card_from_deck() with deckRelationId
- [x] 6.5.8 Test remove_card_from_deck() without deckRelationId
- [x] 6.5.9 Test modify_card_in_deck() to change quantity
- [x] 6.5.10 Test modify_card_in_deck() to change modifier
- [x] 6.5.11 Test multiple card operations in single request
- [x] 6.5.12 Test add_card_to_deck() returns updated deck

### 6.6 Error Handling Tests

- [x] 6.6.1 Test 401 raises ArchidektAuthenticationError
- [x] 6.6.2 Test 403 raises ArchidektAuthenticationError
- [x] 6.6.3 Test 404 raises ArchidektNotFoundError
- [x] 6.6.4 Test 429 raises ArchidektRateLimitError
- [x] 6.6.5 Test 500 raises ArchidektAPIError
- [x] 6.6.6 Test network error raises NetworkError
- [x] 6.6.7 Test invalid JSON response raises APIError
- [x] 6.6.8 Test missing required parameter raises ValidationError
- [x] 6.6.9 Test unauthenticated operation raises AuthenticationError

### 6.7 HAR Logging Tests

- [x] 6.7.1 Test enable_har_logging() starts capture
- [x] 6.7.2 Test disable_har_logging() stops capture
- [x] 6.7.3 Test HAR captures request method and URL
- [x] 6.7.4 Test HAR captures request headers (sanitized)
- [x] 6.7.5 Test HAR captures request body (sanitized)
- [x] 6.7.6 Test HAR captures response status
- [x] 6.7.7 Test HAR captures response headers
- [x] 6.7.8 Test HAR captures response body
- [x] 6.7.9 Test export_har() creates valid HAR file
- [x] 6.7.10 Test HAR file contains correct structure (version 1.2)
- [x] 6.7.11 Test sensitive data is sanitized in HAR export

### 6.8 Rate Limiting Tests

- [x] 6.8.1 Test requests under limit proceed immediately
- [x] 6.8.2 Test requests at limit are delayed
- [x] 6.8.3 Test old requests are removed from window
- [x] 6.8.4 Test get_rate_limit_status() returns correct information

### 6.9 Integration Tests

- [x] 6.9.1 Test complete workflow: auth, search, create deck, add cards, get deck
- [x] 6.9.2 Test HAR logging captures complete workflow
- [x] 6.9.3 Test rate limiting during multiple requests

## 7. Update Documentation

### 7.1 Provider Documentation

- [x] 7.1.1 Create/update `docs/providers/archidekt.md`
- [x] 7.1.2 Add overview of Archidekt provider
- [x] 7.1.3 Add authentication section with JWT example
- [x] 7.1.4 Add usage examples for all major operations
- [x] 7.1.5 Document all public methods with examples
- [x] 7.1.6 Add error handling examples
- [x] 7.1.7 Add HAR logging documentation
- [x] 7.1.8 Add rate limiting documentation
- [x] 7.1.9 Document limitations and known issues

### 7.2 API Reference

- [x] 7.2.1 Document all public methods in provider
- [x] 7.2.2 Document all parameters and return types
- [x] 7.2.3 Document all raised exceptions
- [x] 7.2.4 Document data models returned

### 7.3 README Updates

- [x] 7.3.1 Update provider status table in README.md
- [x] 7.3.2 Mark Archidekt as "Implemented" with JWT auth
- [x] 7.3.3 Update feature list if needed

### 7.4 Code Documentation

- [x] 7.4.1 Verify all methods have Google-style docstrings
- [x] 7.4.2 Verify all type annotations are present
- [x] 7.4.3 Verify all parameters are documented
- [x] 7.4.4 Verify all return values are documented
- [x] 7.4.5 Verify all exceptions are documented

## 8. Final Verification

### 8.1 Code Quality Checks

- [x] 8.1.1 Run `uv run ruff check pymtg/providers/archidekt.py` - no errors
- [x] 8.1.2 Run `uv run ruff check pymtg/auth/jwt.py` - no errors
- [x] 8.1.3 Run `uv run ruff check tests/providers/test_archidekt.py` - no errors
- [x] 8.1.4 Run `uv run pyright pymtg/providers/archidekt.py` - no type errors
- [x] 8.1.5 Run `uv run pyright pymtg/auth/jwt.py` - no type errors
- [x] 8.1.6 Run `uv run black --check pymtg/providers/archidekt.py` - no formatting issues
- [x] 8.1.7 Run `uv run black --check pymtg/auth/jwt.py` - no formatting issues

### 8.2 Test Execution

- [x] 8.2.1 Run all Archidekt tests: `uv run python -m pytest tests/providers/test_archidekt.py -v`
- [x] 8.2.2 Verify all tests pass (100% pass rate)
- [x] 8.2.3 Run tests with coverage: `uv run python -m pytest tests/providers/test_archidekt.py --cov=pymtg.providers.archidekt --cov-report=term`
- [x] 8.2.4 Verify coverage is at least 90%
- [x] 8.2.5 Run full test suite to ensure no regressions: `uv run python -m pytest tests/ -x`

### 8.3 Integration Testing

- [x] 8.3.1 Test with mock credentials to verify flow
- [x] 8.3.2 Verify HAR export produces valid file
- [x] 8.3.3 Verify rate limiting works as expected
- [x] 8.3.4 Verify all parsing methods handle HAR file data correctly

### 8.4 Documentation Verification

- [x] 8.4.1 Verify all documentation files have proper structure
- [x] 8.4.2 Verify documentation examples are correct
- [x] 8.4.3 Verify documentation links work
- [x] 8.4.4 Verify documentation has no typos or errors

## 9. Cleanup and Finalization

- [x] 9.1 Remove any temporary files or debug code
- [x] 9.2 Update CHANGELOG.md with new features and breaking changes
- [x] 9.3 Update .gitignore if any new file patterns added
- [x] 9.4 Review all changes with `git diff`
- [x] 9.5 Create commit with descriptive message following conventional commits
- [x] 9.6 Push branch to remote: `git push origin feat/archidekt-jwt-provider`
- [x] 9.7 Create pull request with link to this change proposal
- [x] 9.8 Mark all tasks in this file as complete

## 10. Post-Implementation (Optional)

These tasks are nice-to-have but not required for initial implementation.

- [x] 10.1 Implement automatic token refresh using refresh_token
- [x] 10.2 Add support for WebSocket collaborative editing (seen in HAR)
- [x] 10.3 Add support for user collections (not just decks)
- [x] 10.4 Add support for folder management
- [x] 10.5 Add support for deck primers and descriptions
- [x] 10.6 Add caching layer for frequently accessed data
- [x] 10.7 Implement async context manager support
- [x] 10.8 Add performance benchmarks
- [x] 10.9 Create integration tests with real API (if credentials available)
