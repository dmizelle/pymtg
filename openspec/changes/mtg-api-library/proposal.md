## Why

Magic: The Gathering developers currently need to integrate with multiple deckbuilding and card database sites (Scryfall, Archidekt, Moxfield, TCGPlayer, Cardmarket, Deckbox), each with different APIs, authentication mechanisms, data formats, and query syntaxes. This forces developers to learn and maintain separate integrations for each provider, leading to duplicated effort, inconsistent data models, and brittle code.

pymtg solves this by providing a **unified Python library** with a consistent interface and normalized data models across all major MTG API providers. This enables developers to build MTG applications that work across multiple platforms without provider-specific code.

## What Changes

- Create new Python library `pymtg` as the root package
- Add provider-specific client classes for Scryfall (public), Archidekt (unofficial), Moxfield (via Parse.bot wrapper), TCGPlayer (OAuth2, closed to new devs), and Cardmarket (OAuth 1.0a, closed to new devs)
- Introduce normalized Pydantic data models (Card, Deck, Pricing, Color, Rarity, Format, etc.)
- Implement unified search interface with provider-specific adapters
- Add authentication handling for different provider requirements (none for Scryfall, session cookies for Archidekt, API key for Parse.bot/Moxfield, OAuth2 for TCGPlayer, OAuth 1.0a for Cardmarket)
- **Note:** Deckbox has no public API and is deferred to future release
- Add rate limiting respect per provider
- Add error handling with custom exception hierarchy
- Create documentation and examples

## Capabilities

### New Capabilities
- **card-lookup**: Fetch and search for card data from any supported provider with normalized Card model output
- **deck-aggregation**: Retrieve and normalize deck data from deckbuilding providers (Archidekt, Moxfield via Parse.bot)
- **universal-search**: Search across multiple providers simultaneously with unified query syntax
- **provider-abstraction**: Common interface for all MTG API providers with provider-specific implementations
- **normalized-models**: Standardized Pydantic models for Card, Deck, Pricing, and supporting types that work across all providers
- **authentication-management**: Handle diverse authentication mechanisms (no auth for Scryfall, session cookies for Archidekt, API key for Parse.bot/Moxfield, OAuth2 for TCGPlayer, OAuth 1.0a for Cardmarket)
- **Note:** Deckbox has no public API and is not included in v1.0 scope
- **rate-limit-handling**: Built-in respect for each provider's rate limits with automatic backoff
- **error-handling**: Consistent exception types and error handling patterns across all providers

### Modified Capabilities
- None (this is a new library, no existing capabilities to modify)

## Impact

- **New code**: Entire `pymtg/` package with submodules for models, providers, utilities
- **Dependencies**: `requests` (HTTP client), `pydantic>=2.0` (data models), `typing-extensions` (for StrEnum on Python < 3.11)
- **Optional dependencies**: `httpx` or `aiohttp` (for async support in future)
- **Configuration**: Environment variables for API keys and credentials
- **Compatibility**: Python 3.11+ (for StrEnum), but can support 3.10+ with typing-extensions
