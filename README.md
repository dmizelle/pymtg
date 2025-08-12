
# PyMTG

A Python module for interacting with Magic: The Gathering APIs.

## Features

- Fetch card data from Scryfall, EDHREC, and Archidekt.
- Unified API for different services.

## Installation

```bash
pip install pymtg
```

## Usage

```python
from pymtg import ScryfallClient

client = ScryfallClient()
card = client.fetch_card("Black Lotus")
print(card)
```

## Development

```bash
pip install -e .[dev]
```

## License

MIT
