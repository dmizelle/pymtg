# Card Search Specification

This specification defines the card search requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR file at `/tmp/archidekt.har`.

## ADDED Requirements

### Requirement: Provider SHALL implement card search via `/api/cards/v2/` endpoint

The Archidekt provider SHALL search for cards using the `/api/cards/v2/` endpoint with GET requests. The endpoint SHALL accept various query parameters for filtering and sorting results.

**Evidence from HAR file**:
- Entry #15: `GET /api/cards/v2/?nameSearch=Myra&includeTokens&includeDigital&includeEmblems&includeArtCards&unique&`
- Entry #23: `GET /api/cards/v2/?nameSearch=sol%20ring&includeTokens&includeEmblems&unique&`
- Entry #26: `GET /api/cards/v2/?name=Arcane%20Signet&formatLegality=3&includeTokens&includeDigital&includeEmblems&includeArtCards&unique&game=1&colors=White,Blue,Black,Red,Green&orderBy=oracleCard__name&colorIdentity=true&rarity=common,uncommon,rare,mythic,special&page=1&`
- Entry #29: `GET /api/cards/v2/?exact&includeTokens&includeDigital&includeEmblems&includeArtCards&oracleCardIds=20089&game=1&orderBy=-editiondate&`

#### Scenario: Search by name fragment
- **WHEN** user searches with `nameSearch` parameter
- **AND** user provides partial card name like "Myra"
- **THEN** provider makes GET request to `/api/cards/v2/?nameSearch=Myra`
- **AND** provider includes `includeTokens`, `includeEmblems`, and `unique` flags
- **AND** response contains cards matching the name fragment

#### Scenario: Search by exact name
- **WHEN** user searches with `name` parameter
- **AND** user provides full card name like "Arcane Signet"
- **THEN** provider makes GET request with `name=Arcane%20Signet`
- **AND** response contains cards with exact name match

#### Scenario: Search with oracle card ID
- **WHEN** user searches with `oracleCardIds` parameter
- **AND** user provides specific oracle card ID like 20089
- **THEN** provider makes GET request with `oracleCardIds=20089`
- **AND** response contains all printings of the card with that oracle ID

---

### Requirement: Provider SHALL support pagination

The card search endpoint SHALL support pagination with `page` and `pageSize` parameters. The provider SHALL handle pagination automatically when iterating through results.

**Evidence from HAR file**:
- Entry #26: `...&page=1&`
- Response structure includes `count`, `next`, `previous`, `results` fields

#### Scenario: Paginated search with page parameter
- **WHEN** user requests page 2 of search results
- **AND** page size is 20
- **THEN** provider makes request with `page=2&pageSize=20`
- **AND** response contains 20 cards from page 2

#### Scenario: Pagination with next/previous URLs
- **WHEN** search returns more results than fit on one page
- **THEN** response includes `next` URL for next page
- **AND** response includes `previous` URL for previous page (null on first page)
- **AND** response includes `count` with total number of matching cards

#### Scenario: Empty search results
- **WHEN** search returns no matching cards
- **THEN** response contains `count: 0`
- **AND** response contains empty `results` array
- **AND** provider returns empty list

---

### Requirement: Provider SHALL support search query parameters

The provider SHALL support all documented search parameters from the Archidekt API, as discovered in the HAR file.

#### Scenario: Search with format legality filter
- **WHEN** user filters by format legality
- **AND** user specifies `formatLegality=3` (Commander)
- **THEN** provider includes `formatLegality=3` in request
- **AND** response contains only cards legal in Commander

#### Scenario: Search with color filter
- **WHEN** user filters by colors
- **AND** user specifies `colors=White,Blue,Black,Red,Green`
- **THEN** provider includes `colors=White,Blue,Black,Red,Green` in request
- **AND** response contains cards matching the color criteria

#### Scenario: Search with color identity filter
- **WHEN** user filters by color identity
- **AND** user specifies `colorIdentity=true`
- **THEN** provider includes `colorIdentity=true` in request
- **AND** response filters by color identity

#### Scenario: Search with rarity filter
- **WHEN** user filters by rarity
- **AND** user specifies `rarity=common,uncommon,rare,mythic,special`
- **THEN** provider includes `rarity=common,uncommon,rare,mythic,special` in request
- **AND** response contains cards of specified rarities

#### Scenario: Search with game filter
- **WHEN** user filters by game
- **AND** user specifies `game=1` (Magic: The Gathering)
- **THEN** provider includes `game=1` in request
- **AND** response contains only MTG cards

#### Scenario: Search with orderBy parameter
- **WHEN** user specifies sort order
- **AND** user specifies `orderBy=oracleCard__name`
- **THEN** provider includes `orderBy=oracleCard__name` in request
- **AND** response is sorted by card name

#### Scenario: Search with edition date ordering
- **WHEN** user specifies `orderBy=-editiondate`
- **THEN** provider includes `orderBy=-editiondate` in request
- **AND** response is sorted by edition date (newest first)

---

### Requirement: Provider SHALL support include flags

The provider SHALL support the various include flags for filtering card types and variants.

#### Scenario: Search with includeTokens flag
- **WHEN** user includes token cards in search
- **THEN** provider includes `includeTokens` flag in request
- **AND** response includes token cards

#### Scenario: Search with includeDigital flag
- **WHEN** user includes digital-only cards in search
- **THEN** provider includes `includeDigital` flag in request
- **AND** response includes digital printings

#### Scenario: Search with includeEmblems flag
- **WHEN** user includes emblem cards in search
- **THEN** provider includes `includeEmblems` flag in request
- **AND** response includes emblem cards

#### Scenario: Search with includeArtCards flag
- **WHEN** user includes art cards in search
- **THEN** provider includes `includeArtCards` flag in request
- **AND** response includes art cards

#### Scenario: Search with unique flag
- **WHEN** user wants only unique card entries (no duplicates)
- **THEN** provider includes `unique` flag in request
- **AND** response contains only one entry per unique card

---

### Requirement: Provider SHALL parse card search response structure

The provider SHALL parse the response from `/api/cards/v2/` and return normalized Card objects. The response structure from Archidekt contains nested data that must be properly extracted.

**Evidence from HAR file (Entry #26 response)**:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 152607,
      "artist": "Jason Smith",
      "collectorNumber": "191",
      "edition": {
        "editioncode": "msc",
        "editionname": "Marvel Super Heroes Commander",
        "editiondate": "2026-06-26",
        "editiontype": "commander"
      },
      "oracleCard": {
        "id": 20089,
        "name": "Arcane Signet",
        "manaCost": "{2}",
        "typeLine": "Artifact",
        "oracleText": "{T}: Add one mana of any color in your commander's color identity.",
        "colors": [],
        "colorIdentity": [],
        "cmc": 2,
        "layout": "normal",
        "legalities": { ... },
        "manaProduction": {"W": 1, "U": 1, "B": 1, "R": 1, "G": 1, "C": null}
      },
      "prices": {
        "tcg": 0.59,
        "tcgfoil": 0.0,
        "ck": 1.29,
        "ckfoil": 2.99,
        ...
      }
    }
  ]
}
```

#### Scenario: Parse card with oracleCard nested structure
- **WHEN** response contains card with nested `oracleCard` object
- **THEN** provider extracts `oracleCard.name` as card name
- **AND** provider extracts `oracleCard.manaCost` as mana cost
- **AND** provider extracts `oracleCard.typeLine` as type line
- **AND** provider extracts `oracleCard.oracleText` as oracle text
- **AND** provider extracts `oracleCard.cmc` as converted mana cost
- **AND** provider extracts `oracleCard.colors` as card colors
- **AND** provider extracts `oracleCard.colorIdentity` as color identity

#### Scenario: Parse edition information
- **WHEN** response contains card with nested `edition` object
- **THEN** provider extracts `edition.editioncode` as set code
- **AND** provider extracts `edition.editionname` as set name
- **AND** provider extracts `edition.editiondate` as set release date
- **AND** provider extracts `edition.editiontype` as set type

#### Scenario: Parse price information
- **WHEN** response contains card with nested `prices` object
- **THEN** provider extracts price data from various sources
- **AND** provider includes TCGPlayer, Card Kingdom, SCG, MTGO, and other prices
- **AND** provider normalizes price data into Pricing model

#### Scenario: Handle missing fields gracefully
- **WHEN** response contains card with missing optional fields
- **AND** fields like `flavor`, `artist`, or prices are null
- **THEN** provider sets those fields to None or appropriate defaults
- **AND** provider does not raise errors for missing optional fields

---

### Requirement: Provider SHALL support empty query parameters

The Archidekt API accepts empty values for flag parameters (e.g., `includeTokens&` without a value means true). The provider SHALL handle this correctly.

**Evidence from HAR file**: All search requests include flags like `&includeTokens&includeDigital&` without values.

#### Scenario: Empty flag parameter treated as true
- **WHEN** user makes search request with flag parameter and no value
- **THEN** provider includes parameter without value (e.g., `?includeTokens&`)
- **AND** API treats it as true

---

### Requirement: Provider SHALL handle special characters in search queries

The provider SHALL properly URL-encode search parameters, especially card names with spaces or special characters.

**Evidence from HAR file**:
- `nameSearch=sol%20ring` (Sol Ring with space encoded)
- `name=Arcane%20Signet` (Arcane Signet with space encoded)

#### Scenario: Search with spaces in card name
- **WHEN** user searches for "Sol Ring"
- **THEN** provider encodes name as `Sol%20Ring` in URL
- **AND** API receives correctly encoded request

#### Scenario: Search with special characters
- **WHEN** user searches for card with special characters
- **THEN** provider properly URL-encodes the query parameter
- **AND** API receives valid request

---

### Requirement: Provider SHALL support generic search parameters from BaseProvider

The provider SHALL map generic search parameters from `BaseProvider.search()` to Archidekt-specific query parameters.

#### Scenario: Map name parameter to nameSearch
- **WHEN** user calls search with `name="Black Lotus"`
- **THEN** provider maps to `nameSearch=Black%20Lotus`
- **AND** makes request to `/api/cards/v2/?nameSearch=Black%20Lotus`

#### Scenario: Map colors parameter to colors filter
- **WHEN** user calls search with `colors=[Color.BLUE, Color.RED]`
- **THEN** provider maps to `colors=Blue,Red`
- **AND** makes request with color filter

#### Scenario: Map color identity parameter
- **WHEN** user calls search with `identity=[Color.BLUE, Color.RED]`
- **THEN** provider includes `colorIdentity=true` in request
- **AND** provider maps colors to appropriate filter

#### Scenario: Map type_line parameter
- **WHEN** user calls search with `type_line="Creature"`
- **THEN** provider maps to appropriate Archidekt filter
- **AND** makes request with type filter

#### Scenario: Map rarity parameter
- **WHEN** user calls search with `rarity=Rarity.RARE`
- **THEN** provider maps to `rarity=rare`
- **AND** makes request with rarity filter
