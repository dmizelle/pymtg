# PyMTG Documentation

Welcome to PyMTG - A unified Python library for Magic: The Gathering APIs.

## Overview

PyMTG provides a normalized interface to multiple MTG API providers, including:

- **Scryfall** - Card database with free public API
- **Archidekt** - Deck building and collection management
- **Moxfield** - Deck building (via Parse.bot wrapper)
- **TCGPlayer** - Marketplace data and pricing (requires approval)
- **Cardmarket** - European marketplace (requires approval)

## Installation

```bash
uv pip install pymtg
```

Or with pip:

```bash
pip install pymtg
```

## Quick Start

### Basic Card Search

```python
from pymtg import Scryfall

# Initialize provider
scryfall = Scryfall()

# Get a card by ID
card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")
print(card.name)  # Black Lotus

# Search for cards
cards = scryfall.search(name="Black Lotus", limit=5)
for card in cards:
    print(card.name, card.set_name)

# Use Scryfall query syntax
blue_creatures = scryfall.search_syntax("c:U type:creature", limit=10)
```

### Deck Aggregation

```python
from pymtg.search import Aggregator

# Create aggregator with providers
aggregator = Aggregator([scryfall])

# Search across all providers
results = aggregator.search(name="Black Lotus", limit=5)
print(results)  # dict keyed by provider name
```

## Features

- **Normalized Data Models** - Consistent Card, Deck, and Pricing models across all providers
- **Provider Abstraction** - Unified interface for search, card retrieval, and deck operations
- **Rate Limit Handling** - Built-in rate limit tracking and respect
- **Error Handling** - Consistent exception hierarchy for API errors
- **Type Safety** - Full type annotations with Pydantic models

## Providers

### Scryfall

No authentication required. Free public API.

```python
from pymtg import Scryfall

scryfall = Scryfall()
card = scryfall.get_card("scryfall-uuid-here")
```

### Archidekt

Requires username/password authentication.

```python
from pymtg import Archidekt

archidekt = Archidekt(username="your_username", password="your_password")
archidekt.authenticate()

# Get your decks
decks = archidekt.get_user_decks()

# Get a specific deck
deck = archidekt.get_deck(deck_id=12345)
```

### Moxfield (via Parse.bot)

Requires Parse.bot API key.

```python
from pymtg import Moxfield

moxfield = Moxfield(api_key="your-parse-bot-key")

# Get decks
decks = moxfield.get_user_decks()

# Search cards
cards = moxfield.search(name="Black Lotus")
```

### TCGPlayer

Requires approved developer application.

```python
from pymtg import TCGPlayer

tcgplayer = TCGPlayer(
    client_id="your-client-id",
    client_secret="your-client-secret"
)
tcgplayer.authenticate()

# Get card with pricing
card = tcgplayer.get_card(product_id=12345, include="pricing")
print(card.pricing)  # Pricing information
```

### Cardmarket

Requires approved developer application.

```python
from pymtg import Cardmarket

cardmarket = Cardmarket(
    client_id="your-client-id",
    client_secret="your-client-secret"
)
cardmarket.authenticate()

# Search cards
cards = cardmarket.search(name="Black Lotus")
```

## Error Handling

```python
from pymtg.exceptions import NotFoundError, RateLimitError, AuthenticationError

try:
    card = scryfall.get_card("fake-id")
except NotFoundError as e:
    print(f"Card not found: {e}")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

## Rate Limiting

Each provider has built-in rate limit tracking:

- **Scryfall**: 2 requests/sec for search, 10 requests/sec for other endpoints
- **Archidekt**: ~60 requests/minute
- **TCGPlayer**: 10 requests/second
- **Cardmarket**: 30K-100K requests/day

The library automatically tracks and respects these limits.

## Examples

See the [examples directory](./examples/) for complete usage examples:

- [basic_search.py](./examples/basic_search.py) - Basic search operations
- [deck_retrieval.py](./examples/deck_retrieval.py) - Deck retrieval and parsing


## Contributing

See CONTRIBUTING.md in the repository root for contribution guidelines.

## License

This project is licensed under the MIT License - see LICENSE in the repository root for details.
