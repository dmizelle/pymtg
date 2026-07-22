## Why

The current Archidekt provider implementation uses session-based authentication with CSRF tokens, but the actual Archidekt API (as revealed by HAR file analysis) uses JWT Bearer token authentication via `/api/rest-auth/login/`. This mismatch prevents the provider from working with the real Archidekt API. Additionally, the current implementation references incorrect API endpoints and lacks support for deck card management operations that are critical for a complete Archidekt integration.

The HAR files provided at `/tmp/archidekt.har` and `/tmp/archidekt2.har` contain real API traffic that reveals the actual Archidekt API structure, including JWT authentication, card search endpoints, deck creation, card modification operations, and additional endpoints for card metadata, deck organization, social features, and realtime collaboration. This change implements a complete overhaul based on reverse-engineered API data.

## What Changes

- **BREAKING**: Replace SessionAuthHandler with JWT-based authentication for Archidekt
- **BREAKING**: Update API base URL from `https://archidekt.com` to `https://archidekt.com/api/`
- **BREAKING**: Change authentication endpoint from `/accounts/login/` to `/api/rest-auth/login/`
- **BREAKING**: Update card search from `/api/cards/` to `/api/cards/v2/` with proper query parameters
- Add support for deck card modification via `PATCH /api/decks/{id}/modifyCards/v2/`
- Add proper request/response parsing for Archidekt's card and deck data structures
- Add comprehensive error handling for Archidekt-specific API errors
- Add rate limiting support (60 requests per minute)
- Add HAR file export capability for debugging
- Update data models to match Archidekt's actual response structure
- Add complete test coverage with mock responses based on HAR file data
- Add support for card metadata endpoints (`/api/cards/editions/`, `/api/cards/subtypes/`)
- Add support for deck organization endpoints (`/api/decks/folders/{folder_id}/`, `/api/decks/tags/v2/`, `/api/decks/folders/deleteItems/`)
- Add support for social features endpoints (`/api/comments/{comment_id}/`, `/api/users/{user_id}/notificationCount/`)
- Add support for realtime collaboration WebSocket endpoint (`/api/ws/collaborative/{id}/`)

## Capabilities

### New Capabilities

- `jwt-authentication`: JWT Bearer token authentication with Archidekt's `/api/rest-auth/login/` endpoint, including token refresh and secure credential handling
- `card-search`: Search for cards using Archidekt's `/api/cards/v2/` endpoint with parameters like `nameSearch`, `oracleCardIds`, `formatLegality`, `colors`, `rarity`, and pagination support
- `deck-management`: Create and retrieve decks via `/api/decks/v2/` and `/api/decks/{id}/` endpoints with proper format and game parameters
- `deck-card-management`: Add, remove, and modify cards in decks via `PATCH /api/decks/{id}/modifyCards/v2/` with support for quantity, foil status, and categories
- `api-error-handling`: Consistent error handling for Archidekt-specific errors (401 Unauthorized, 403 Forbidden, 404 Not Found, 429 Rate Limited, 500 API Error)
- `rate-limiting`: Automatic rate limit tracking and retry logic for Archidekt's ~60 requests/minute limit
- `har-logging`: Optional HAR file logging for debugging and API traffic analysis
- `card-metadata`: Retrieve card editions and subtypes via `/api/cards/editions/` and `/api/cards/subtypes/` endpoints for filtering and validation
- `deck-organization`: Manage deck folders and tags via `/api/decks/folders/{folder_id}/`, `/api/decks/tags/v2/`, and `/api/decks/folders/deleteItems/` endpoints
- `social-features`: Access deck comments and user notifications via `/api/comments/{comment_id}/` and `/api/users/{user_id}/notificationCount/` endpoints
- `realtime-collaboration`: Establish WebSocket connections for collaborative editing via `/api/ws/collaborative/{id}/` endpoint

### Modified Capabilities

<!-- No existing capabilities to modify - this is a complete rewrite based on correct API understanding -->

## Impact

- **Files Modified**:
  - `pymtg/providers/archidekt.py` - Complete rewrite of provider implementation
  - `pymtg/providers/__init__.py` - Update provider registry
  
- **Files Added**:
  - `pymtg/auth/jwt.py` - New JWT authentication handler
  - `tests/providers/test_archidekt.py` - Comprehensive test suite with HAR-based mocks
  - `docs/providers/archidekt.md` - Updated provider documentation
  - `openspec/changes/implement-archidekt-provider/specs/card-metadata/spec.md` - Card editions and subtypes specification
  - `openspec/changes/implement-archidekt-provider/specs/deck-organization/spec.md` - Deck folders and tags specification
  - `openspec/changes/implement-archidekt-provider/specs/social-features/spec.md` - Comments and notifications specification
  - `openspec/changes/implement-archidekt-provider/specs/realtime-collaboration/spec.md` - WebSocket collaboration specification

- **Dependencies**: No new external dependencies required (uses existing httpx, pydantic)

- **API Changes**: All Archidekt API interactions will use the correct JWT-based authentication and v2 endpoints

- **Breaking Changes**: Users currently using the Archidekt provider will need to update their code to use the new authentication method (username/password → JWT tokens instead of session cookies)
