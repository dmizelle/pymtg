"""pymtg - A Python library providing a unified interface to Magic: The Gathering APIs.

This library provides a consistent interface and normalized data models
across multiple MTG API providers including Scryfall, Archidekt, Moxfield,
TCGPlayer, and Cardmarket.

Typical usage example:

    from pymtg import Scryfall

    scryfall = Scryfall()
    cards = scryfall.search(name="Black Lotus", limit=1)
    for card in cards:
        print(card.name, card.mana_cost)

Or with authenticated providers:

    from pymtg import Archidekt

    archidekt = Archidekt(username="your_username", password="your_password")
    decks = archidekt.get_user_decks()
    for deck in decks:
        print(deck.name)
"""

# Providers
from pymtg.providers import (
    Archidekt,
    BaseProvider,
    Cardmarket,
    Moxfield,
    Scryfall,
    TCGPlayer,
)

# Models
from pymtg.models import (
    Board,
    Card,
    Color,
    Deck,
    DeckCard,
    Format,
    Pricing,
    Rarity,
    Set,
    SetType,
)

# Search
from pymtg.search import Aggregator

# Exceptions
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
    PyMTGError,
    RateLimitError,
)

__all__ = [
    # Providers
    "Archidekt",
    "BaseProvider",
    "Cardmarket",
    "Moxfield",
    "Scryfall",
    "TCGPlayer",
    # Models
    "Board",
    "Card",
    "Color",
    "Deck",
    "DeckCard",
    "Format",
    "Pricing",
    "Rarity",
    "Set",
    "SetType",
    # Search
    "Aggregator",
    # Exceptions
    "APIError",
    "AuthenticationError",
    "InvalidQueryError",
    "NetworkError",
    "NotFoundError",
    "PyMTGError",
    "RateLimitError",
]

__version__ = "0.1.0"
