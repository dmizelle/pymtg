## ADDED Requirements

### Requirement: Provider SHALL support deck retrieval by ID
Deckbuilding providers that support deck retrieval (Archidekt, Moxfield) MUST implement a method to fetch a deck by its unique identifier. The method SHALL return a normalized Deck model containing normalized Card objects.

**Note:** Deckbox does not currently have a public API and is not included in v1.0 scope.

#### Scenario: Successful deck retrieval from Archidekt
- **WHEN** user calls `archidekt.get_deck("12345")`
- **THEN** system returns a Deck object with the deck's name, cards, commander, etc.

#### Scenario: Deck not found
- **WHEN** user calls `archidekt.get_deck("non-existent-id")`
- **THEN** system raises NotFoundError with resource_type="deck" and resource_id="non-existent-id"

#### Scenario: Private deck without authentication
- **WHEN** user calls `archidekt.get_deck("private-deck-id")` without authentication
- **THEN** system raises AuthenticationError or NotFoundError depending on provider behavior

---

### Requirement: Provider SHALL support listing user decks
Deckbuilding providers MUST implement a method to list all decks belonging to a specific user. The method SHALL return a list of minimal Deck information (ID, name, maybe description).

#### Scenario: List decks for authenticated user
- **WHEN** user calls `archidekt.get_user_decks()` with valid credentials
- **THEN** system returns a list of Deck objects (minimal info) for that user

#### Scenario: List decks for specific user
- **WHEN** user calls `archidekt.get_user_decks(username="player123")`
- **THEN** system returns a list of public decks for user "player123"

#### Scenario: User has no decks
- **WHEN** user calls `archidekt.get_user_decks()` for a user with no decks
- **THEN** system returns an empty list

---

### Requirement: Deck SHALL contain full Card objects
When a Deck is retrieved, it MUST contain full Card objects for each card in the deck (not just references or IDs). This follows the eager loading decision.

#### Scenario: Deck with cards
- **WHEN** user retrieves a deck
- **THEN** each card in `deck.cards` is a fully populated Card object with all available fields

#### Scenario: Deck card with count
- **WHEN** user retrieves a deck containing 4x Lightning Bolt
- **THEN** the Deck contains a DeckCard object with card=Card(name="Lightning Bolt", ...) and count=4

---

### Requirement: Deck SHALL support multiple boards
Deck objects MUST support multiple boards (main deck, sideboard, commander, maybeboard).

#### Scenario: Commander deck with multiple boards
- **WHEN** user retrieves a Commander deck from Archidekt
- **THEN** the Deck object has commander cards in the commander board and other cards in the main board

#### Scenario: Deck with sideboard
- **WHEN** user retrieves a Standard deck with a sideboard
- **THEN** the Deck object has cards in both main and sideboard boards

---

### Requirement: Deck SHALL preserve source information
Deck objects MUST preserve information about which provider and provider-specific ID they came from.

#### Scenario: Deck from Archidekt
- **WHEN** user retrieves a deck from Archidekt
- **THEN** the Deck object has source="archidekt" and source_id="12345"

#### Scenario: Cross-provider deck comparison
- **WHEN** user retrieves the same deck from multiple providers (if possible)
- **THEN** each Deck object can be identified as coming from its specific provider via the source field

---

### Requirement: Provider SHALL support deck metadata
Deck objects MUST include metadata about the deck: name, description, format, creation date, update date, etc.

#### Scenario: Deck with full metadata
- **WHEN** user retrieves a deck
- **THEN** the Deck object contains name, description (if available), format, created_at, updated_at

#### Scenario: Deck format identification
- **WHEN** user retrieves a Commander deck
- **THEN** the Deck object has format=Format.COMMANDER

---

### Requirement: Deck SHALL handle missing card data gracefully
If a deck contains cards that cannot be fully resolved (e.g., custom cards, tokens, cards not in provider's database), the provider SHALL handle this gracefully.

#### Scenario: Deck with unknown card
- **WHEN** a deck contains a card that the provider cannot resolve
- **THEN** the DeckCard has a card field with as much information as available (at minimum the name)

#### Scenario: Partial deck data
- **WHEN** a provider returns incomplete deck data
- **THEN** the Deck object contains all available data with missing fields as None

---

### Requirement: Deck search SHALL be supported where available
Providers that support deck search (by name, tags, etc.) MUST implement search functionality.

#### Scenario: Search decks by name
- **WHEN** user calls `archidekt.search_decks(name="Atraxa")`
- **THEN** system returns a list of decks with "Atraxa" in the name

#### Scenario: Search decks by tags
- **WHEN** user calls `archidekt.search_decks(tags=["competitive", "budget"])`
- **THEN** system returns a list of decks with those tags

---

### Requirement: Deck aggregation across providers SHALL be possible
The library SHALL provide a way to aggregate decks from multiple providers into a consistent format.

#### Scenario: Get decks from multiple providers
- **WHEN** user wants to retrieve their decks from both Archidekt and Moxfield
- **THEN** user can call each provider separately and receive Deck objects with the same structure

#### Scenario: Compare decks across providers
- **WHEN** user has decks on multiple platforms
- **THEN** the normalized Deck models allow for comparison and analysis regardless of source
