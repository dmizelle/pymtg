## ADDED Requirements

### Requirement: All models SHALL inherit from PyMTGBaseModel
All normalized data models MUST inherit from a common base model (PyMTGBaseModel) that itself inherits from Pydantic BaseModel.

#### Scenario: Model inheritance
- **WHEN** Card model is defined
- **THEN** it inherits from PyMTGBaseModel which inherits from BaseModel

#### Scenario: Base model configuration
- **WHEN** PyMTGBaseModel is configured
- **THEN** it sets consistent Pydantic configuration for all models

---

### Requirement: Card model SHALL include core card fields
The Card model MUST include the minimum set of fields required for Card Lookup, Deck Aggregator, and Universal Search.

#### Scenario: Card with all core fields
- **WHEN** a Card is created with all required fields
- **THEN** system validates and creates the Card object successfully

#### Scenario: Card with missing optional fields
- **WHEN** a Card is created with only required fields
- **THEN** system creates the Card with optional fields as None

#### Scenario: Core fields validation
- **WHEN** Card model is validated
- **THEN** all core fields (id, scryfall_id, name, mana_cost, cmc, type_line, colors, color_identity) are present with appropriate types

---

### Requirement: Card model SHALL use Scryfall ID as canonical identifier
The Card model MUST include a scryfall_id field that serves as the canonical card identifier across all providers.

#### Scenario: Card from Scryfall
- **WHEN** Scryfall returns a card
- **THEN** the Card model has scryfall_id populated with the Scryfall UUID

#### Scenario: Card from Archidekt
- **WHEN** Archidekt returns a card
- **THEN** the Card model has scryfall_id populated if the Archidekt response includes a Scryfall ID, otherwise None

#### Scenario: Cross-provider card matching
- **WHEN** user has cards from different providers
- **THEN** user can match cards by comparing scryfall_id values

---

### Requirement: Card model SHALL normalize color representation
The Card model MUST normalize color representation using the Color enum consistently. The Color enum MUST support single colors, two-color combinations, three-color combinations, and five-color (WUBRG).

#### Scenario: Single letter colors
- **WHEN** Scryfall returns colors as ["U", "R"]
- **THEN** Card model normalizes to [Color.BLUE, Color.RED]

#### Scenario: Full name colors
- **WHEN** a provider returns colors as ["Blue", "Red"]
- **THEN** Card model normalizes to [Color.BLUE, Color.RED]

#### Scenario: Color identity normalization
- **WHEN** a provider returns color_identity
- **THEN** Card model normalizes to list of Color enum values

#### Scenario: Color combination enum values
- **WHEN** a card has Azorius colors
- **THEN** Color.AZORIUS can be used and has value "WU"

#### Scenario: Color from combination
- **WHEN** user calls Color.from_colors([Color.WHITE, Color.BLUE])
- **THEN** system returns Color.AZORIUS

#### Scenario: Color full name for combinations
- **WHEN** user accesses Color.AZORIUS.full_name
- **THEN** system returns "White Blue"

---

### Requirement: Card model SHALL include pricing field
The Card model MUST include a pricing field that contains provider-specific pricing information.

#### Scenario: Scryfall pricing
- **WHEN** Scryfall returns a card with pricing
- **THEN** Card.pricing.scryfall contains usd, eur, tix fields

#### Scenario: Multiple provider pricing
- **WHEN** a Card has pricing from multiple sources
- **THEN** Card.pricing contains populated fields for each available provider

#### Scenario: No pricing available
- **WHEN** a provider does not return pricing data
- **THEN** Card.pricing has all provider-specific pricing as None

---

### Requirement: Deck model SHALL include cards with counts
The Deck model MUST include a list of DeckCard objects, each containing a Card and a count.

#### Scenario: Deck with multiple cards
- **WHEN** a Deck is created with cards
- **THEN** deck.cards contains DeckCard objects with card and count fields

#### Scenario: DeckCard with count
- **WHEN** a deck contains 4 copies of a card
- **THEN** there is a DeckCard with card=Card(...) and count=4

#### Scenario: Empty deck
- **WHEN** a Deck has no cards
- **THEN** deck.cards is an empty list

---

### Requirement: Deck model SHALL support multiple boards
The Deck model MUST support multiple boards: main, sideboard, commander, maybeboard.

#### Scenario: Commander deck
- **WHEN** a Commander deck is retrieved
- **THEN** deck.commander contains the commander cards and deck.cards contains the main deck

#### Scenario: Standard deck with sideboard
- **WHEN** a Standard deck with sideboard is retrieved
- **THEN** deck.cards contains main deck cards and deck.sideboard contains sideboard cards

#### Scenario: Deck with maybeboard
- **WHEN** a deck with maybeboard is retrieved
- **THEN** deck.maybeboard contains the maybeboard cards

---

### Requirement: Deck model SHALL preserve source information
The Deck model MUST include source and source_id fields to track which provider the deck came from.

#### Scenario: Deck from Archidekt
- **WHEN** a deck is retrieved from Archidekt
- **THEN** deck.source = "archidekt" and deck.source_id = "12345"

#### Scenario: Deck from Moxfield
- **WHEN** a deck is retrieved from Moxfield
- **THEN** deck.source = "moxfield" and deck.source_id = "abc123"

---

### Requirement: Deck model SHALL include metadata
The Deck model MUST include metadata: name, description, format, created_at, updated_at, url.

#### Scenario: Deck with full metadata
- **WHEN** a deck is retrieved
- **THEN** deck.name, deck.description, deck.format, deck.created_at, deck.updated_at are populated

#### Scenario: Optional metadata fields
- **WHEN** a deck does not have description or url
- **THEN** those fields are None

#### Scenario: Format enum
- **WHEN** a deck has a format
- **THEN** deck.format is a Format enum value (e.g., Format.COMMANDER)

---

### Requirement: Pricing model SHALL be provider-specific
The Pricing model MUST use provider-specific sub-models for each provider's pricing data.

#### Scenario: Scryfall pricing fields
- **WHEN** Scryfall pricing is populated
- **THEN** pricing.scryfall has usd, usd_foil, eur, tix fields

#### Scenario: TCGPlayer pricing fields
- **WHEN** TCGPlayer pricing is populated
- **THEN** pricing.tcgplayer has market, mid, low, high, direct_low fields

#### Scenario: Cardmarket pricing fields
- **WHEN** Cardmarket pricing is populated
- **THEN** pricing.cardmarket has avg1, avg7, avg30, low, low_ex, trend fields

---

### Requirement: Search SHALL return all prints by default
When searching for cards, providers MUST return all available printings by default, matching Scryfall's behavior.

#### Scenario: Search for card with multiple prints
- **WHEN** user searches for "Lightning Bolt"
- **THEN** system returns all printings of Lightning Bolt (all sets where it appears)

#### Scenario: Distinct parameter
- **WHEN** user calls search() with distinct=True
- **THEN** system returns only one version of each card (by name or oracle_id)

#### Scenario: Normalization across providers
- **WHEN** a provider only returns latest prints by default
- **THEN** the adapter fetches and returns all prints to match the expected behavior

---

### Requirement: Model SHALL support serialization and deserialization
All models MUST support serialization to dict/JSON and deserialization from dict/JSON.

#### Scenario: Serialize Card to dict
- **WHEN** user calls card.model_dump()
- **THEN** system returns a dictionary representation of the Card

#### Scenario: Deserialize Card from dict
- **WHEN** user calls Card.model_validate(card_dict)
- **THEN** system returns a Card object

#### Scenario: Serialize to JSON
- **WHEN** user calls card.model_dump_json()
- **THEN** system returns a JSON string representation

---

### Requirement: Models SHALL normalize fuzzy matching across providers
All provider implementations MUST normalize fuzzy matching behavior so that searches produce consistent results regardless of the underlying provider's fuzzy matching algorithm.

#### Scenario: Fuzzy card name matching
- **WHEN** user searches for "Lighning Boltt" (misspelled)
- **THEN** system returns "Lightning Bolt" from all providers that support fuzzy matching

#### Scenario: Fuzzy matching with provider normalization
- **WHEN** a provider returns fuzzy matched results
- **THEN** Card names are normalized to their canonical form

#### Scenario: Fuzzy matching utility
- **WHEN** user needs to check if a name matches a card
- **THEN** system provides a centralized fuzzy matching utility

---

### Requirement: Pricing SHALL be eagerly loaded by default
The Card model's pricing field MUST be populated by default when cards are retrieved from providers that return pricing data.

#### Scenario: Card from Scryfall with pricing
- **WHEN** user retrieves a card from Scryfall
- **THEN** card.pricing.scryfall contains usd, eur, tix values (or None if not available)

#### Scenario: Card from provider without pricing
- **WHEN** user retrieves a card from a provider that doesn't return pricing
- **THEN** card.pricing has None for that provider's pricing field

#### Scenario: Eager loading default
- **WHEN** user calls search() or get_card()
- **THEN** pricing data is included by default without requiring additional calls

---

### Requirement: Model SHALL provide helper methods and properties
Models MUST include helper methods and properties for common operations.

#### Scenario: Color full names
- **WHEN** user accesses color.full_name
- **THEN** system returns "Blue" for Color.BLUE

#### Scenario: Color from full name
- **WHEN** user calls Color.from_full_name("Blue")
- **THEN** system returns Color.BLUE

#### Scenario: Card multicolor check
- **WHEN** user accesses card.is_multicolor
- **THEN** system returns True if len(card.color_identity) > 1

#### Scenario: Card color checks
- **WHEN** user accesses card.is_blue
- **THEN** system returns True if Color.BLUE in card.color_identity
