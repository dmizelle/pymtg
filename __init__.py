



"""
A Python module for interacting with Magic: The Gathering APIs.

This module provides a unified interface for interacting with various Magic: The Gathering APIs.
"""

from .card import Card
from .scryfall import ScryfallClient, CardNotFoundError

__all__ = ["Card", "ScryfallClient", "CardNotFoundError"]


