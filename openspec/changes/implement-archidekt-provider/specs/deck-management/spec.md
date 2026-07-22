# Deck Management Specification

This specification defines the deck creation and retrieval requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR file at `/tmp/archidekt.har`.

## ADDED Requirements

### Requirement: Provider SHALL support deck creation via `/api/decks/v2/`

The Archidekt provider SHALL create decks using POST requests to `/api/decks/v2/` endpoint with proper authentication and request body.

**Evidence from HAR file (Entry #16)**:
```
POST /api/decks/v2/
Authorization: JWT <token>
Content-Type: application/json

{
  "name": "testing123",
  "deckFormat": 3,
  "edhBracket": null,
  "description": "",
  "featured": "",
  "playmat": "",
  "private": true,
  "unlisted": true,
  "theorycrafted": true,
  "game": 1,
  "parent_folder": 1735877,
  "cardPackage": null,
  "extras": {
    "decksToInclude": [],
    "commandersToAdd": [109768],
    "forceCardsToSingleton": false,
    "ignoreCardsOutOfCommanderIdentity": true
  }
}

Response (201 Created):
{
  "owner": { ... },
  "name": "testing123",
  "updatedAt": "2026-07-12T18:27:09.269631Z",
  "deckFormat": 3,
  "edhBracket": null,
  "id": 24299438,
  "colors": {"W": 0, "U": 1, "B": 0, "R": 1, "G": 0},
  ...
}
```

#### Scenario: Create deck with name and format
- **WHEN** user creates deck with name "My Deck" and format "commander"
- **THEN** provider POSTs to `/api/decks/v2/`
- **AND** request body includes `name: "My Deck"`
- **AND** request body includes `deckFormat: 3` (Commander format ID)
- **AND** request body includes `game: 1` (MTG game ID)
- **AND** request includes Authorization header with JWT token
- **AND** response contains created deck with ID

#### Scenario: Create deck with commanders
- **WHEN** user creates commander deck with specific commanders
- **AND** user specifies commander card IDs [109768]
- **THEN** provider includes `extras.commandersToAdd: [109768]` in request body
- **AND** created deck includes specified commanders

#### Scenario: Create deck with parent folder
- **WHEN** user creates deck in specific folder
- **AND** user specifies parent folder ID 1735877
- **THEN** provider includes `parent_folder: 1735877` in request body
- **AND** created deck is placed in specified folder

#### Scenario: Create private deck
- **WHEN** user creates private deck
- **THEN** provider includes `private: true` in request body
- **AND** created deck is not publicly visible

#### Scenario: Create deck without authentication
- **WHEN** user attempts to create deck without authentication
- **THEN** provider raises `ArchidektAuthenticationError` before making request

---

### Requirement: Provider SHALL support deck retrieval via `/api/decks/{id}/`

The Archidekt provider SHALL retrieve deck information using GET requests to `/api/decks/{deck_id}/` endpoint.

**Note**: The HAR file shows frontend uses Next.js data endpoints (`/_next/data/...`), but the actual API endpoint is `/api/decks/{id}/`.

#### Scenario: Retrieve deck by ID
- **WHEN** user requests deck with ID 24299438
- **THEN** provider makes GET request to `/api/decks/24299438/`
- **AND** request includes Authorization header with JWT token
- **AND** response contains deck data
- **AND** provider parses response into Deck object

#### Scenario: Retrieve non-existent deck
- **WHEN** user requests deck with non-existent ID
- **THEN** provider receives HTTP 404 response
- **AND** provider raises `NotFoundError` with deck ID

#### Scenario: Retrieve private deck without authentication
- **WHEN** user attempts to retrieve private deck without authentication
- **THEN** provider receives HTTP 401 or 403 response
- **AND** provider raises `AuthenticationError`

---

### Requirement: Provider SHALL parse deck response structure

The provider SHALL parse the response from `/api/decks/{id}/` and `/api/decks/v2/` (create) into normalized Deck objects.

**Evidence from HAR file (Entry #16 response - deck creation)**:
```json
{
  "owner": {
    "id": 1071357,
    "username": "phobos_pymtg",
    "avatar": "https://storage.googleapis.com/topdekt-user/avatars/default/avatar_colorless.svg",
    "moderator": false,
    "pledgeLevel": null,
    "roles": []
  },
  "name": "testing123",
  "updatedAt": "2026-07-12T18:27:09.269631Z",
  "deckFormat": 3,
  "edhBracket": null,
  "id": 24299438,
  "colors": {"W": 0, "U": 1, "B": 0, "R": 1, "G": 0},
  "featured": "https://storage.googleapis.com/archidekt-card-images/unf/5e57baea-00ee-49dc-80ce-a8c11a67a6db_art_crop.jpg",
  "customFeatured": "",
  "viewCount": 0,
  "private": true,
  "tags": [],
  "cardPackage": null,
  "unlisted": true,
  "theorycrafted": true,
  "game": 1,
  "hasPrimer": false
}
```

#### Scenario: Parse deck metadata
- **WHEN** provider receives deck response
- **THEN** provider extracts `id` as deck ID
- **AND** provider extracts `name` as deck name
- **AND** provider extracts `description` or uses empty string if null
- **AND** provider extracts `deckFormat` and maps to Format enum
- **AND** provider extracts `private` and maps to privacy setting

#### Scenario: Parse deck owner information
- **WHEN** provider receives deck response with owner object
- **THEN** provider extracts `owner.id` as owner ID
- **AND** provider extracts `owner.username` as owner name
- **AND** provider extracts `owner.avatar` as owner avatar URL

#### Scenario: Parse deck color information
- **WHEN** provider receives deck response with colors object
- **AND** colors object is `{"W": 0, "U": 1, "B": 0, "R": 1, "G": 0}`
- **THEN** provider extracts color identity from colors object
- **AND** provider creates Color enum list from colors with non-zero counts

#### Scenario: Parse deck timestamps
- **WHEN** provider receives deck response with timestamps
- **THEN** provider extracts `updatedAt` as updated_at
- **AND** provider extracts `createdAt` as created_at (if present)
- **AND** provider converts ISO 8601 strings to datetime objects

---

### Requirement: Provider SHALL map deck format IDs to Format enum

The provider SHALL map Archidekt's numeric format IDs to pymtg's Format enum.

**Known format IDs from HAR file**:
- 3 = Commander

#### Scenario: Map format ID 3 to COMMANDER
- **WHEN** provider receives deck with `deckFormat: 3`
- **THEN** provider maps to `Format.COMMANDER`

#### Scenario: Map format ID 2 to STANDARD
- **WHEN** provider receives deck with `deckFormat: 2`
- **THEN** provider maps to `Format.STANDARD`

#### Scenario: Handle unknown format ID
- **WHEN** provider receives deck with unknown format ID
- **THEN** provider maps to `Format.COMMANDER` as default
- **AND** provider logs warning about unknown format

---

### Requirement: Provider SHALL map game IDs to game types

The provider SHALL map Archidekt's numeric game IDs to game types.

**Known game IDs from HAR file**:
- 1 = Magic: The Gathering

#### Scenario: Map game ID 1 to MTG
- **WHEN** provider receives deck with `game: 1`
- **THEN** provider identifies it as Magic: The Gathering

---

### Requirement: Provider SHALL support deck cards in response

When retrieving a deck, the response may include the cards in the deck. The provider SHALL parse this card data into DeckCard objects.

**Note**: The HAR file does not show a complete deck retrieval with cards, but the API structure suggests cards are included in the deck object.

#### Scenario: Parse deck with cards
- **WHEN** provider receives deck response with `cards` array
- **THEN** provider iterates through cards array
- **AND** provider parses each card into DeckCard object
- **AND** provider includes cards in returned Deck object

#### Scenario: Parse deck without cards
- **WHEN** provider receives deck response without `cards` array
- **THEN** provider returns Deck object with empty cards list

---

### Requirement: Provider SHALL handle deck creation errors

The provider SHALL properly handle and communicate errors during deck creation.

#### Scenario: Invalid deck name (too long)
- **WHEN** user attempts to create deck with name longer than 100 characters
- **THEN** provider validates name length before making request
- **AND** provider raises `ValidationError` with appropriate message

#### Scenario: Invalid deck format
- **WHEN** user attempts to create deck with invalid format ID
- **THEN** provider receives HTTP 400 response
- **AND** provider raises `ValidationError` with API error message

#### Scenario: Unauthorized deck creation
- **WHEN** user attempts to create deck without authentication
- **THEN** provider raises `AuthenticationError` before making request

---

### Requirement: Provider SHALL get user decks

The provider SHALL support retrieving all decks for the authenticated user.

**Evidence from HAR file**: The frontend loads user data from `/_next/data/.../folders/1735877.json` which includes deck information, but the direct API endpoint would be `/api/decks/` or `/api/users/{id}/decks/`.

#### Scenario: Get all decks for authenticated user
- **WHEN** user calls get_user_decks() without user_id parameter
- **THEN** provider makes GET request to `/api/decks/`
- **AND** request includes Authorization header
- **AND** response contains list of decks for authenticated user
- **AND** provider parses response into list of Deck objects

#### Scenario: Get decks for specific user
- **WHEN** user calls get_user_decks(user_id=1071357)
- **THEN** provider makes GET request to `/api/users/1071357/decks/`
- **AND** response contains list of decks for specified user

#### Scenario: Empty deck list
- **WHEN** user has no decks
- **THEN** provider returns empty list
