# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-02

### Added

- **Core Infrastructure**:
  - Project structure with `pymtg/` package containing `models/`, `providers/`, `auth/`, `search/`, `utils/` subpackages
  - `py.typed` marker for IDE type hint support
  - Basic logging configuration
  - Configuration classes in `pymtg/config.py`

- **Base Classes and Utilities**:
  - `PyMTGBaseModel` base class for all models (extends Pydantic BaseModel)
  - Full exception hierarchy: `PyMTGError`, `RateLimitError`, `NotFoundError`, `AuthenticationError`, `InvalidQueryError`, `APIError`, `NetworkError`
  - `HTTPClient` with User-Agent header handling and timeout management
  - Rate limiting utilities (`RateLimiter` class)
  - Retry utilities with exponential backoff

- **Enums and Types**:
  - `Color` enum (W, U, B, R, G, COLORLESS) with `full_name` property and `from_full_name` classmethod
  - `Rarity` enum (COMMON, UNCOMMON, RARE, MYTHIC, SPECIAL, BONUS)
  - `Format` enum (STANDARD, MODERN, LEGACY, VINTAGE, COMMANDER, PAUPER, etc.)
  - `Board` enum (MAIN, SIDEBOARD, COMMANDER, MAYBEBOARD)
  - `SetType` enum (CORE, EXPANSION, REPRINT, etc.)

- **Normalized Data Models**:
  - `Card` model with all core fields from specification
  - `CardFace` model for multi-faced cards
  - `DeckCard` model (card: Card, count: int, board: Board)
  - `Deck` model with cards, metadata, and source fields
  - `Set` model for set information
  - Provider-specific pricing models: `ScryfallPricing`, `TCGPlayerPricing`, `CardmarketPricing`, `DeckboxPricing`
  - Main `Pricing` model containing all provider-specific models
  - Helper methods on Card model (is_multicolor, is_white, is_blue, etc.)

- **Provider Abstraction**:
  - `BaseProvider` abstract base class with required methods: `search()`, `get_card()`, `search_syntax()`, `get_rate_limit_status()`
  - Optional methods in BaseProvider: `get_deck()`, `get_user_decks()`, `autocomplete()`, `is_authenticated()`, `refresh_auth()`
  - Provider metadata fields (name, base_url, rate_limit, etc.)
  - `iter_search()` method for pagination support

- **Authentication Handlers**:
  - `BaseAuthHandler` abstract class
  - `NoAuthHandler` for Scryfall (no authentication required)
  - `SessionAuthHandler` for Archidekt and Moxfield (username/password session)
  - `OAuth2ClientCredentialsHandler` for TCGPlayer and Cardmarket (OAuth2 client credentials)
  - `APIKeyAuthHandler` for Deckbox (API key authentication)

- **Provider Implementations**:
  - **Scryfall**: Full implementation with all endpoints
    - `get_card()` using `/cards/{id}` endpoint
    - `search()` using `/cards/search` endpoint with generic parameters
    - `search_syntax()` using `/cards/search` endpoint with `q` parameter
    - `autocomplete()` using `/cards/autocomplete` endpoint
    - `get_cards_by_name()` using `/cards/named` endpoint
    - Response parsing from Scryfall JSON to normalized Card model
    - Rate limit tracking (2/sec for search, 10/sec for others)
    - Comprehensive error handling for all HTTP errors
  - **Archidekt**: Full implementation
    - Authentication: login flow with username/password to `/accounts/login/`
    - Session cookie management with `requests.Session`
    - CSRF token handling (X-CSRFToken header)
    - `get_deck()` using `/api/decks/{id}/` endpoint
    - `get_user_decks()` using `/api/decks/` endpoint
    - `search()` using `/api/cards/` endpoint with generic parameters
    - `search_syntax()` using `/api/cards/` endpoint with `q` parameter
    - Response parsing with color normalization
    - Rate limit tracking (~60/min)
  - **Moxfield**: Full implementation via Parse.bot wrapper
    - Authentication: Parse.bot API key passed via X-API-Key header
    - `get_deck()` using Parse.bot wrapper endpoints
    - `get_deck_full()` using Parse.bot wrapper endpoints
    - `get_user_decks()` using Parse.bot wrapper endpoints
    - `search()` using Parse.bot `/cards/search` endpoint
    - `search_syntax()` using Parse.bot `/cards/named` endpoint with fuzzy parameter
    - `autocomplete()` using Parse.bot `/cards/autocomplete` endpoint
    - Rate limit tracking (5-100 req/min depending on tier)
  - **TCGPlayer**: Full implementation (requires approved developer access)
    - OAuth2 client credentials flow
    - Token storage and refresh logic
    - `get_card()` using `/v2/catalog/products` endpoint
    - `search()` using `/v2/catalog/products` endpoint
    - Pricing retrieval using `/v2/pricing/product/{productId}` endpoint
    - Rate limit tracking (10 req/s)
  - **Cardmarket**: Full implementation (requires approved developer access)
    - OAuth 1.0a flow with `/ws/v2.0/` endpoints
    - Token storage and refresh logic
    - `get_card()` using `/products/find` endpoint
    - `search()` using `/products` endpoint
    - Pricing retrieval using `/marketplace/prices` endpoint
    - Rate limit tracking (30K-100K req/day)

- **Universal Search Aggregator**:
  - `Aggregator` class that queries all providers
  - `search()` returns dict keyed by provider
  - `sources` parameter to limit providers
  - `search_syntax()` for syntax queries across providers
  - Timing tracking for each provider's response
  - Error handling: capture provider errors and include in results dict
  - Rate limit respect: ensure each provider is queried within its limits

- **Testing**:
  - Comprehensive unit tests for all providers
  - Exception tests
  - Model tests
  - Universal search tests
  - Integration tests (skipped by default, require opt-in via environment variable)

- **Documentation**:
  - README.md with library overview, installation, and usage examples
  - Comprehensive docstrings on all classes, methods, and modules
  - Examples in `docs/examples/`
  - API documentation structure

- **CI/CD**:
  - GitHub Actions workflows for tests, linting, and documentation checks
  - All workflows use `uv run` for commands

### Changed

- Initial release

## [Unreleased]

### Added

- Deckbox provider (pending official API release)

### To Do

- Async support using httpx or aiohttp
- Caching utilities (Redis, SQLite, filesystem)
- Circuit breaker pattern for provider failures
- Bulk operations (get multiple cards in one call)
- CLI tool (pymtg-cli package)
- Plugin system for custom providers
- Webhook support
- Card image downloading utilities
- Deck analysis utilities (mana curve, color distribution)
