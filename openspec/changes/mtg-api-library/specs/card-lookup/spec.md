## ADDED Requirements

### Requirement: Provider SHALL support card lookup by ID
Each provider MUST implement a method to fetch a single card by its unique identifier. The method SHALL return a normalized Card model.

#### Scenario: Successful card lookup by Scryfall ID
- **WHEN** user calls `scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")`
- **THEN** system returns a Card object with name "Black Lotus"

#### Scenario: Card not found by ID
- **WHEN** user calls `scryfall.get_card("non-existent-id")`
- **THEN** system raises NotFoundError with resource_type="card" and resource_id="non-existent-id"

#### Scenario: Invalid ID format
- **WHEN** user calls `scryfall.get_card("invalid-id-format")`
- **THEN** system raises InvalidQueryError with the invalid ID

---

### Requirement: Provider SHALL support card lookup by name
Each provider MUST implement a method to search for cards by name. The method SHALL return a list of normalized Card models.

#### Scenario: Exact name match
- **WHEN** user calls `scryfall.search(name="Black Lotus")`
- **THEN** system returns a list containing the Black Lotus card

#### Scenario: Partial name match
- **WHEN** user calls `scryfall.search(name="Lotus")`
- **THEN** system returns a list of all cards with "Lotus" in the name

#### Scenario: No cards found by name
- **WHEN** user calls `scryfall.search(name="NonExistentCard12345")`
- **THEN** system returns an empty list

---

### Requirement: Provider SHALL support card search with filters
Each provider MUST implement a method to search for cards with various filters. The method SHALL accept filter parameters and return matching normalized Card models.

#### Scenario: Filter by color identity
- **WHEN** user calls `scryfall.search(identity=[Color.BLUE, Color.BLACK])`
- **THEN** system returns a list of cards with blue and/or black in their color identity

#### Scenario: Filter by card type
- **WHEN** user calls `scryfall.search(type_line="Creature")`
- **THEN** system returns a list of creature cards

#### Scenario: Filter by mana cost
- **WHEN** user calls `scryfall.search(cmc={"gte": 3, "lte": 5})`
- **THEN** system returns a list of cards with converted mana cost between 3 and 5 inclusive

#### Scenario: Filter by set
- **WHEN** user calls `scryfall.search(set_code="M20")`
- **THEN** system returns a list of cards from the M20 set

#### Scenario: Combine multiple filters
- **WHEN** user calls `scryfall.search(name="Bolt", colors=[Color.RED], type_line="Instant")`
- **THEN** system returns a list of red instant cards with "Bolt" in the name

---

### Requirement: Provider SHALL support card name autocompletion
Each provider SHALL implement a method to provide card name suggestions based on a partial name. The method SHALL return a list of matching card names.

#### Scenario: Autocomplete with partial name
- **WHEN** user calls `scryfall.autocomplete("Ligh")`
- **THEN** system returns a list of card names starting with "Ligh" including "Lightning Bolt", "Lightning Greaves", etc.

#### Scenario: Autocomplete with minimum characters
- **WHEN** user calls `scryfall.autocomplete("B")`
- **THEN** system returns a list of card names starting with "B"

#### Scenario: Autocomplete with no matches
- **WHEN** user calls `scryfall.autocomplete("xyzabc123")`
- **THEN** system returns an empty list

---

### Requirement: Provider SHALL support syntax-based card search
Each provider SHALL implement a `search_syntax()` method that accepts provider-specific query syntax strings. This provides an escape hatch for advanced queries not supported by the generic search parameters.

#### Scenario: Scryfall syntax query
- **WHEN** user calls `scryfall.search_syntax("c:U type:creature pow>=3")`
- **THEN** system returns a list of blue creatures with power 3 or greater

#### Scenario: Archidekt syntax query
- **WHEN** user calls `archidekt.search_syntax("o:treasure ci:black")`
- **THEN** system returns a list of black cards with "treasure" in the oracle text

#### Scenario: Invalid syntax query
- **WHEN** user calls `scryfall.search_syntax("invalid syntax !!!")`
- **THEN** system raises InvalidQueryError with the invalid query string

---

### Requirement: Card search SHALL support pagination
Each provider's search methods MUST support pagination for large result sets. The method SHALL allow users to retrieve results in pages or using cursors.

#### Scenario: Paginate using page number
- **WHEN** user calls `scryfall.search(name="Creature", page=1, page_size=100)`
- **THEN** system returns the first 100 creature cards
- **WHEN** user calls `scryfall.search(name="Creature", page=2, page_size=100)`
- **THEN** system returns the next 100 creature cards

#### Scenario: Paginate using cursor
- **WHEN** user calls `scryfall.search(name="Creature", limit=100)` and receives a response with `has_more=True`
- **THEN** system provides a cursor that can be used to fetch the next page

#### Scenario: Exhaustive pagination
- **WHEN** user iterates through all pages of a search result
- **THEN** system returns all matching cards without duplicates

---

### Requirement: Card objects SHALL include pricing information
When available from the provider, Card objects MUST include pricing information in the normalized format. Pricing SHALL be eagerly loaded.

#### Scenario: Scryfall card with pricing
- **WHEN** user calls `scryfall.get_card("black-lotus-id")`
- **THEN** the returned Card object has a Pricing field with scryfall.usd, scryfall.eur, etc. populated

#### Scenario: Provider without pricing data
- **WHEN** user calls a provider that does not provide pricing data
- **THEN** the returned Card object has a Pricing field with all provider-specific pricing as None

---

### Requirement: Search results SHALL be consistent across providers
When the same query is executed against multiple providers, the returned Card objects SHALL have the same structure and field names, even if the underlying data comes from different sources.

#### Scenario: Same card from different providers
- **WHEN** user calls `scryfall.get_card("id1")` and `archidekt.get_card("id2")` for the same card
- **THEN** both return Card objects with the same fields (name, mana_cost, etc.) even though the IDs differ

#### Scenario: Normalized color representation
- **WHEN** Scryfall returns colors as ["U", "R"] and Archidekt returns colors as ["Blue", "Red"]
- **THEN** both are normalized to [Color.BLUE, Color.RED] in the Card object
