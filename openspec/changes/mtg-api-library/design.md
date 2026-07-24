## Context

This is a greenfield Python library project. Currently, no `pymtg` library exists. The project structure is minimal with only a placeholder `main.py`, `pyproject.toml`, and the OpenSpec configuration.

Existing Python MTG libraries:
- **scrython**: Well-maintained Scryfall client, but limited to Scryfall only and lacks full feature parity with the API
- **mtgsdk**: Node.js library for Scryfall
- Various unofficial wrappers for specific sites (Archidekt, Moxfield) exist as community projects but are inconsistent

No existing library provides a unified interface across multiple MTG API providers with normalized data models.

**Constraints:**
- Must follow AGENTS.md requirements: Google-style docstrings for all Python code, type annotations, line length limits
- Must use `uv run` for all command execution
- Python version: Project currently specifies >=3.13, but we should support >=3.11 to allow StrEnum usage (or >=3.10 with typing-extensions)
- All commands must be prefixed with `uv run`

**Stakeholders:**
- MTG application developers who need to integrate with multiple deckbuilding/card sites
- Open source community (potential contributors)

## Goals / Non-Goals

**Goals:**
- Provide a unified, consistent Python interface to multiple MTG API providers
- Normalize data models (Card, Deck, Pricing) across all providers so users get the same object types regardless of source
- Support Card Lookup as the primary use case with full query syntax support
- Support Deck Aggregation for retrieving decks from Archidekt, Moxfield, and Deckbox
- Support Universal Search to query across multiple providers simultaneously
- Handle diverse authentication mechanisms transparently (no auth, session cookies, OAuth2, API keys)
- Respect rate limits for each provider with automatic backoff
- Provide consistent error handling
- Be well-documented with Google-style docstrings
- Be type-safe with Pydantic models
- Be easy to extend with new providers

**Non-Goals:**
- Provide a web UI or server component (library only)
- Implement card image storage or caching (users handle their own caching)
- Provide historical pricing data (beyond what providers offer)
- Support real-time updates or webhooks (v1)
- Async support in v1 (can be added in future version)
- Support for non-MTG games (even though some providers like TCGPlayer support multiple games)
- Bulk data downloading and local database management (users can use provider bulk endpoints directly)
- Bulk operations in v1 (out of scope for initial release)
- Binary data (card images) downloading in v1 (out of scope for initial release)

## Decisions

### D001: Provider Class Pattern
**Decision:** Each API provider will have its own client class that inherits from a base `Provider` class and implements a common interface.

**Alternatives Considered:**
- **Single class with provider parameter:** Rejected because each provider has very different capabilities, auth mechanisms, and endpoints
- **Function-based API:** Rejected because it doesn't allow for provider-specific state (auth, sessions)
- **Plugin architecture:** Considered for future extensibility but adds complexity for v1

**Rationale:** The class-per-provider pattern allows each provider to have its own authentication, endpoints, and capabilities while presenting a unified interface through the base class. Users instantiate specific providers and get IDE autocomplete for provider-specific methods.

```python
# Usage example
from pymtg import Scryfall, Archidekt

# Provider-specific instantiation
scryfall = Scryfall()
archidekt = Archidekt(username="user", password="pass")

# Unified interface
cards = scryfall.search(name="Black Lotus", limit=1)
cards = archidekt.search(name="Black Lotus", limit=1)
```

### D002: Normalized Data Models with Pydantic
**Decision:** Use Pydantic v2 BaseModel for all normalized data models with strict validation.

**Alternatives Considered:**
- **Plain Python classes:** Rejected - no validation, no serialization, no type coercion
- **dataclasses:** Rejected - no validation, less IDE support
- **attrs:** Rejected - similar limitations to dataclasses
- **TypedDict:** Rejected - no runtime validation, no methods

**Rationale:** Pydantic provides:
- Runtime type validation and coercion
- Automatic serialization/deserialization
- Excellent IDE support (autocomplete, type hints)
- Integration with FastAPI and other frameworks
- Custom validators for complex fields
- Performance is acceptable for library use

**Model hierarchy:**
```
PyMTGBaseModel (BaseModel)
├── Card
├── Deck
├── DeckCard
├── Pricing
├── Set
├── User
└── ...
```

### D003: Color Enum with Single-Letter Values, Full Names, and Color Combinations
**Decision:** Color enum uses single-letter values (W, U, B, R, G) with utility methods for full names, AND includes color combinations (WU, UB, BR, RG, GW, WUB, UBH, etc.) as enum values.

**Alternatives Considered:**
- **Full names only:** Rejected - doesn't match MTG conventions, Scryfall uses single letters
- **Both as separate enums:** Rejected - unnecessary complexity, can derive full names
- **Custom class with both:** Rejected - StrEnum can't have aliases to different strings
- **Color combinations as strings only:** Rejected - user wants type-safe enum values for combinations

**Rationale:** MTG conventions use single letters (WUBRG). Scryfall API returns colors as single letters. Most MTG players understand these abbreviations. We can provide utility methods for full names when needed for display. Color combinations (like WU for Azorius, UR for Izzet) are commonly referenced in MTG and should be first-class enum values for type safety.

```python
from enum import StrEnum

class Color(StrEnum):
    # Single colors
    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"
    COLORLESS = ""
    
    # Color combinations (two-color pairs)
    AZORIUS = "WU"
    DIMIR = "UB"
    RAKDOS = "BR"
    GRUEL = "RG"
    SELESNYA = "GW"
    ORZHOV = "WB"
    GOLGARI = "BG"
    SIMIC = "UG"
    BOROS = "RW"
    IZZET = "UR"
    
    # Three-color shards
    BANT = "WUG"
    ESPER = "WUB"
    GRIXIS = "UBR"
    JUND = "BRG"
    NAYA = "RGW"
    ABZAN = "WBG"
    JESKAI = "WUR"
    SULTIA = "URG"
    MARDEK = "RGW"
    TEMPO = "GWU"
    
    # Four-color combinations
    WUBR = "WUBR"
    WUBG = "WUBG"
    WURG = "WURG"
    WBRG = "WBRG"
    UBRG = "UBRG"
    
    # Five-color
    WUBRG = "WUBRG"

    @property
    def full_name(self) -> str:
        """Returns the full display name for the color or color combination."""
        names = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green", "": "Colorless"}
        if not self.value:
            return names[""]
        return " ".join(names[c] for c in self.value)

    @classmethod
    def from_full_name(cls, name: str) -> "Color":
        """Converts a full color name to Color enum value."""
        mapping = {"White": cls.WHITE, "Blue": cls.BLUE, "Black": cls.BLACK, "Red": cls.RED, "Green": cls.GREEN, "Colorless": cls.COLORLESS}
        return mapping.get(name, cls.COLORLESS)

    @classmethod
    def from_colors(cls, colors: list["Color"]) -> "Color":
        """Creates a color combination from a list of individual colors."""
        combined = "".join(sorted(c.value for c in colors if c.value))
        # Try to find exact match in enum
        for member in cls:
            if member.value == combined:
                return member
        # If no exact match, return as combined string (will still be valid)
        return cls(combined)
```

### D004: Scryfall ID as Canonical Card Identifier
**Decision:** Use Scryfall UUID as the canonical card identifier across all providers.

**Alternatives Considered:**
- **Provider-specific IDs:** Rejected - no unified identifier
- **MTGJSON ID:** Rejected - not all providers use this
- **Multiverse ID:** Rejected - not all cards have this, not unique across printings
- **Oracle ID:** Rejected - identifies the card text but not the specific printing

**Rationale:** Scryfall IDs are:
- UUIDs (globally unique)
- Stable (don't change)
- Available in Scryfall responses
- Mapped to by other providers (TCGPlayer, Cardmarket IDs available in Scryfall responses)
- The de facto standard MTG API

All Card models will have both a provider-specific ID and the Scryfall ID (if available).

### D005: Generic Parameters + Syntax Escape Hatch
**Decision:** Each provider will have a `search()` method with generic parameters AND a `search_syntax()` method for provider-specific query syntax.

**Alternatives Considered:**
- **Generic parameters only:** Rejected - hides provider capabilities, limits power users
- **Provider-specific syntax only:** Rejected - inconsistent API, defeats unification purpose
- **Query builder pattern:** Considered but adds complexity for v1

**Rationale:** The generic `search()` method provides a consistent interface for common use cases (name, colors, type, etc.). The `search_syntax()` escape hatch allows power users to use provider-specific query syntax when needed. This gives us the best of both worlds.

```python
# Generic interface
cards = archidekt.search(
    name="Lightning Bolt",
    colors=[Color.RED],
    identity=[Color.RED],
    type_line="Instant",
    limit=10
)

# Escape hatch for advanced queries
cards = archidekt.search_syntax("o:treasure ci:black type:creature")
```

### D006: Provider-Specific Pricing Model
**Decision:** Use provider-specific pricing fields within a unified Pricing model (Option A from exploration).

**Alternatives Considered:**
- **Generic PricePoint with source:** Rejected - loses type safety per provider
- **Flat pricing fields:** Rejected - providers have different pricing concepts (TCGPlayer has market/mid/low/high, Cardmarket has avg1/avg7/avg30, Scryfall has usd/eur/tix)

**Rationale:** Type safety is paramount (user's decision). Provider-specific pricing models allow:
- Type-safe access to provider-specific fields
- Clear documentation of what each provider offers
- No ambiguity about which field means what
- Easy to extend when providers add new pricing fields

```python
class ScryfallPricing(BaseModel):
    usd: float | None = None
    usd_foil: float | None = None
    usd_etched: float | None = None
    eur: float | None = None
    eur_foil: float | None = None
    tix: float | None = None

class TCGPlayerPricing(BaseModel):
    market: float | None = None
    mid: float | None = None
    low: float | None = None
    high: float | None = None
    direct_low: float | None = None

class CardmarketPricing(BaseModel):
    avg1: float | None = None
    avg7: float | None = None
    avg30: float | None = None
    low: float | None = None
    low_ex: float | None = None
    trend: float | None = None

class Pricing(BaseModel):
    scryfall: ScryfallPricing | None = None
    tcgplayer: TCGPlayerPricing | None = None
    cardmarket: CardmarketPricing | None = None
```

### D007: Eager Loading for Deck Cards
**Decision:** Full Card objects for each card in a Deck (Option A from exploration).

**Alternatives Considered:**
- **Lazy loading with references:** Rejected - adds complexity, requires additional calls
- **Mixed approach:** Considered but adds inconsistency

**Rationale:** 
- Simpler API for users
- Most deck use cases need the full card data anyway
- Providers return card data with decks (Archidekt, Moxfield do)
- Users can cache responses themselves if needed
- Eager loading matches the user's stated preference

Note: This may be revisited if performance becomes an issue with very large decks.

---

### D015: Fuzzy Matching Normalization
**Decision:** Normalize fuzzy matching behavior across all providers to provide consistent search results.

**Alternatives Considered:**
- **Provider-specific fuzzy matching:** Rejected - inconsistent user experience
- **No fuzzy matching:** Rejected - users expect fuzzy matching for card names

**Rationale:** Users expect consistent behavior regardless of provider. Each provider has different fuzzy matching algorithms, but we should normalize the results to provide a consistent interface.

**Implementation:**
- Each provider will implement fuzzy matching normalization in its response parsing
- Provide a centralized fuzzy matching utility for consistent behavior
- Allow providers to override with provider-specific logic when necessary

---

### D016: Multiple Prints Handling
**Decision:** Return all prints of a card by default when searching.

**Alternatives Considered:**
- **Return only latest print:** Rejected - users often need access to all printings
- **Require users to specify:** Rejected - adds friction for common use case
- **Provider-dependent:** Rejected - inconsistent behavior

**Rationale:** Most use cases benefit from having access to all printings. Users can filter by set or other criteria if they need specific prints.

**Implementation:**
- Scryfall already returns all prints by default
- Other providers should be normalized to return all available prints
- Add `distinct` parameter to search methods for users who want only one version

---

### D017: Pricing Eager Loading
**Decision:** Pricing information should be eagerly loaded by default (user's preference).

**Rationale:** Users typically want pricing information when retrieving cards. Most providers return pricing with card data, so eager loading is natural.

**Implementation:**
- Pricing field will be populated in Card model by default
- Providers that don't return pricing will have None for their pricing fields
- Add lazy loading option in future if performance becomes an issue

### D008: Constructor-Based Authentication
**Decision:** Each provider client accepts its required authentication via constructor parameters (user's Decision 4).

**Alternatives Considered:**
- **Config object:** Rejected - user prefers simpler constructor approach
- **Environment variables only:** Rejected - less flexible, harder to test
- **From environment class method:** Can be added as convenience but not primary

**Rationale:** Simple, explicit, and Pythonic. Each provider knows what it needs. Users can still use environment variables via their own code.

```python
# Direct
archidekt = Archidekt(username="user", password="pass")

# Or via environment (user's code, not library's)
import os
archidekt = Archidekt(
    username=os.getenv("ARCHIDEKT_USERNAME"),
    password=os.getenv("ARCHIDEKT_PASSWORD")
)
```

### D009: Universal Search Returns Dict Keyed by Provider
**Decision:** Universal search aggregator returns a dictionary with provider names as keys (user's Decision 6).

**Alternatives Considered:**
- **Unified result list:** Rejected - user prefers per-provider results
- **Custom typed dict:** Rejected - user doesn't like string keys in dicts, but this is the cleanest approach

**Rationale:** Allows users to:
- See which providers returned results
- Handle provider-specific issues
- Access results by provider name
- Implement their own deduplication if needed

```python
results = aggregator.search("Black Lotus")
# results = {
#     "scryfall": [Card(...), ...],
#     "archidekt": [Card(...), ...],
#     "moxfield": "Error: rate limited"
# }
```

### D010: Project Structure
**Decision:** Organize code into clear subpackages by concern.

```
pymtg/
├── __init__.py           # Main exports
├── _version.py           # Version info
├── models/               # Normalized data models
│   ├── __init__.py
│   ├── base.py           # PyMTGBaseModel
│   ├── card.py           # Card, CardFace, DeckCard
│   ├── deck.py           # Deck
│   ├── pricing.py        # Pricing and provider-specific pricing
│   └── enums.py          # Color, Rarity, Format, Board, SetType, etc.
├── providers/            # Provider implementations
│   ├── __init__.py       # Exports all providers
│   ├── base.py          # BaseProvider ABC
│   ├── scryfall.py      # Scryfall provider
│   ├── archidekt.py     # Archidekt provider
│   ├── moxfield.py      # Moxfield provider
│   ├── tcgplayer.py     # TCGPlayer provider
│   ├── cardmarket.py    # Cardmarket provider
│   └── deckbox.py       # Deckbox provider
├── auth/                # Authentication handlers
│   ├── __init__.py
│   ├── base.py          # Base auth handler
│   ├── session.py       # Session cookie auth
│   ├── oauth2.py        # OAuth2 client credentials
│   └── api_key.py       # API key auth
├── search/              # Universal search
│   └── aggregator.py    # Aggregator class
├── utils/               # Utilities
│   ├── __init__.py
│   ├── http.py          # HTTP client utilities
│   ├── rate_limiting.py # Rate limit handling
│   └── retry.py         # Retry logic
├── exceptions.py        # Custom exception hierarchy
├── config.py            # Configuration classes
└── __main__.py          # CLI entry point (future)

tests/
├── test_models.py
├── test_providers/
│   ├── test_scryfall.py
│   └── ...
└── ...

docs/
examples/
```

### D011: Error Handling Hierarchy
**Decision:** Create a custom exception hierarchy for consistent error handling across providers.

**Rationale:** Allows users to catch specific error types and handle them appropriately. Provides context about which provider and what went wrong.

```python
class PyMTGError(Exception):
    """Base exception for all pymtg errors."""
    provider: str
    message: str
    status_code: int | None = None
    details: dict | None = None

class RateLimitError(PyMTGError):
    """Rate limit exceeded."""
    retry_after: int | None = None  # Seconds to wait

class NotFoundError(PyMTGError):
    """Resource not found."""
    resource_type: str  # "card", "deck", "set", etc.
    resource_id: str | None = None

class AuthenticationError(PyMTGError):
    """Authentication failed."""
    pass

class InvalidQueryError(PyMTGError):
    """Invalid query syntax."""
    query: str
    provider_specific_message: str | None = None

class APIError(PyMTGError):
    """Generic API error."""
    pass

class NetworkError(PyMTGError):
    """Network-related error."""
    pass
```

### D012: Rate Limit Implementation Strategy
**Decision:** Implement rate limiting respect but NOT automatic retry/backoff in v1. Users must handle rate limits themselves or we provide opt-in utilities.

**Alternatives Considered:**
- **Automatic backoff:** Rejected for v1 - adds complexity, may mask issues
- **Semaphore-based throttling:** Can be added as optional utility

**Rationale:** 
- Each provider has different rate limits
- Automatic retries can cause cascading issues
- Users should be aware of rate limits
- We can provide utilities to help users respect limits

**Implementation:**
- Track last request time per provider
- Warn/log when approaching limits
- Provide utility for users to implement their own backoff
- Document rate limits clearly per provider

### D013: Minimum Card Model for MVP
**Decision:** Implement a practical Card model that covers the essential fields needed for Card Lookup, Deck Aggregator, and Universal Search.

**Fields:**
- `id`: Provider-specific ID
- `scryfall_id`: Canonical Scryfall UUID (None if not available from provider)
- `name`: Card name
- `mana_cost`: Raw mana cost string
- `cmc`: Converted mana cost (float to handle fractional costs)
- `type_line`: Full type line string
- `oracle_text`: Oracle rules text
- `colors`: List of colors in mana cost
- `color_identity`: List of colors in color identity
- `keywords`: List of keyword abilities
- `set_code`: Set code (e.g., "LEA", "M20")
- `set_name`: Full set name
- `rarity`: Rarity
- `collector_number`: Collector number
- `power`: Power (string to handle non-numeric values like "*")
- `toughness`: Toughness (string)
- `image_uris`: Dictionary of image URIs
- `pricing`: Pricing information (nullable, eager-loaded)
- `legalities`: Dictionary of format legalities

**Rationale:** This covers 95% of use cases for the three initial features while keeping the model manageable. Additional fields can be added as needed based on user feedback.

### D014: Python Version Support
**Decision:** Support Python 3.11+ as the minimum version.

**Alternatives Considered:**
- **Python 3.13+:** Rejected - too restrictive, limits user base
- **Python 3.10+:** Considered - wider compatibility but requires typing-extensions for StrEnum
- **Python 3.9+:** Rejected - no native type hints for collections, less ideal

**Rationale:**
- Python 3.11 is widely available (released Oct 2022)
- Provides StrEnum natively
- Has modern type system features
- All type annotations work without additional dependencies
- Can still support 3.10 users if they install typing-extensions, but we won't officially support it

---

### D018: Session Persistence
**Decision:** Persist sessions across requests within a provider instance using requests.Session (user's Decision 7).

**Alternatives Considered:**
- **No session persistence:** Rejected - requires users to re-authenticate for each request
- **Global session pool:** Rejected - complex, potential for credential leakage between instances
- **Disk-based persistence:** Rejected - security risk, user wants in-memory only

**Rationale:** Users expect that once authenticated, a provider client can make multiple requests without re-authenticating. Using requests.Session provides cookie persistence automatically. Each provider instance maintains its own session.

**Implementation:**
- Each provider class will use a requests.Session instance
- Session is created during initialization/authentication
- Cookies (including sessionid, csrftoken) are automatically managed
- Session is not persisted to disk - in-memory only
- Multiple provider instances can coexist with separate sessions

---

### D019: Pagination Helpers
**Decision:** Implement pagination helpers for providers that support pagination (user's Decision 9).

**Alternatives Considered:**
- **No pagination helpers:** Rejected - users would need to implement pagination themselves
- **Automatic full result fetching:** Rejected - can be inefficient for large result sets

**Rationale:** Many providers return paginated results. Providing iterator-based helpers improves usability significantly while giving users control over when to stop.

**Implementation:**
- Add `iter_search()` method to BaseProvider that yields results page by page
- Each provider implements its own pagination logic based on its API
- Provide a consistent interface across all providers
- Include page metadata (current page, total pages, has_next, etc.) when available

---

### D020: Type Stub Package
**Decision:** Include py.typed marker file for basic IDE type hint support (user's Decision 10).

**Alternatives Considered:**
- **Separate stubs package:** Rejected - adds complexity, not needed for v1
- **No type hints:** Rejected - type safety is paramount per user's preference

**Rationale:** Including py.typed marker enables IDEs like VS Code, PyCharm, and others to recognize the package as having type hints without requiring a separate stubs package.

**Implementation:**
- Add `pymtg/__init__.pyi` stub file or include py.typed marker
- Actually, for Pydantic models, the py.typed marker in the package root is sufficient
- Add `py.typed` file to pymtg package
- Ensure all public APIs have complete type annotations

---

### D021: Error Handling - Fail Fast
**Decision:** Fail fast when a provider is unavailable or returns an error (user's Decision 5).

**Alternatives Considered:**
- **Retry other providers:** Rejected - can mask issues, inconsistent behavior
- **Return cached data:** Rejected - not implemented in v1, adds complexity
- **Silent failure:** Rejected - users need to know when something goes wrong

**Rationale:** Users should be immediately aware when a provider fails so they can handle it appropriately. In Universal Search, failed providers will be indicated in the results dict rather than silently omitted.

**Implementation:**
- Providers raise appropriate exceptions immediately on failure
- Universal Search Aggregator catches provider errors and includes them in the results dict
- Error messages are clear and actionable

## Risks / Trade-offs

**[Risk: Provider API changes]**: Each provider can change their API at any time, breaking our adapters.
- **Mitigation:** Monitor provider API changelogs, implement version detection, provide clear error messages when APIs change, make adapters easy to update.

**[Risk: Rate limit complexity]**: Different rate limits per provider, plus user's own usage patterns, makes it hard to provide a one-size-fits-all solution.
- **Mitigation:** Document rate limits clearly, provide examples of respectful usage, offer opt-in utilities for rate limiting, let users control their own caching.

**[Risk: Authentication complexity]**: Each provider has different auth mechanisms (none, session, OAuth2, API key) which are complex to implement correctly.
- **Mitigation:** Isolate auth handling in the auth/ subpackage, provide clear examples per provider, document auth requirements thoroughly, test auth flows with real accounts.

**[Risk: Data model drift]**: Providers may return data that doesn't perfectly fit our normalized models, or new card types/layouts may not be representable.
- **Mitigation:** Use Pydantic's flexible validation (coerce types where possible), make models extensible with optional fields, document limitations clearly, provide escape hatches for raw data access.

**[Risk: Performance with eager loading]**: Loading full Card objects for large decks may be slow and memory-intensive.
- **Mitigation:** Document the memory implications, suggest pagination for large queries, consider adding lazy loading option in future version, allow users to select specific fields.

**[Risk: Session management complexity]**: Session-based auth (Archidekt, Moxfield) requires managing cookies, CSRF tokens, session expiration, etc.
- **Mitigation:** Use requests.Session for cookie persistence, implement session refresh logic, provide clear error messages for expired sessions, document session lifetime expectations.

**[Risk: Dependency on undocumented APIs]**: Archidekt and Moxfield APIs are undocumented and could change without notice.
- **Mitigation:** Treat these as "best effort" providers, document their undocumented status, provide fallback to other providers where possible, make it easy to update adapters when APIs change.

**[Risk: Async support delayed]**: Not including async support in v1 may limit adoption by async-native frameworks.
- **Mitigation:** Design the sync interface to be easily wrappable in async (e.g., using asyncio.to_thread or similar), document async usage patterns, prioritize async support for v2.

**[Risk: Provider approval requirements]**: TCGPlayer and Cardmarket require approval, which may limit testing and deployment.
- **Mitigation:** Document the approval process, provide guidance on obtaining credentials, implement these providers but document they require approval, test with mock data where possible.

## API Verification Findings

Based on subagent investigation of all provider APIs (July 2026):

| Provider | API Status | Base URL | Auth Method | Rate Limits | Card Lookup | Deck Retrieval | Notes |
|----------|------------|----------|-------------|-------------|--------------|----------------|-------|
| **Scryfall** | ✅ Public | `api.scryfall.com` | None (OAuth beta) | 2-10 req/s | ✅ Full | ❌ No | Well-documented, reliable |
| **Archidekt** | ⚠️ Unofficial | `archidekt.com` | None | 40-80 req/min | ✅ Via decks | ✅ Full | Undocumented, may change, user will provide HAR files |
| **Moxfield** | ⚠️ Wrapper | `api.parse.bot/...` | Parse.bot key | 5-100 req/min* | ✅ Full | ❌ No | Uses Parse.bot service, requires their API key |
| **TCGPlayer** | ❌ Closed | `api.tcgplayer.com` | OAuth/Bearer | 10 req/s | ✅ Full | ❌ No | New access not granted, existing users only |
| **Cardmarket** | ❌ Closed | `apiv2.cardmarket.com` | OAuth 1.0a | 30K-100K/day | ✅ Full | ❌ No | New access not granted, existing users only |
| **Deckbox** | ❌ None | `deckbox.org` | None | N/A | ❌ No | ❌ No | API "not ready", no official endpoint |

*Parse.bot tiers: Free (5/min), Hobby (20/min), Developer (100/min)

**Findings:**
- **Scryfall** is the only provider with a fully public, well-documented API with no auth required
- **Archidekt** has an undocumented but functional API that we can reverse-engineer using HAR files
- **Moxfield** requires using the Parse.bot wrapper service (paid tiers for higher limits)
- **TCGPlayer** and **Cardmarket** require pre-existing API approval that is currently not available for new developers
- **Deckbox** has no public API and the team has stated it's "not ready"

**Recommended Implementation Order:**
1. **Scryfall** (Phase 1) - No blockers, can start immediately
2. **Archidekt** (Phase 2) - User will provide HAR files for testing
3. **Moxfield** (Phase 2) - Requires Parse.bot API key, but service is available
4. **TCGPlayer/Cardmarket** (Phase 3) - Implement but cannot fully test without approval
5. **Deckbox** (Future) - Monitor for API release

---

## Migration Plan

As this is a new library with no existing users, there is no migration needed. The plan is:

1. **Phase 1: Core Implementation**
   - Implement Scryfall provider (no auth, well-documented)
   - Implement normalized models (Card, enums)
   - Implement base provider class and interface
   - Add error handling
   - Add basic tests

2. **Phase 2: Provider Expansion**
   - Implement Archidekt provider (session auth, using HAR files provided by user)
   - Implement Moxfield provider (via Parse.bot wrapper API)
   - Add universal search aggregator
   - Add pagination helpers (iter_search)

3. **Phase 3: Advanced Features**
   - Implement TCGPlayer provider (OAuth2, requires approval - implement but cannot test without credentials)
   - Implement Cardmarket provider (OAuth 1.0a, requires approval - implement but cannot test without credentials)
   - Add rate limiting utilities
   - Add retry/backoff utilities

4. **Phase 4: Polish and Release**
   - Complete documentation
   - Add examples
   - Set up CI/CD
   - Publish to PyPI

**Rollback Strategy:** N/A (new library, no existing deployment)

## Open Questions

None - All v1 planning questions have been resolved.

## Resolved Questions (v1)

The following questions have been resolved and incorporated into the design decisions above:

1. **[Color Enum]** ✅ Include color combinations as enum values (D003, D015)
2. **[Card Model Completeness]** ✅ Practical subset (~20 fields) for v1 (D013)
3. **[Fuzzy Matching]** ✅ Normalize fuzzy matching behavior across providers (D015)
4. **[Multiple Prints Handling]** ✅ Return all prints by default (D016)
5. **[Provider Availability]** ✅ Fail fast (D021)
6. **[Bulk Operations]** ✅ Not in v1 scope (Non-Goals)
7. **[Session Persistence]** ✅ Persist sessions across requests within instance using requests.Session (D018)
8. **[Binary Data (Images)]** ✅ Not in v1 scope (Non-Goals)
9. **[Pagination Helpers]** ✅ Implement iterator-based pagination helpers (D019)
10. **[Type Stub Package]** ✅ Include py.typed marker (D020)
