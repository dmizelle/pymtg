# pymtg

![PyPI version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A unified Python interface to Magic: The Gathering APIs.

## Overview

`pymtg` provides a consistent, normalized interface to multiple Magic: The Gathering API providers including Scryfall, Archidekt, Moxfield, TCGPlayer, and Cardmarket. Instead of learning and maintaining separate integrations for each provider, you can use `pymtg` to access all of them through a single, unified API.

### Features

- Unified interface: the same methods work across all providers
- Normalized data models: `Card`, `Deck`, and `Pricing` objects are identical regardless of source
- Provider support: public APIs (Scryfall) and authenticated services
- Type safety: full type annotations and Pydantic models
- Error handling: a single exception hierarchy across all providers
- Rate limit awareness: automatic respect for each provider's limits
- Pagination: `iter_search()` iterates through large result sets page by page

## Installation

```bash
uv pip install pymtg
```

Or if you're using `pip`:

```bash
pip install pymtg
```

## Quick Start

### Basic Usage

```python
import pymtg

# Create a provider instance
scryfall = pymtg.Scryfall()

# Get a specific card by Scryfall ID
card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")
print(f"{card.name}: {card.mana_cost}")

# Search for cards using generic parameters
cards = scryfall.search(name="Lotus", limit=5)
for card in cards:
    print(f"{card.name} ({card.set_name})")

# Use Scryfall's query syntax for advanced searches
blue_creatures = scryfall.search_syntax("c:U type:creature", limit=10)
for creature in blue_creatures:
    print(f"{creature.name} - {creature.type_line}")

# Get autocomplete suggestions
suggestions = scryfall.autocomplete("Ligh")
print(f"Suggestions: {suggestions}")

# Look up cards by name
black_lotus_printings = scryfall.get_cards_by_name("Black Lotus")
for printing in black_lotus_printings:
    print(f"{printing.set_name} - {printing.collector_number}")
```

### Working with Card Data

```python
import pymtg
from pymtg.models import Color

scryfall = pymtg.Scryfall()

# Get a card and access its properties
card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")

print(f"Name: {card.name}")
print(f"Mana Cost: {card.mana_cost}")
print(f"CMC: {card.cmc}")
print(f"Type: {card.type_line}")
print(f"Rarity: {card.rarity}")
print(f"Set: {card.set_name} ({card.set_code})")

# Access color information
if card.color_identity:
    print(f"Color Identity: {card.get_color_identity_string()}")

# Check card characteristics
print(f"Is Creature: {card.is_creature()}")
print(f"Is Blue: {card.is_blue()}")
print(f"Is Multicolor: {card.is_multicolor()}")

# Access pricing information
if card.pricing and card.pricing.scryfall:
    pricing = card.pricing.scryfall
    print(f"USD Price: ${pricing.usd or 'N/A'}")
    print(f"USD Foil Price: ${pricing.usd_foil or 'N/A'}")
```

### Using Generic Search Parameters

```python
import pymtg
from pymtg.models import Color, Rarity

scryfall = pymtg.Scryfall()

# Search by name and color
blue_cards = scryfall.search(
    name="Counter",
    colors=[Color.BLUE],
    limit=10
)

# Search by color identity
multicolor_cards = scryfall.search(
    identity=[Color.BLUE, Color.BLACK],
    limit=10
)

# Search by type
creatures = scryfall.search(
    type_line="Creature",
    limit=10
)

# Search by set
m20_cards = scryfall.search(
    set_code="M20",
    limit=10
)

# Search by rarity
mythic_cards = scryfall.search(
    rarity=Rarity.MYTHIC,
    limit=10
)

# Search by CMC range
mid_cmc_cards = scryfall.search(
    cmc={"gte": 3, "lte": 5},
    limit=10
)
```

### Pagination with iter_search

```python
import pymtg
from pymtg.models import Color

scryfall = pymtg.Scryfall()

# Iterate through all blue creatures
for card in scryfall.iter_search(
    colors=[Color.BLUE],
    type_line="Creature",
    limit=100,  # Maximum total results
    page_size=20   # Results per page
):
    print(f"{card.name} - {card.cmc} mana")
```

## Supported Providers

| Provider | Status | Authentication | Rate Limits |
| ---------- | -------- | ---------------- | ------------- |
| Scryfall | Implemented | None (public API) | 2/sec search, 10/sec others |
| Archidekt | Implemented | JWT | ~60/min |
| Moxfield | Wrapper (Parse.bot) | Parse.bot API key | ~100/min |
| TCGPlayer | Implemented | OAuth2 client credentials (user-supplied) | 10/sec |
| Cardmarket | Implemented | OAuth 1.0a (user-supplied) | 30K-100K/day |

Moxfield does not have a public API. The Moxfield provider routes all requests through [Parse.bot](https://parse.bot), a third-party scraper service. This means:

- You need a Parse.bot API key, not a Moxfield key.
- The base URL contains a scraper UUID (`api.parse.bot/scraper/{uuid}/`) that Parse.bot can revoke or rotate at any time.
- Rate limits and uptime depend on Parse.bot, not Moxfield.

If you need direct Moxfield access, you would have to reverse-engineer their private endpoints, which is fragile and may violate their terms of service.

## Provider-Specific Usage

### Scryfall

Scryfall has a public API covering all cards, sets, and prices. It does not require authentication.

```python
import pymtg

scryfall = pymtg.Scryfall()

card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")
cards = scryfall.search(name="Black Lotus")
```

### Archidekt

Archidekt uses JWT authentication. Pass your username and password to the constructor.

```python
import pymtg

archidekt = pymtg.Archidekt(
    username="your_username",
    password="your_password",
)

decks = archidekt.get_user_decks()
deck = archidekt.get_deck(deck_id="24299438")
cards = archidekt.search(name="Black Lotus", limit=5)
```

### Moxfield

Moxfield has no public API. The Moxfield provider routes all requests through [Parse.bot](https://parse.bot), a third-party scraper service. You need a Parse.bot API key, not a Moxfield key.

```python
import pymtg

moxfield = pymtg.Moxfield(api_key="your-parse-bot-key")

decks = moxfield.get_user_decks()
deck = moxfield.get_deck(deck_id="deck-uuid-here")
cards = moxfield.search(name="Black Lotus")
```

The base URL contains a scraper UUID (`api.parse.bot/scraper/{uuid}/`) that Parse.bot can revoke or rotate at any time. Rate limits and uptime depend on Parse.bot, not Moxfield. If you need direct Moxfield access, you would have to reverse-engineer their private endpoints, which is fragile and may violate their terms of service.

### TCGPlayer

TCGPlayer uses OAuth2 client credentials. Pass your own `client_id` and `client_secret` to the constructor. Authentication is lazy and happens on the first API call.

```python
import pymtg

tcgplayer = pymtg.TCGPlayer(
    client_id="your-client-id",
    client_secret="your-client-secret",
)

card = tcgplayer.get_card(card_id="12345", pricing=True)
cards = tcgplayer.search(name="Black Lotus", limit=5)
```

### Cardmarket

Cardmarket uses OAuth 1.0a. Pass your own consumer key, consumer secret, access token, and access token secret to the constructor.

```python
import pymtg

cardmarket = pymtg.Cardmarket(
    consumer_key="your-consumer-key",
    consumer_secret="your-consumer-secret",
    access_token="your-access-token",
    access_token_secret="your-access-token-secret",
)

card = cardmarket.get_card(card_id="12345")
cards = cardmarket.search(name="Black Lotus", limit=5)
```

OAuth1 does not support automatic token refresh. If the access token expires, obtain a new one from Cardmarket and re-instantiate the provider.

## Data Models

### Card Model

The `Card` model normalizes card data across all providers. It exposes fields like `name`, `mana_cost`, `cmc`, `type_line`, `rarity`, `set_name`, `set_code`, `color_identity`, and `pricing`, plus helper methods like `is_creature()`, `is_blue()`, and `is_multicolor()`.

```python
card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")

print(card.name)              # Black Lotus
print(card.mana_cost)         # {0}
print(card.cmc)              # 0
print(card.type_line)         # Artifact
print(card.rarity)           # rare
print(card.set_name)         # Beta
print(card.is_multicolor())  # False
```

### Pricing Model

Each `Card` has an optional `pricing` attribute with provider-specific price submodels. Scryfall prices are available without authentication; TCGPlayer and Cardmarket prices require their respective providers.

```python
card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")

if card.pricing and card.pricing.scryfall:
    print(f"USD: ${card.pricing.scryfall.usd}")
    print(f"EUR: €{card.pricing.scryfall.eur}")
```

## Error Handling

All providers raise the same exception hierarchy. The base exception is `PyMTGError`. Subclasses include `NotFoundError`, `RateLimitError`, `AuthenticationError`, `InvalidQueryError`, `APIError`, and `NetworkError`.

```python
import pymtg

scryfall = pymtg.Scryfall()

try:
    card = scryfall.get_card("invalid-id")
except pymtg.NotFoundError as e:
    print(f"Card not found: {e}")
except pymtg.RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
except pymtg.AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

## Rate Limiting

Each provider tracks its own rate limits internally. The library sleeps automatically to stay within limits. Call `get_rate_limit_status()` on any provider to inspect the current window.

```python
status = scryfall.get_rate_limit_status()
print(status)
```

## Development

### Setting Up a Development Environment

```bash
git clone https://github.com/dmizelle/pymtg.git
cd pymtg
uv sync
uv pip install -e .
```

### Running Tests

```bash
# Run the full suite
uv run pytest

# Run a single provider's tests
uv run pytest tests/test_providers/test_scryfall.py -v

# Run with coverage
uv run pytest --cov=pymtg
```

### Type Checking and Linting

```bash
uv run pyright pymtg/
uv run ruff check pymtg/
```

### Code Style

This project follows the coding standards defined in [AGENTS.md](AGENTS.md): Google-style docstrings on every module, class, and function; PEP 484 type annotations on all public APIs; and no `**kwargs` in function signatures.

## Contributing

Contributions are welcome. Fork the repository and open a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and workflow details.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Support

- Documentation: [docs/](docs/) directory
- Examples: [docs/examples/](docs/examples/) directory
