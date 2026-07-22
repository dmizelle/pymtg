"""Normalized data models for Magic: The Gathering card and deck data.

This module contains Pydantic models that provide a consistent interface
across all MTG API providers.
"""

from pymtg.models.base import PyMTGBaseModel
from pymtg.models.card import Card, CardFace, DeckCard
from pymtg.models.deck import Deck
from pymtg.models.enums import Board, Color, Format, Rarity, SetType
from pymtg.models.pricing import (
    CardmarketPricing,
    Pricing,
    ScryfallPricing,
    TCGPlayerPricing,
)
from pymtg.models.set import Set

__all__ = [
    # pymtg.models.base
    "PyMTGBaseModel",
    # pymtg.models.card
    "Card",
    "CardFace",
    "DeckCard",
    # pymtg.models.deck
    "Deck",
    # pymtg.models.enums
    "Board",
    "Color",
    "Format",
    "Rarity",
    "SetType",
    # pymtg.models.pricing
    "Pricing",
    "ScryfallPricing",
    "TCGPlayerPricing",
    "CardmarketPricing",
    # pymtg.models.set
    "Set",
]
