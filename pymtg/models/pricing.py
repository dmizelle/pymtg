"""Pricing models for Magic: The Gathering cards.

This module provides normalized pricing models for different MTG API providers,
allowing for consistent access to pricing information across all providers.
Each provider has its own pricing model with provider-specific fields.

Each provider pricing model declares its currency (or currencies) as a
``ClassVar`` so callers can verify currency consistency before comparing
or aggregating prices across providers. The unified ``Pricing`` model
exposes ``validate_currency_consistency`` as the primary method for
ensuring currency consistency before comparing or aggregating prices
across providers; it surfaces which currencies are actually populated
across the aggregated providers.
"""

from typing import ClassVar

from pymtg.models.base import PyMTGBaseModel


class ScryfallPricing(PyMTGBaseModel):
    """Pricing information from Scryfall.

    Scryfall provides pricing in multiple currencies and for different
    print variations (normal, foil, etched). The ``CURRENCIES``
    ClassVar declares the supported currency codes (usd, eur, tix).
    Use ``get_normal_print_currencies()`` to retrieve the normal-print
    prices for these currencies.

    Attributes:
        usd: Price in USD for normal prints.
        usd_foil: Price in USD for foil prints.
        usd_etched: Price in USD for etched foil prints.
        eur: Price in EUR for normal prints.
        eur_foil: Price in EUR for foil prints.
        tix: Price in MTGO tix for normal prints.
    """

    # Currency codes supported by this provider's pricing model. If
    # modified, update the class docstring and Attributes section to match.
    CURRENCIES: ClassVar[tuple[str, ...]] = ("usd", "eur", "tix")

    usd: float | None = None
    usd_foil: float | None = None
    usd_etched: float | None = None
    eur: float | None = None
    eur_foil: float | None = None
    tix: float | None = None

    def get_normal_print_currencies(self) -> dict[str, float | None]:
        """Returns the currency codes and normal-print prices tracked.

        Only normal-print prices are included; foil and etched variants
        share the same currency as their normal-print counterpart but
        are not returned by this method.

        Returns:
            A dict mapping currency code to the normal-print price for
            that currency. Currencies with no price set map to None.
        """
        return {currency: getattr(self, currency, None) for currency in self.CURRENCIES}


class TCGPlayerPricing(PyMTGBaseModel):
    """Pricing information from TCGPlayer.

    TCGPlayer provides various pricing metrics including market price,
    mid price, low/high prices, direct low price, and condition-specific
    prices. All prices are in US dollars. The ``CURRENCIES`` ClassVar
    declares the supported currency code (usd). Use ``has_prices()``
    to check if any price field is set.

    Attributes:
        market: Market price in USD.
        mid: Mid price in USD.
        low: Low price in USD.
        high: High price in USD.
        direct_low: Direct low price in USD.
        near_mint: Price for Near Mint condition in USD.
        good: Price for Good condition in USD.
        excellent: Price for Excellent condition in USD.
        very_good: Price for Very Good condition in USD.
        fair: Price for Fair condition in USD.
        poor: Price for Poor condition in USD.
    """

    # Currency codes supported by this provider's pricing model. If
    # modified, update the class docstring and Attributes section to match.
    CURRENCIES: ClassVar[tuple[str, ...]] = ("usd",)

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

    # Price fields checked by has_prices(). If new price fields are
    # added to the model above without updating this tuple, has_prices()
    # will not detect them. Keep this tuple in sync with the model fields.
    _PRICE_FIELDS: ClassVar[tuple[str, ...]] = (
        "market",
        "mid",
        "low",
        "high",
        "direct_low",
        "near_mint",
        "good",
        "excellent",
        "very_good",
        "fair",
        "poor",
    )

    def has_prices(self) -> bool:
        """Returns whether any price field is set.

        Checks only the fields listed in ``_PRICE_FIELDS`` so that
        non-price fields (if any are added in the future) do not
        produce false positives.

        Returns:
            True if at least one price field is not None, False otherwise.
        """
        return any(getattr(self, field) is not None for field in self._PRICE_FIELDS)


class CardmarketPricing(PyMTGBaseModel):
    """Pricing information from Cardmarket.

    Cardmarket provides average prices over different time periods,
    as well as low prices and trend information. All prices are in Euros.
    The ``CURRENCIES`` ClassVar declares the supported currency code
    (eur). Use ``has_prices()`` to check if any price field is set.

    Attributes:
        avg1: 1-day average price in EUR.
        avg7: 7-day average price in EUR.
        avg30: 30-day average price in EUR.
        low: Lowest price in EUR.
        low_ex: Lowest price for Excellent condition in EUR.
        trend: Price trend in EUR.
    """

    # Currency codes supported by this provider's pricing model. If
    # modified, update the class docstring and Attributes section to match.
    CURRENCIES: ClassVar[tuple[str, ...]] = ("eur",)

    avg1: float | None = None
    avg7: float | None = None
    avg30: float | None = None
    low: float | None = None
    low_ex: float | None = None
    trend: float | None = None

    # Price fields checked by has_prices(). If new price fields are
    # added to the model above without updating this tuple, has_prices()
    # will not detect them. Keep this tuple in sync with the model fields.
    _PRICE_FIELDS: ClassVar[tuple[str, ...]] = (
        "avg1",
        "avg7",
        "avg30",
        "low",
        "low_ex",
        "trend",
    )

    def has_prices(self) -> bool:
        """Returns whether any price field is set.

        Checks only the fields listed in ``_PRICE_FIELDS`` so that
        non-price fields (if any are added in the future) do not
        produce false positives.

        Returns:
            True if at least one price field is not None, False otherwise.
        """
        return any(getattr(self, field) is not None for field in self._PRICE_FIELDS)


class Pricing(PyMTGBaseModel):
    """Unified pricing model containing pricing from all providers.

    This model aggregates pricing information from all supported providers,
    allowing users to access pricing from any provider through a single
    interface. Each provider's pricing is optional and may be None if the
    provider doesn't return pricing information.

    Because providers use different currencies (Scryfall tracks USD, EUR,
    and tix; TCGPlayer is USD-only; Cardmarket is EUR-only), callers must
    verify currency consistency before comparing or aggregating prices
    across providers. Use ``validate_currency_consistency`` to surface
    which currencies are actually populated.

    Attributes:
        scryfall: Pricing information from Scryfall.
        tcgplayer: Pricing information from TCGPlayer.
        cardmarket: Pricing information from Cardmarket.
    """

    scryfall: ScryfallPricing | None = None
    tcgplayer: TCGPlayerPricing | None = None
    cardmarket: CardmarketPricing | None = None

    def validate_currency_consistency(self) -> dict[str, list[str]]:
        """Returns currencies populated across all provider pricings.

        Inspects each present provider pricing and maps each currency
        code to the list of provider names that have at least one
        non-None price in that currency. Providers with no prices set
        are omitted. This surfaces which currencies are actually
        populated so callers can avoid comparing prices across
        different currencies.

        For Scryfall, each currency is included only if its
        normal-print price is not None. For single-currency providers
        (TCGPlayer and Cardmarket), the currency is included if
        ``has_prices()`` returns True, rather than checking individual
        currency fields. This is correct because these providers
        currently support only one currency each; if they ever support
        multiple currencies, this logic must be updated to check
        individual currency fields.

        Returns:
            A dict mapping each currency code to the list of provider
            names that have at least one non-None price in that
            currency. Returns an empty dict if no providers are
            present or none have prices set.
        """
        result: dict[str, list[str]] = {}
        if self.scryfall is not None:
            currencies = self.scryfall.get_normal_print_currencies()
            for currency, value in currencies.items():
                if value is not None:
                    result.setdefault(currency, []).append("scryfall")
        # TODO: TCGPlayer and Cardmarket are single-currency providers:
        # if has_prices() is True, all their declared currencies are
        # populated. If they ever support multiple currencies, this
        # logic must be updated to check individual currency fields
        # rather than relying on has_prices() alone.
        if self.tcgplayer is not None and self.tcgplayer.has_prices():
            for currency in TCGPlayerPricing.CURRENCIES:
                result.setdefault(currency, []).append("tcgplayer")
        if self.cardmarket is not None and self.cardmarket.has_prices():
            for currency in CardmarketPricing.CURRENCIES:
                result.setdefault(currency, []).append("cardmarket")
        return result
