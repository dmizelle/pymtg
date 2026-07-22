# Deck Organization Specification

This specification defines the deck organization requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR files at `/tmp/archidekt.har` and `/tmp/archidekt2.har`.

## ADDED Requirements

### Requirement: Provider SHALL implement deck folders endpoint

The Archidekt provider SHALL retrieve the contents of a deck folder using the `/api/decks/folders/{folder_id}/` endpoint with GET requests. This endpoint returns metadata about a folder including its subfolders and decks.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `GET /api/decks/folders/1735877/`
- Status: 200
- Response: JSON object with folder metadata and decks array
- Content-Type: application/json
- Content-Size: 853-810 bytes

#### Scenario: Retrieve folder contents
- **WHEN** user requests contents of a specific folder
- **AND** folder ID is 1735877
- **THEN** provider makes GET request to `/api/decks/folders/1735877/`
- **AND** provider includes JWT Authorization header
- **AND** response contains folder object with nested decks

#### Scenario: Folder object structure
- **WHEN** provider receives folder response
- **THEN** the folder object contains:
  - `id`: integer - folder ID
  - `name`: string - folder name (e.g., "Home")
  - `parentFolder`: object or null - reference to parent folder
  - `private`: boolean - whether folder is private
  - `owner`: object - owner user information
  - `subfolders`: array - nested folder objects
  - `decks`: array - deck objects in this folder

#### Scenario: Deck in folder structure
- **WHEN** provider receives decks in folder response
- **THEN** each deck object contains:
  - `id`: integer - deck ID
  - `name`: string - deck name
  - `size`: integer - number of cards in deck
  - `updatedAt`: string - last update timestamp
  - `createdAt`: string - creation timestamp
  - `deckFormat`: integer - format ID (1=Standard, 3=Commander, 5=Pioneer, etc.)
  - `private`: boolean - whether deck is private
  - `colors`: object - color counts (W, U, B, R, G)
  - `owner`: object - deck owner information
  - `parentFolderId`: integer - ID of parent folder

#### Scenario: Empty folder
- **WHEN** folder has no decks or subfolders
- **THEN** response contains empty `decks` and `subfolders` arrays
- **AND** provider returns empty lists for both

---

### Requirement: Provider SHALL implement deck tags endpoint

The Archidekt provider SHALL retrieve the list of all available deck tags using the `/api/decks/tags/v2/` endpoint with GET requests. This endpoint returns metadata about all available tags that users can apply to their decks.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `GET /api/decks/tags/v2/?q=`
- Status: 200
- Response: JSON array of tag objects
- Content-Type: application/json
- Content-Size: 13576 bytes

#### Scenario: Retrieve all deck tags
- **WHEN** user requests list of all available deck tags
- **THEN** provider makes GET request to `/api/decks/tags/v2/`
- **AND** provider includes JWT Authorization header
- **AND** response contains array of tag objects

#### Scenario: Tag object structure
- **WHEN** provider receives tags response
- **THEN** each tag object contains:
  - `id`: integer - tag ID
  - `name`: string - tag name (e.g., "+1/+1 Counters", "Aggro")
  - `aliases`: string - comma-separated alternative names
  - `description`: string - tag description
  - `created_at`: string - creation timestamp

#### Scenario: Search tags with query parameter
- **WHEN** user searches for tags matching a query
- **AND** user provides search term via `q` parameter
- **THEN** provider makes GET request with `q=<search_term>`
- **AND** response contains filtered list of matching tags

---

### Requirement: Provider SHALL implement folder delete items endpoint

The Archidekt provider SHALL remove decks from a folder using the `/api/decks/folders/deleteItems/` endpoint with POST requests. This endpoint accepts a list of items to delete from a folder.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `POST /api/decks/folders/deleteItems/`
- Status: 200
- Request body: `{"items": [{"id": 24299438, "type": "deck"}]}`
- Response: `{"status": "success"}`
- Content-Type: application/json

#### Scenario: Remove single deck from folder
- **WHEN** user removes a deck from a folder
- **AND** deck ID is 24299438
- **THEN** provider makes POST request to `/api/decks/folders/deleteItems/`
- **AND** provider includes JWT Authorization header
- **AND** request body contains `{"items": [{"id": 24299438, "type": "deck"}]}`
- **AND** response contains `{"status": "success"}`

#### Scenario: Remove multiple decks from folder
- **WHEN** user removes multiple decks from a folder
- **AND** deck IDs are 24299438 and 24307454
- **THEN** provider makes POST request with items array
- **AND** request body contains `{"items": [{"id": 24299438, "type": "deck"}, {"id": 24307454, "type": "deck"}]}`
- **AND** response contains `{"status": "success"}`

#### Scenario: Handle deletion error
- **WHEN** deletion fails (e.g., deck not in folder)
- **THEN** provider receives error response
- **AND** provider raises appropriate exception with error details
