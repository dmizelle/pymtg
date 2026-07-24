# pymtg

![PyPI version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A unified Python interface to Magic: The Gathering APIs.

## Overview

`pymtg` provides a consistent, normalized interface to multiple Magic: The Gathering API providers including Scryfall, Archidekt, Moxfield, TCGPlayer, and Cardmarket. Instead of learning and maintaining separate integrations for each provider, you can use `pymtg` to access all of them through a single, unified API.

### Features

- **Unified Interface**: Same methods across all providers for consistent usage
- **Normalized Data Models**: Get the same `Card`, `Deck`, and `Pricing` objects regardless of the source
- **Provider Support**: Public APIs (Scryfall) and authenticated services
- **Type Safety**: Full type annotations and Pydantic models for reliable development
- **Error Handling**: Consistent exception hierarchy across all providers
- **Rate Limit Awareness**: Automatic respect for each provider's rate limits
- **Pagination Support**: Easy iteration through large result sets

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
| **Scryfall** | ✅ Implemented | None (Public API) | 2/sec search, 10/sec others |
| **Archidekt** | 🔄 Planned | Session Cookies | ~60/min |
| **Moxfield** | ✅ Implemented | Parse.bot API Key | ~100/min |
| **TCGPlayer** | 🔄 Planned | OAuth2 Client Credentials | 10/sec |
| **Cardmarket** | 🔄 Planned | OAuth 1.0a | 30K-100K/day |

**Note:** The Moxfield provider uses the [Parse.bot](https://parse.bot) third-party scraper service as its backend. You will need a Parse.bot API key to use this provider.

## Provider-Specific Usage

### Scryfall

Scryfall has a public API covering all cards, sets, and prices, and doesn't require authentication for most endpoints.

```python
import pymtg

scryfall = pymtg.Scryfall()

# All Scryfall methods are available immediately
card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")
cards = scryfall.search(name="Black Lotus")
```

## Data Models

### Card Model

The `Card` model provides normalized card data across all providers with extensive fields and helper methods.

### Pricing Model

```python
card = scryfall.get_card("some-card-id")

if card.pricing and card.pricing.scryfall:
    print(f"USD: ${card.pricing.scryfall.usd}")
    print(f"EUR: €{card.pricing.scryfall.eur}")
```

## Error Handling

`pymtg` provides a consistent exception hierarchy for error handling across all providers.

## Rate Limiting

Each provider has its own rate limits that are automatically tracked and accessible via `get_rate_limit_status()`.

## Project Structure

See the codebase for the full project structure including `auth/`, `models/`, `providers/`, `search/`, and `utils/` packages.

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/pymtg/pymtg.git
cd pymtg

# Install dependencies
uv sync

# Install in development mode
uv pip install -e .
```

### Running Tests

```bash
# Run specific test file
uv run python -m unittest tests.test_providers.test_scryfall -v
```

### Code Style

This project follows strict coding standards as defined in AGENTS.md.

## Contributing

Contributions are welcome! Please fork the repository and submit pull requests.

## License

This project is licensed under the MIT License.

## Support

- **Documentation**: See the [docs/](docs/) directory
- **Examples**: See the [docs/examples/](docs/examples/) directory

---

**pymtg v0.1.0** - A unified Python interface to Magic: The Gathering APIs.
