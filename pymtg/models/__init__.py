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
    "PyMTGBaseModel",
    "Card",
    "CardFace",
    "DeckCard",
    "Deck",
    "Board",
    "Color",
    "Format",
    "Rarity",
    "SetType",
    "Pricing",
    "ScryfallPricing",
    "TCGPlayerPricing",
    "CardmarketPricing",
    "Set",
]
