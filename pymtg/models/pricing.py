"""Pricing models for Magic: The Gathering cards.

This module provides normalized pricing models for different MTG API providers,
allowing for consistent access to pricing information across all providers.
Each provider has its own pricing model with provider-specific fields.
"""

from pymtg.models.base import PyMTGBaseModel


class ScryfallPricing(PyMTGBaseModel):
    """Pricing information from Scryfall.

    Scryfall provides pricing in multiple currencies and for different
    print variations (normal, foil, etched).

    Attributes:
        usd: Price in US dollars for normal prints.
        usd_foil: Price in US dollars for foil prints.
        usd_etched: Price in US dollars for etched foil prints.
        eur: Price in Euros for normal prints.
        eur_foil: Price in Euros for foil prints.
        tix: Price in MTGO tix.
    """

    usd: float | None = None
    usd_foil: float | None = None
    usd_etched: float | None = None
    eur: float | None = None
    eur_foil: float | None = None
    tix: float | None = None


class TCGPlayerPricing(PyMTGBaseModel):
    """Pricing information from TCGPlayer.

    TCGPlayer provides various pricing metrics including market price,
    mid price, low/high prices, direct low price, and condition-specific prices.

    Attributes:
        market: Market price.
        mid: Mid price.
        low: Low price.
        high: High price.
        direct_low: Direct low price.
        near_mint: Price for Near Mint condition.
        good: Price for Good condition.
        excellent: Price for Excellent condition.
        very_good: Price for Very Good condition.
        fair: Price for Fair condition.
        poor: Price for Poor condition.
    """

    market: float | None = None
    mid: float | None = None
    low: float | None = None
    high: float | None = None
    direct_low: float | None = None
    near_mint: float | None = None
    good: float | None = None
    excellent: float | None = None
    very_good: float | None = None
    fair: float | None = None
    poor: float | None = None


class CardmarketPricing(PyMTGBaseModel):
    """Pricing information from Cardmarket.

    Cardmarket provides average prices over different time periods,
    as well as low prices and trend information.

    Attributes:
        avg1: 1-day average price.
        avg7: 7-day average price.
        avg30: 30-day average price.
        low: Lowest price.
        low_ex: Lowest price for Excellent condition.
        trend: Price trend.
    """

    avg1: float | None = None
    avg7: float | None = None
    avg30: float | None = None
    low: float | None = None
    low_ex: float | None = None
    trend: float | None = None


class Pricing(PyMTGBaseModel):
    """Unified pricing model containing pricing from all providers.

    This model aggregates pricing information from all supported providers,
    allowing users to access pricing from any provider through a single
    interface. Each provider's pricing is optional and may be None if the
    provider doesn't return pricing information.

    Attributes:
        scryfall: Pricing information from Scryfall.
        tcgplayer: Pricing information from TCGPlayer.
        cardmarket: Pricing information from Cardmarket.
    """

    scryfall: ScryfallPricing | None = None
    tcgplayer: TCGPlayerPricing | None = None
    cardmarket: CardmarketPricing | None = None
