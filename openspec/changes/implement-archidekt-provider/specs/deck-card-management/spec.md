# Deck Card Management Specification

This specification defines the requirements for adding, removing, and modifying cards in decks for the Archidekt provider, based on reverse-engineered API analysis from the HAR file at `/tmp/archidekt.har`.

## ADDED Requirements

### Requirement: Provider SHALL support card modification via PATCH `/api/decks/{id}/modifyCards/v2/`

The Archidekt provider SHALL modify cards in a deck using PATCH requests to `/api/decks/{deck_id}/modifyCards/v2/` endpoint with a JSON body specifying the action and card details.

**Evidence from HAR file**:
- Entry #24 (add): `PATCH /api/decks/24299438/modifyCards/v2/`
- Entry #25 (remove): `PATCH /api/decks/24299438/modifyCards/v2/`
- Entry #28 (add): `PATCH /api/decks/24299438/modifyCards/v2/`
- Entry #30 (modify): `PATCH /api/decks/24299438/modifyCards/v2/`

#### Scenario: Add card to deck
- **WHEN** user adds card with ID 152606 to deck 24299438
- **THEN** provider makes PATCH request to `/api/decks/24299438/modifyCards/v2/`
- **AND** request body includes action: "add", cardid: "152606"
- **AND** request body includes modifications with quantity: 1
- **AND** request includes Authorization header with JWT token
- **AND** response confirms card was added

#### Scenario: Remove card from deck
- **WHEN** user removes card with ID 152606 from deck 24299438
- **THEN** provider makes PATCH request to `/api/decks/24299438/modifyCards/v2/`
- **AND** request body includes action: "remove", cardid: "152606"
- **AND** request body includes deckRelationId from previous add response
- **AND** response confirms card was removed

#### Scenario: Modify card quantity in deck
- **WHEN** user modifies card with ID 153286 in deck 24299438
- **THEN** provider makes PATCH request to `/api/decks/24299438/modifyCards/v2/`
- **AND** request body includes action: "modify", cardid: "153286"
- **AND** request body includes deckRelationId from add response
- **AND** response confirms card was modified

---

### Requirement: Provider SHALL use correct request body structure for card modifications

The PATCH request body SHALL contain a `cards` array with each card operation as an object containing action, card ID, categories, and modifications.

**Evidence from HAR file (Entry #24 request body)**:
```json
{
  "cards": [
    {
      "action": "add",
      "cardid": "152606",
      "customCardId": null,
      "categories": ["Ramp"],
      "patchId": "vefVNwJdd",
      "modifications": {
        "quantity": 1,
        "modifier": "Normal",
        "customCmc": null,
        "companion": false,
        "flippedDefault": false,
        "label": ",#656565"
      }
    }
  ]
}
```

#### Scenario: Add card with all required fields
- **WHEN** user adds card to deck
- **THEN** provider includes `action: "add"` in card object
- **AND** provider includes `cardid: "<card_id>"` (as string)
- **AND** provider includes `customCardId: null` (not using custom card)
- **AND** provider includes `categories` array (even if empty)
- **AND** provider includes `patchId` (unique identifier for this patch)
- **AND** provider includes `modifications` object with card details

#### Scenario: Remove card with deckRelationId
- **WHEN** user removes previously added card
- **AND** provider has deckRelationId from add response
- **THEN** provider includes `action: "remove"`
- **AND** provider includes `deckRelationId` from add response
- **AND** provider includes same cardid and patchId

#### Scenario: Modify card with updated quantity
- **WHEN** user modifies card quantity
- **THEN** provider includes `action: "modify"`
- **AND** provider includes `deckRelationId` from add response
- **AND** provider includes updated `modifications.quantity`

---

### Requirement: Provider SHALL handle modification response structure

The provider SHALL parse the response from PATCH `/api/decks/{id}/modifyCards/v2/` which returns information about the added/removed/modified cards and any created categories.

**Evidence from HAR file (Entry #24 response)**:
```json
{
  "add": [
    {
      "deckRelationId": 3259240809,
      "patchId": "vefVNwJdd",
      "categories": ["Ramp"],
      "quantity": 1,
      "modifier": "Normal",
      "customCmc": null,
      "companion": false,
      "flippedDefault": false,
      "label": ",#656565",
      "cardId": "152606",
      "createdAt": "2026-07-12T18:27:20.832140+00:00"
    }
  ],
  "createdCategories": [
    {
      "name": "Ramp",
      "id": 305380251,
      "includedInDeck": true,
      "includedInPrice": true,
      "isPremier": false
    }
  ]
}
```

#### Scenario: Parse add response with deckRelationId
- **WHEN** provider receives response from add card operation
- **THEN** provider extracts `add[0].deckRelationId` from response
- **AND** provider stores deckRelationId for future operations on this card
- **AND** provider extracts `add[0].cardId` to confirm card was added
- **AND** provider extracts `add[0].quantity` to confirm quantity

#### Scenario: Parse remove response
- **WHEN** provider receives response from remove card operation
- **THEN** provider confirms card was removed (response may be minimal or empty)
- **AND** provider removes card from local deck state

#### Scenario: Parse modify response
- **WHEN** provider receives response from modify card operation
- **THEN** provider confirms card was modified
- **AND** provider updates local deck state with new quantity/attributes

#### Scenario: Parse created categories
- **WHEN** provider receives response with `createdCategories`
- **THEN** provider extracts category information
- **AND** provider may store category IDs for future operations

---

### Requirement: Provider SHALL support modification actions

The provider SHALL support the three modification actions: add, remove, and modify.

#### Scenario: Action add - Add card to deck
- **WHEN** user wants to add a card to deck
- **THEN** provider uses action: "add"
- **AND** card is added to deck with specified quantity

#### Scenario: Action remove - Remove card from deck
- **WHEN** user wants to remove a card from deck
- **THEN** provider uses action: "remove"
- **AND** provider includes deckRelationId from add response
- **AND** card is removed from deck

#### Scenario: Action modify - Change card quantity or attributes
- **WHEN** user wants to change card quantity in deck
- **THEN** provider uses action: "modify"
- **AND** provider includes deckRelationId from add response
- **AND** provider updates quantity in modifications

---

### Requirement: Provider SHALL generate unique patchId for each modification

Each card modification operation SHALL include a unique `patchId` to identify the operation.

**Evidence from HAR file**:
- Entry #24: `patchId: "vefVNwJdd"`
- Entry #25: `patchId: "vefVNwJdd"` (same for remove of same card)
- Entry #28: `patchId: "akuLuc7UC6"` (different for new operation)

#### Scenario: Generate unique patchId
- **WHEN** provider creates card modification request
- **THEN** provider generates unique patchId string
- **AND** patchId is included in each card object in request

#### Scenario: Use same patchId for related operations
- **WHEN** provider removes a card that was just added
- **THEN** provider may reuse the same patchId from add operation
- **AND** provider includes deckRelationId from add response

---

### Requirement: Provider SHALL support modification parameters

The `modifications` object in card operations SHALL support various parameters for card customization.

**Evidence from HAR file**: All modify operations include:
- `quantity: 1`
- `modifier: "Normal"`
- `customCmc: null`
- `companion: false`
- `flippedDefault: false`
- `label: ",#656565"`

#### Scenario: Set card quantity
- **WHEN** user adds card with quantity 4
- **THEN** provider sets `modifications.quantity: 4`
- **AND** API adds 4 copies of the card

#### Scenario: Set card modifier to Foil
- **WHEN** user adds foil card
- **THEN** provider sets `modifications.modifier: "Foil"`
- **AND** API tracks card as foil version

#### Scenario: Set card as companion
- **WHEN** user adds companion card
- **THEN** provider sets `modifications.companion: true`

#### Scenario: Set custom CMC
- **WHEN** user overrides card CMC
- **THEN** provider sets `modifications.customCmc: <value>`
- **AND** API uses custom CMC instead of card's actual CMC

#### Scenario: Set label
- **WHEN** user sets card label
- **THEN** provider sets `modifications.label: "<label>"`

---

### Requirement: Provider SHALL support categories for cards

Each card operation SHALL include a `categories` array which categorizes the card in the deck (e.g., "Ramp", "Draw", "Removal").

**Evidence from HAR file**:
- Entry #24: `categories: ["Ramp"]`
- Response includes: `createdCategories: [{"name": "Ramp", "id": 305380251, ...}]`

#### Scenario: Add card with category
- **WHEN** user adds card with category "Ramp"
- **THEN** provider includes `categories: ["Ramp"]` in request
- **AND** if category doesn't exist, API creates it and returns in createdCategories

#### Scenario: Add card with multiple categories
- **WHEN** user adds card with multiple categories
- **THEN** provider includes `categories: ["Ramp", "Mana Fixing"]` in request

#### Scenario: Add card without category
- **WHEN** user adds card without specifying category
- **THEN** provider includes `categories: []` (empty array)

---

### Requirement: Provider SHALL handle card ID formats

The Archidekt API uses different ID types for cards:
- `cardid`: The printing ID (e.g., 152606 for Arcane Signet in MSC)
- `cardId`: The oracle card ID (e.g., 20089 for Arcane Signet)
- `deckRelationId`: Internal ID for the card-deck relationship (e.g., 3259240809)

**Evidence from HAR file**:
- Request: `cardid: "152606"` (printing ID as string)
- Response: `cardId: "152606"` and `deckRelationId: 3259240809`

#### Scenario: Use printing ID for add/remove
- **WHEN** user adds/removes card from deck
- **THEN** provider uses printing ID (e.g., 152606) as cardid
- **AND** cardid is sent as string in request

#### Scenario: Track deckRelationId for future operations
- **WHEN** provider adds card successfully
- **THEN** provider extracts deckRelationId from response
- **AND** provider stores deckRelationId for remove/modify operations

---

### Requirement: Provider SHALL require authentication for all card modifications

All card modification operations SHALL require authentication.

#### Scenario: Add card without authentication
- **WHEN** user attempts to add card to deck without authentication
- **THEN** provider raises `ArchidektAuthenticationError` before making request

#### Scenario: Remove card without authentication
- **WHEN** user attempts to remove card from deck without authentication
- **THEN** provider raises `ArchidektAuthenticationError` before making request

#### Scenario: Modify card without authentication
- **WHEN** user attempts to modify card in deck without authentication
- **THEN** provider raises `ArchidektAuthenticationError` before making request

---

### Requirement: Provider SHALL handle multiple card operations in single request

The API supports adding/removing/modifying multiple cards in a single PATCH request by including multiple card objects in the `cards` array.

#### Scenario: Add multiple cards in one request
- **WHEN** user adds 3 different cards to deck
- **THEN** provider creates single PATCH request with cards array of length 3
- **AND** each card object has its own action, cardid, patchId, and modifications

#### Scenario: Mixed operations in one request
- **WHEN** user adds 2 cards and removes 1 card in same operation
- **THEN** provider creates single PATCH request with 3 card objects
- **AND** first two cards have action: "add"
- **AND** third card has action: "remove" with deckRelationId

---

### Requirement: Provider SHALL support card lookup by name for add operations

For user convenience, the provider SHALL support adding cards by name, internally resolving the name to a card ID via the search endpoint.

#### Scenario: Add card by name
- **WHEN** user calls add_card with card_name="Sol Ring"
- **THEN** provider first searches for card by name
- **AND** provider resolves name to card printing ID
- **AND** provider uses resolved ID in modifyCards request

#### Scenario: Add card by name with foil
- **WHEN** user calls add_card with card_name="Sol Ring" and foil=True
- **THEN** provider resolves name to card ID
- **AND** provider sets modifications.modifier: "Foil"

#### Scenario: Add card by name not found
- **WHEN** user calls add_card with invalid card name
- **THEN** provider searches for card and finds no results
- **AND** provider raises `NotFoundError` with card name
