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
    import os

    archidekt = Archidekt(
        username=os.getenv("ARCHIDEKT_USERNAME"),
        password=os.getenv("ARCHIDEKT_PASSWORD")
    )
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

from pymtg._version import __version__

__all__ = [
    # Version
    "__version__",
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
