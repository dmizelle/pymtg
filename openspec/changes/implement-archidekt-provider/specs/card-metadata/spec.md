# Card Metadata Specification

This specification defines the card metadata requirements for the Archidekt provider, based on reverse-engineered API analysis from the HAR files at `/tmp/archidekt.har` and `/tmp/archidekt2.har`.

## ADDED Requirements

### Requirement: Provider SHALL implement editions endpoint

The Archidekt provider SHALL retrieve the list of all Magic: The Gathering editions/sets using the `/api/cards/editions/` endpoint with GET requests. This endpoint returns metadata about all available sets that can be used for filtering card searches.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `GET /api/cards/editions/`
- Status: 200
- Response: JSON array of 1000+ edition objects
- Content-Type: application/json
- Content-Size: 15258 bytes

#### Scenario: Retrieve all editions
- **WHEN** user requests list of all MTG sets
- **THEN** provider makes GET request to `/api/cards/editions/`
- **AND** provider includes JWT Authorization header
- **AND** response contains array of edition objects

#### Scenario: Edition object structure
- **WHEN** provider receives editions response
- **THEN** each edition object contains:
  - `editioncode`: string - short code for the set (e.g., "trc", "fra")
  - `editionname`: string - full name of the set
  - `editiondate`: string - release date in YYYY-MM-DD format
  - `editiontype`: string - type of set (e.g., "expansion", "commander", "promo", "memorabilia")
  - `mtgoCode`: string or null - MTG Online code

#### Scenario: Handle large response
- **WHEN** editions endpoint returns large payload (15KB+)
- **THEN** provider successfully parses and caches the response
- **AND** provider makes the data available for set filtering operations

---

### Requirement: Provider SHALL implement subtypes endpoint

The Archidekt provider SHALL retrieve the list of all Magic: The Gathering card subtypes using the `/api/cards/subtypes/` endpoint with GET requests. This endpoint returns metadata about all available subtypes that can be used for filtering card searches.

**Evidence from HAR file `/tmp/archidekt2.har`**:
- Entry: `GET /api/cards/subtypes/`
- Status: 200
- Response: JSON array of subtype strings
- Content-Type: application/json
- Content-Size: 3614 bytes

#### Scenario: Retrieve all subtypes
- **WHEN** user requests list of all card subtypes
- **THEN** provider makes GET request to `/api/cards/subtypes/`
- **AND** provider includes JWT Authorization header
- **AND** response contains array of subtype objects

#### Scenario: Subtype object structure
- **WHEN** provider receives subtypes response
- **THEN** each subtype object contains:
  - `subtypename`: string - the name of the subtype (e.g., "Angel", "Zombie", "Advisor")

#### Scenario: Use subtypes for filtering
- **WHEN** user searches for cards with subtype filter
- **AND** user specifies subtype like "Angel"
- **THEN** provider can validate the subtype against the subtypes list
- **AND** provider includes appropriate filter in card search request
