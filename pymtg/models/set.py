"""Set model for Magic: The Gathering sets.

This module provides the Set model for representing Magic: The Gathering
sets in a normalized format across all providers.
"""

from pydantic import AnyUrl, Field

from pymtg.models.base import PyMTGBaseModel
from pymtg.models.enums import SetType


class Set(PyMTGBaseModel):
    """Normalized Magic: The Gathering set model.

    This model represents a Magic: The Gathering set in a normalized format
    that is consistent across all supported providers.

    Attributes:
        code: Set code (e.g., "LEA", "M20", "SNC").
        name: Full set name.
        set_type: Type of set (core, expansion, reprint, etc.).
        released_at: Date the set was released.
        block_code: Block code (if applicable).
        block_name: Block name (if applicable).
        parent_set_code: Parent set code (if applicable).
        card_count: Number of cards in the set.
        printed_size: Number of printed cards in the set.
        digital: Whether the set is digital-only.
        foil_only: Whether the set is foil-only.
        nonfoil_only: Whether the set is non-foil only.
        icon_svg_uri: URI to the set's icon SVG.
        search_uri: URI to search for cards in this set.
        scryfall_uri: URI to the set on Scryfall.
        uri: URI to the set on the provider's site.
        source: Provider name that provided this set data.
        mtgo_code: MTGO set code (if applicable).
        arena_code: Arena set code (if applicable).
        tcgplayer_id: TCGPlayer ID for the set.
        cardmarket_id: Cardmarket ID for the set.
    """

    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    set_type: SetType | None = None
    released_at: str | None = None
    block_code: str | None = None
    block_name: str | None = None
    parent_set_code: str | None = None
    card_count: int | None = None
    printed_size: int | None = None
    digital: bool | None = None
    foil_only: bool | None = None
    nonfoil_only: bool | None = None
    icon_svg_uri: AnyUrl | None = None
    search_uri: AnyUrl | None = None
    scryfall_uri: AnyUrl | None = None
    uri: AnyUrl | None = None
    source: str | None = None
    mtgo_code: str | None = None
    arena_code: str | None = None
    tcgplayer_id: int | None = None
    cardmarket_id: int | None = None
