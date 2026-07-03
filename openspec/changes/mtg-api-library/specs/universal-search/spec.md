## ADDED Requirements

### Requirement: Universal search SHALL query multiple providers
The library MUST provide a universal search capability that queries multiple providers simultaneously and returns results organized by provider.

#### Scenario: Search across all providers
- **WHEN** user calls `aggregator.search("Black Lotus")` with all providers configured
- **THEN** system queries each provider and returns results in a dict keyed by provider name

#### Scenario: Search specific providers only
- **WHEN** user calls `aggregator.search("Black Lotus", sources=["scryfall", "archidekt"])`
- **THEN** system only queries Scryfall and Archidekt

#### Scenario: Provider returns error
- **WHEN** user calls `aggregator.search("Black Lotus")` and one provider is unavailable
- **THEN** system returns successful results from other providers and an error message for the unavailable provider

---

### Requirement: Universal search results SHALL be dict keyed by provider
The universal search aggregator MUST return results as a dictionary with provider names as keys and lists of Card objects (or error strings) as values.

#### Scenario: Successful search across providers
- **WHEN** user searches for "Black Lotus" across Scryfall and Archidekt
- **THEN** system returns `{"scryfall": [Card(...)], "archidekt": [Card(...)]}`

#### Scenario: Mixed success and failure
- **WHEN** Scryfall succeeds but Archidekt fails
- **THEN** system returns `{"scryfall": [Card(...)], "archidekt": "Error: rate limited"}`

#### Scenario: All providers fail
- **WHEN** all providers fail or return no results
- **THEN** system returns `{"scryfall": "Error: ...", "archidekt": "Error: ..."}` or empty lists

---

### Requirement: Universal search SHALL NOT deduplicate results
The universal search aggregator MUST NOT automatically deduplicate results across providers. Each provider's results SHALL be kept separate.

#### Scenario: Same card from multiple providers
- **WHEN** "Black Lotus" exists in both Scryfall and Archidekt
- **THEN** system returns the card in both provider result lists

#### Scenario: User wants deduplication
- **WHEN** user wants to deduplicate results
- **THEN** user can implement their own deduplication logic using the scryfall_id field

---

### Requirement: Universal search SHALL handle provider-specific query translation
The aggregator MUST translate unified query parameters into provider-specific queries where possible.

#### Scenario: Generic query to all providers
- **WHEN** user calls `aggregator.search(name="Black Lotus", colors=[Color.BLUE])`
- **THEN** system translates this to each provider's query format and executes

#### Scenario: Provider-specific query fallback
- **WHEN** a provider does not support a particular filter
- **THEN** system omits that filter for that provider (with warning) or uses the escape hatch

---

### Requirement: Aggregator SHALL accept provider instances
The universal search aggregator MUST accept provider client instances so it can work with authenticated providers.

#### Scenario: Aggregator with authenticated providers
- **WHEN** user creates an aggregator with authenticated Archidekt and Moxfield clients
- **THEN** system uses those authenticated sessions for searching

#### Scenario: Aggregator with mixed auth
- **WHEN** user creates an aggregator with Scryfall (no auth) and Archidekt (auth required)
- **THEN** system handles each provider's auth requirements appropriately

---

### Requirement: Aggregator SHALL support query syntax escape hatch
The universal search aggregator MUST support a syntax query that can be passed to all providers that support syntax-based search.

#### Scenario: Syntax query across providers
- **WHEN** user calls `aggregator.search_syntax("o:treasure ci:black")`
- **THEN** system passes this query string to each provider's search_syntax method

#### Scenario: Provider does not support syntax search
- **WHEN** a provider does not have a search_syntax method
- **THEN** system skips that provider or uses a fallback mechanism

---

### Requirement: Universal search SHALL respect rate limits per provider
The aggregator MUST respect each provider's rate limits independently when querying multiple providers simultaneously.

#### Scenario: Parallel queries with rate limits
- **WHEN** user searches across providers with different rate limits
- **THEN** system ensures each provider is queried within its rate limit constraints

#### Scenario: Rate limit exceeded on one provider
- **WHEN** one provider returns a rate limit error
- **THEN** system captures this error and returns it in the results dict without affecting other providers

---

### Requirement: Universal search SHALL provide timing information
The aggregator SHALL provide timing information for each provider's response to help users understand performance.

#### Scenario: Timed search results
- **WHEN** user searches across multiple providers
- **THEN** each provider's results include timing information (e.g., response_time_ms)

#### Scenario: Slow provider identification
- **WHEN** one provider is significantly slower than others
- **THEN** user can identify this from the timing information in the results

---

### Requirement: Aggregator SHALL be configurable
The universal search aggregator MUST allow configuration of search parameters per provider.

#### Scenario: Provider-specific limits
- **WHEN** user wants different page sizes for different providers
- **THEN** system allows configuration of provider-specific parameters

#### Scenario: Provider exclusion
- **WHEN** user wants to exclude certain providers from universal search
- **THEN** system allows configuration of which providers to include
