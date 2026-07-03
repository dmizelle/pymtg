"""Provider implementations for various MTG API providers.

Each provider module implements a consistent interface through the BaseProvider
class, allowing users to interact with different MTG APIs in a unified way.
"""

from pymtg.providers.archidekt import Archidekt
from pymtg.providers.base import BaseProvider
from pymtg.providers.cardmarket import Cardmarket
from pymtg.providers.moxfield import Moxfield
from pymtg.providers.scryfall import Scryfall
from pymtg.providers.tcgplayer import TCGPlayer

__all__ = [
    "Archidekt",
    "BaseProvider",
    "Cardmarket",
    "Moxfield",
    "Scryfall",
    "TCGPlayer",
]
