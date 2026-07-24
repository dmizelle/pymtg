# Archidekt Provider Implementation Design

This document describes the technical design for implementing the Archidekt provider based on reverse-engineered API analysis from the HAR file at `/tmp/archidekt.har`.

## Context

### Current State

The existing Archidekt provider implementation (`pymtg/providers/archidekt.py`) uses `SessionAuthHandler` which expects:
- Session cookie-based authentication via `/accounts/login/`
- CSRF token protection
- Form-encoded POST data for login

However, the actual Archidekt API (as revealed by HAR file analysis) uses:
- JWT Bearer token authentication via `/api/rest-auth/login/`
- JSON-encoded POST data for login
- Authorization header: `JWT <token>`
- API base URL: `https://archidekt.com/api/`

This mismatch means the current implementation **will not work** with the real Archidekt API.

### Constraints

1. **Must use existing pymtg infrastructure**: The implementation must inherit from `BaseProvider` and use existing models (`Card`, `Deck`, etc.)
2. **Must follow AGENTS.md requirements**: All code must have Google-style docstrings, type annotations, etc.
3. **Must use uv for package management**: All commands must be prefixed with `uv run`
4. **Must handle credentials securely**: Never persist credentials or tokens to disk; clear from memory after use
5. **Must be backward compatible where possible**: While authentication is breaking, other aspects should integrate with existing pymtg patterns

### Stakeholders

- Users of pymtg who want to use Archidekt
- Maintainers of pymtg who need to review and merge changes
- Future developers who will maintain this code

## Goals / Non-Goals

### Goals

1. **Functional Archidekt API access**: Users can authenticate, search cards, create decks, and manage deck cards
2. **Accurate API mapping**: Implementation matches the actual Archidekt API endpoints and data structures from HAR analysis
3. **Consistent with pymtg patterns**: Follows existing provider patterns (Scryfall, Moxfield, etc.)
4. **Error handling**: Proper exceptions for all error scenarios
5. **Rate limit awareness**: Respects Archidekt's ~60 requests/minute limit
6. **HAR logging capability**: Enables debugging by exporting HTTP traffic to HAR format
7. **Secure credential handling**: JWT tokens stored in memory only, cleared appropriately
8. **Testable**: Includes tests with HAR-based mock responses

### Non-Goals

1. **OAuth2 support**: Archidekt uses JWT via username/password, not OAuth2
2. **Session cookie support**: Archidekt uses JWT tokens, not session cookies
3. **Real-time features**: WebSocket support (seen in HAR but not required for initial implementation)
4. **Collection management**: Focus on decks and cards, not user collections
5. **Folder management**: Deck folders are referenced but not a priority for initial implementation
6. **Pagination helpers**: While supported, automatic pagination iteration is not required initially

## Decisions

### Decision: Use JWT Authentication Handler (Not SessionAuthHandler)

**Chosen**: Create new `JWTAuthHandler` in `pymtg/auth/jwt.py`

**Rationale**: 
- Archidekt API uses JWT Bearer tokens, not session cookies
- Existing `SessionAuthHandler` expects CSRF tokens and form data, which won't work
- JWT is a standard authentication pattern that may be reused by other providers
- Keeps authentication logic separate and testable

**Alternatives Considered**:
1. **Modify SessionAuthHandler**: Could extend to support JWT, but would add complexity and confusion
2. **Inline JWT in Archidekt provider**: Would work but violates separation of concerns
3. **Use OAuth2 handler**: Archidekt doesn't use OAuth2 flow, so not applicable

**Implementation**:
```python
class JWTAuthHandler(BaseAuthHandler):
    """Handles JWT token-based authentication for Archidekt."""
    
    def __init__(self, base_url: str, login_endpoint: str = "/api/rest-auth/login/"):
        self.base_url = base_url
        self.login_endpoint = login_endpoint
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    def authenticate(self, username: str, password: str) -> str:
        """POST credentials to login endpoint, return access token."""
        # Implementation here
    
    def get_auth_header(self) -> dict[str, str]:
        """Return Authorization header with JWT token."""
        if self.access_token:
            return {"Authorization": f"JWT {self.access_token}"}
        return {}
```

---

### Decision: Use `/api/` Base URL (Not Root Domain)

**Chosen**: All API requests go to `https://archidekt.com/api/` base URL

**Rationale**:
- All API endpoints in HAR file are under `/api/` path
- Frontend makes requests to `/api/cards/v2/`, `/api/decks/v2/`, `/api/rest-auth/login/`
- Separates API traffic from frontend routes

**Implementation**:
```python
# In Archidekt provider
base_url = "https://archidekt.com/api/"
```

---

### Decision: Use httpx for HTTP Client (Not requests)

**Chosen**: Use `httpx.AsyncClient` for async HTTP requests

**Rationale**:
- pymtg already uses httpx in other providers (moxfield.py)
- Better async support than requests
- HTTP/2 support
- Cleaner API for modern Python

**Note**: The existing `HTTPClient` in `pymtg/utils/http.py` uses `requests` library. For consistency with async patterns, we'll use httpx directly in the Archidekt provider.

**Alternatives Considered**:
1. **Use existing HTTPClient**: Would require modifying to support httpx or adding httpx support
2. **Use requests only**: Would work but lacks async support

**Implementation**:
```python
import httpx

class ArchidektClient:
    """Async HTTP client for Archidekt API."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url="https://archidekt.com/api/",
            timeout=30.0,
        )
```

---

### Decision: Keep Existing Archidekt Provider File Structure

**Chosen**: Replace existing `pymtg/providers/archidekt.py` with new implementation

**Rationale**:
- Single file per provider is the existing pattern (scryfall.py, moxfield.py, etc.)
- Keeps imports simple: `from pymtg.providers import Archidekt`
- No need to split into multiple files initially

**Alternatives Considered**:
1. **Create archidekt/ subdirectory**: More organized but breaks existing pattern
2. **Keep as separate file**: Not applicable, already exists

**Structure**:
```
pymtg/providers/archidekt.py
├── Archidekt class (main provider)
├── JWTAuthHandler (or import from auth/jwt.py)
├── Card parsing methods
├── Deck parsing methods
└── Error handling
```

---

### Decision: Map Generic Search Parameters to Archidekt-Specific

**Chosen**: Implement parameter mapping in `search()` and `search_syntax()` methods

**Rationale**:
- BaseProvider requires `search()` with generic parameters (name, colors, identity, type_line)
- Archidekt uses different parameter names (nameSearch, colors, colorIdentity, etc.)
- Need to map between the two for consistency

**Mapping Strategy**:
```python
def _build_search_params(self, name: str | None = None, colors: list[Color] | None = None, 
                        identity: list[Color] | None = None, type_line: str | None = None,
                        **kwargs) -> dict[str, Any]:
    params = {}
    
    # Map name to nameSearch for partial matches
    if name:
        params["nameSearch"] = name
    
    # Map colors to colors filter
    if colors:
        color_str = ",".join(c.value for c in colors)
        params["colors"] = color_str
    
    # Map identity to colorIdentity
    if identity:
        params["colorIdentity"] = "true"
        # Also include colors if provided
        if colors:
            color_str = ",".join(c.value for c in colors)
            params["colors"] = color_str
    
    # Map type_line to appropriate filter
    if type_line:
        # Archidekt may not have direct type_line filter
        # Could use text search or subtype filters
        params["textsearch"] = type_line
    
    # Include default flags
    params["includeTokens"] = ""
    params["includeEmblems"] = ""
    params["unique"] = ""
    
    return params
```

---

### Decision: Store deckRelationId for Card Operations

**Chosen**: Track deckRelationId returned from add operations for use in remove/modify

**Rationale**:
- Archidekt requires deckRelationId for remove and modify operations
- deckRelationId is returned in response to add operations
- Need to store this mapping to support future operations on the same card

**Implementation Options**:
1. **In-memory mapping in provider**: Simple but lost when provider is recreated
2. **Return deckRelationId to user**: User must track it themselves
3. **Store in DeckCard model**: Persist with the card in the deck

**Chosen**: Option 3 - Store in DeckCard model extension

```python
# In DeckCard or extended model
class ArchidektDeckCard(DeckCard):
    """DeckCard with Archidekt-specific metadata."""
    deck_relation_id: int | None = None
```

---

### Decision: Use Pydantic Models for Data Parsing

**Chosen**: Use Pydantic models to parse Archidekt responses into pymtg models

**Rationale**:
- Existing pymtg models (Card, Deck, etc.) are already Pydantic models
- Provides type safety and validation
- Can handle nested structures cleanly
- Built-in serialization/deserialization

**Implementation**:
```python
from pymtg.models.card import Card
from pymtg.models.deck import Deck
from pydantic import BaseModel

class ArchidektCardResponse(BaseModel):
    """Archidekt-specific card response structure."""
    id: int
    oracleCard: dict  # Nested card data
    edition: dict
    prices: dict | None = None
    # ... other fields
    
    def to_card(self) -> Card:
        """Convert Archidekt response to pymtg Card model."""
        return Card(
            id=str(self.id),
            name=self.oracleCard.get("name"),
            mana_cost=self.oracleCard.get("manaCost"),
            # ... other mappings
        )
```

---

### Decision: Implement Rate Limiting with Token Bucket

**Chosen**: Implement token bucket algorithm for rate limiting

**Rationale**:
- Simple and effective for API rate limiting
- Allows bursts of requests up to the limit
- Easy to understand and debug
- Can be shared across provider instances if needed

**Implementation**:
```python
from collections import deque
from datetime import datetime, timedelta
import time

class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: deque[float] = deque()
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove old timestamps
        while self.timestamps and now - self.timestamps[0] > self.window_seconds:
            self.timestamps.popleft()
        
        # If at limit, wait
        if len(self.timestamps) >= self.max_requests:
            oldest = self.timestamps[0]
            wait_time = self.window_seconds - (now - oldest)
            if wait_time > 0:
                time.sleep(wait_time)
                now = time.time()
                # Clean up again after waiting
                while self.timestamps and now - self.timestamps[0] > self.window_seconds:
                    self.timestamps.popleft()
        
        # Record this request
        self.timestamps.append(now)
```

---

### Decision: Keep HAR Logging in Provider (Not HTTP Client)

**Chosen**: Implement HAR logging in the Archidekt provider itself

**Rationale**:
- HAR logging is a debugging feature, not core functionality
- Keeps HTTP client clean and focused
- Easier to access from provider level
- Can be enabled/disabled without affecting core operations

**Implementation**:
```python
class Archidekt(BaseProvider):
    """Archidekt provider with HAR logging support."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._har_entries: list[dict] = []
        self._har_enabled: bool = False
    
    def enable_har_logging(self) -> None:
        """Enable HAR logging."""
        self._har_enabled = True
    
    def disable_har_logging(self) -> None:
        """Disable HAR logging."""
        self._har_enabled = False
    
    def export_har(self, filename: str) -> None:
        """Export HAR data to file."""
        har = {
            "log": {
                "version": "1.2",
                "creator": {"name": "pymtg Archidekt Provider", "version": __version__},
                "entries": self._har_entries
            }
        }
        with open(filename, 'w') as f:
            json.dump(har, f, indent=2)
```

## Risks / Trade-offs

### Risk: Archidekt API Changes
**Mitigation**: API is unofficial and undocumented; implementation is based on current HAR analysis. If API changes, tests will fail and can be updated. HAR logging will help diagnose future changes.

### Risk: JWT Token Expiration
**Mitigation**: Implement token refresh using refresh_token when access_token expires. Track token expiration from JWT payload (exp claim).

### Risk: Rate Limit Sharing Across Instances
**Mitigation**: Current implementation uses per-instance rate limiting. For multi-threaded use, use thread-safe structures. For distributed systems, would need external coordination (Redis, etc.).

### Risk: Memory Usage from HAR Logging
**Mitigation**: HAR entries can grow large; provide method to clear entries. Limit total entries or memory usage. Warn users not to enable in production for long periods.

### Risk: Incomplete HAR Analysis
**Mitigation**: HAR file contains limited examples. Implementation may encounter undocumented endpoints or parameters. HAR logging will capture these for future analysis.

### Trade-off: Async vs Sync
**Decision**: Use async (httpx.AsyncClient) for better performance
**Trade-off**: Requires async/await in user code; slightly more complex than sync
**Justification**: Modern Python best practice; aligns with other async providers in pymtg

### Trade-off: Full vs Minimal Implementation
**Decision**: Implement full feature set (search, decks, card management)
**Trade-off**: More code to maintain; longer initial implementation
**Justification**: Users expect full Archidekt functionality; partial implementation would be frustrating

## Migration Plan

### For Users of Current Archidekt Provider

**Breaking Changes**:
1. Authentication method changes from session-based to JWT-based
2. API endpoints updated to use `/api/` base path
3. Deck card operations now require different method signatures

**Migration Steps**:
```python
# Old (doesn't work with real API):
from pymtg.providers import Archidekt
archidekt = Archidekt(username="user", password="pass")
# Uses session cookies internally

# New (works with real API):
from pymtg.providers import Archidekt
archidekt = Archidekt()
archidekt.authenticate(username="user", password="pass")
# Uses JWT tokens internally
```

**No migration needed for**:
- Card search (method signatures unchanged)
- Basic deck retrieval (method signatures unchanged)
- Model usage (Card, Deck models unchanged)

### Deployment Strategy

1. **Phase 1**: Create new implementation in separate file (`archidekt_new.py`)
2. **Phase 2**: Test thoroughly with HAR-based mocks
3. **Phase 3**: Replace existing `archidekt.py` with new implementation
4. **Phase 4**: Update tests and documentation
5. **Phase 5**: Release as breaking change in changelog

**Rollback**: Keep old implementation in separate file temporarily; can revert by restoring old `archidekt.py`

## Open Questions

1. **Token Refresh**: Should we implement automatic token refresh when access_token expires? The HAR file shows both access_token and refresh_token are returned.
   - **Proposed**: Yes, implement refresh logic
   - **Alternative**: Let users handle token expiration manually

2. **Deck Card Model Extension**: Should we extend DeckCard to include Archidekt-specific fields like deckRelationId?
   - **Proposed**: Yes, but only if needed for core functionality
   - **Alternative**: Store mapping separately in provider

3. **HAR Logging Scope**: Should HAR logging be a provider-level feature or move to HTTP client level?
   - **Proposed**: Provider-level for now, can refactor later
   - **Alternative**: Add to base HTTPClient

4. **Format ID Mapping**: How should we handle Archidekt's numeric format IDs?
   - **Proposed**: Maintain mapping dictionary in provider
   - **Alternative**: Add to Format enum or create separate mapping

5. **Multi-tenant Rate Limiting**: How to handle rate limiting across multiple provider instances?
   - **Proposed**: Document that users should reuse provider instance or use external coordination
   - **Alternative**: Implement global rate limiter

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Archidekt Provider                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────┐ │
│  │ JWTAuthHandler    │    │ ArchidektClient   │    │RateLimiter│ │
│  │                  │    │ (httpx.Async)   │    │          │ │
│  │ - authenticate()  │◄──►│ - get()         │    │ - wait() │ │
│  │ - get_auth_header()│   │ - post()        │    │          │ │
│  │ - clear_auth()   │    │ - patch()       │    │          │ │
│  └──────────────────┘    └────────┬─────────┘    └──────────┘ │
│                                          │                      │
│                   ┌──────────────────────▼──────────────────┐ │
│                   │                Archidekt                 │ │
│                   │    (extends BaseProvider)                │ │
│                   ├──────────────────────────────────────────┤ │
│                   │ - search()                              │ │
│                   │ - search_syntax()                      │ │
│                   │ - get_card()                           │ │
│                   │ - get_deck()                           │ │
│                   │ - get_user_decks()                     │ │
│                   │ - create_deck()                        │ │
│                   │ - add_card_to_deck()                   │ │
│                   │ - remove_card_from_deck()              │ │
│                   │ - modify_card_in_deck()                 │ │
│                   │ - _parse_card()                         │ │
│                   │ - _parse_deck()                         │ │
│                   │ - enable_har_logging()                 │ │
│                   │ - export_har()                         │ │
│                   └──────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Pydantic Models                          │ │
│  │  - Card, Deck, DeckCard (from pymtg.models)                  │ │
│  │  - Archidekt-specific response parsers (internal)           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Archidekt API (https://archidekt.com/api/)        │
├─────────────────────────────────────────────────────────────────┤
│  /api/rest-auth/login/          POST  - JWT auth               │
│  /api/cards/v2/                  GET   - Card search             │
│  /api/decks/v2/                  POST  - Create deck             │
│  /api/decks/{id}/                GET   - Get deck                │
│  /api/decks/{id}/modifyCards/v2/ PATCH - Modify deck cards       │
│  /api/users/{id}/notificationCount/ GET - Notification count    │
└─────────────────────────────────────────────────────────────────┘
```
