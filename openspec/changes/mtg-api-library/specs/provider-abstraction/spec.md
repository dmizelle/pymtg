## ADDED Requirements

### API Verification Context
Based on subagent investigation (July 2026):
- **Scryfall**: Public, well-documented, no auth, base URL: `https://api.scryfall.com`
- **Archidekt**: Unofficial, no auth, base URL: `https://archidekt.com`, endpoints: `/api/decks/v3/`, `/api/decks/{id}/`
- **Moxfield**: Unofficial via Parse.bot wrapper, base URL: `https://api.parse.bot/scraper/55189296-4a3a-4cd2-a006-802b22cd2b73/`, requires `X-API-Key` header
- **TCGPlayer**: Official but closed to new developers, base URL: `https://api.tcgplayer.com`, requires OAuth
- **Cardmarket**: Official but closed to new developers, base URL: `https://apiv2.cardmarket.com`, requires OAuth 1.0a
- **Deckbox**: No public API available

### Requirement: All providers SHALL inherit from base provider class
Each provider implementation MUST inherit from a common base class (BaseProvider) to ensure a consistent interface and structure.

#### Scenario: Provider instantiation
- **WHEN** user imports and instantiates a provider
- **THEN** system provides a consistent interface through the base class

#### Scenario: Common methods available
- **WHEN** user accesses methods on any provider
- **THEN** all providers have the same core methods (search, get_card, etc.)

---

### Requirement: Base provider SHALL define common interface
The BaseProvider class MUST define the common interface that all providers MUST implement.

#### Scenario: Required methods
- **WHEN** a provider is implemented
- **THEN** it MUST implement: search(), get_card(), get_deck() (where applicable), and search_syntax()

#### Scenario: Optional methods
- **WHEN** a provider supports additional functionality
- **THEN** it CAN implement additional methods (get_user_decks, etc.)

---

### Requirement: Provider SHALL expose provider metadata
Each provider MUST expose metadata about itself: name, base URL, API version, authentication type, rate limits, etc.

#### Scenario: Provider identification
- **WHEN** user accesses provider.name
- **THEN** system returns a string identifier (e.g., "scryfall", "archidekt")

#### Scenario: Base URL
- **WHEN** user accesses provider.base_url
- **THEN** system returns the correct base URL:
  - Scryfall: `https://api.scryfall.com`
  - Archidekt: `https://archidekt.com`
  - Moxfield: `https://api.parse.bot/scraper/55189296-4a3a-4cd2-a006-802b22cd2b73/`
  - TCGPlayer: `https://api.tcgplayer.com`
  - Cardmarket: `https://apiv2.cardmarket.com`
  - Deckbox: N/A (no public API)

#### Scenario: Rate limit information
- **WHEN** user accesses provider.rate_limit
- **THEN** system returns the rate limit information for that provider:
  - Scryfall: 2 req/s for search, 10 req/s for other endpoints
  - Archidekt: 40-80 req/min
  - Moxfield (Parse.bot): 5-100 req/min depending on tier
  - TCGPlayer: 10 req/s
  - Cardmarket: 30,000-100,000 req/day
  - Deckbox: N/A

---

### Requirement: Provider SHALL handle its own authentication
Each provider MUST handle its own authentication mechanism internally. The base class SHALL NOT impose a specific auth mechanism.

#### Scenario: No auth provider
- **WHEN** user instantiates Scryfall()
- **THEN** system requires no authentication parameters

#### Scenario: Session auth provider
- **WHEN** user instantiates Archidekt(username="x", password="y")
- **THEN** system handles session creation and cookie management internally

#### Scenario: OAuth2 provider
- **WHEN** user instantiates TCGPlayer(client_id="a", client_secret="b")
- **THEN** system handles OAuth2 token acquisition and refresh internally

---

### Requirement: Provider SHALL maintain its own HTTP session
Each provider MUST maintain its own HTTP session (requests.Session or similar) for connection pooling, cookie persistence, and request configuration.

#### Scenario: Cookie persistence
- **WHEN** user authenticates with a session-based provider
- **THEN** system persists cookies across requests within that provider instance

#### Scenario: Connection reuse
- **WHEN** user makes multiple requests to the same provider
- **THEN** system reuses the HTTP connection for efficiency

---

### Requirement: Provider SHALL implement consistent error handling
All providers MUST use the same custom exception hierarchy for errors.

#### Scenario: Not found error
- **WHEN** a card is not found
- **THEN** all providers raise NotFoundError with consistent fields

#### Scenario: Rate limit error
- **WHEN** rate limit is exceeded
- **THEN** all providers raise RateLimitError with retry_after field where available

#### Scenario: Authentication error
- **WHEN** authentication fails
- **THEN** all providers raise AuthenticationError with appropriate details

---

### Requirement: Provider SHALL support provider-specific methods
In addition to the common interface, providers MUST be able to expose provider-specific methods that are not part of the base interface.

#### Scenario: Scryfall bulk data
- **WHEN** Scryfall provides bulk data endpoints not available on other providers
- **THEN** Scryfall provider can expose a get_bulk_data() method

#### Scenario: Archidekt user collections
- **WHEN** Archidekt provides user collection endpoints
- **THEN** Archidekt provider can expose a get_collections() method

---

### Requirement: Provider SHALL document its capabilities
Each provider MUST have documentation (via docstrings) explaining its capabilities, limitations, and any provider-specific features.

#### Scenario: Provider docstring
- **WHEN** user views help(Scryfall)
- **THEN** system displays documentation about Scryfall provider capabilities

#### Scenario: Method docstrings
- **WHEN** user views help(Scryfall.search)
- **THEN** system displays parameter descriptions, return types, and examples

---

### Requirement: Provider SHALL respect rate limits
Each provider MUST respect its own rate limits and provide appropriate warnings/errors when limits are approached or exceeded.

#### Scenario: Rate limit tracking
- **WHEN** user makes requests to a provider
- **THEN** system tracks request timing to respect rate limits

#### Scenario: Rate limit warning
- **WHEN** user approaches a provider's rate limit
- **THEN** system logs a warning about rate limit approach

#### Scenario: Rate limit error
- **WHEN** user exceeds a provider's rate limit
- **THEN** system raises RateLimitError with retry_after information

---

### Requirement: Provider SHALL handle pagination consistently
All providers MUST handle pagination in a consistent way, even if the underlying API uses different pagination mechanisms.

#### Scenario: Cursor-based pagination
- **WHEN** Scryfall returns cursor-based pagination
- **THEN** system provides a consistent interface for fetching next page

#### Scenario: Page-based pagination
- **WHEN** Archidekt returns page-based pagination
- **THEN** system provides a consistent interface for fetching next page

---

### Requirement: Provider SHALL support iterator-based pagination helpers
All providers MUST provide an iter_search() method that yields search results page by page for easy iteration.

#### Scenario: Iterate through all search results
- **WHEN** user calls provider.iter_search(name="Creature")
- **THEN** system yields Card objects one page at a time until all results are exhausted

#### Scenario: Manual page control
- **WHEN** user calls provider.iter_search(name="Creature", page_size=50)
- **THEN** system yields results in batches of 50 at a time

#### Scenario: Page metadata
- **WHEN** user iterates through search results
- **THEN** each iteration provides access to page metadata (page number, total pages, has_next, etc.)

---

### Requirement: Provider SHALL be importable from main package
All providers MUST be importable directly from the pymtg package.

#### Scenario: Direct import
- **WHEN** user executes `from pymtg import Scryfall, Archidekt`
- **THEN** system successfully imports the provider classes

#### Scenario: Provider list
- **WHEN** user wants to see all available providers
- **THEN** system provides a way to list all registered providers
