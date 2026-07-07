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


class _ProviderPricingBase(PyMTGBaseModel):
    """Base class for provider pricing models.

    Subclasses must declare ``CURRENCIES`` (currency codes supported by
    the provider) and may declare ``_PRICE_FIELDS`` (fields checked by
    ``has_prices()``). At class creation time, ``_PRICE_FIELDS`` is
    validated against the subclass's model fields so typos or drift
    are caught early rather than silently returning wrong results.

    ``CURRENCIES`` is not validated against model fields because its
    semantics differ per subclass: for ``ScryfallPricing`` each
    currency code is also a field name, but for single-currency
    providers (TCGPlayer, Cardmarket) the currency code describes all
    fields rather than naming one.

    Attributes:
        CURRENCIES: Currency codes supported by the provider.
        _PRICE_FIELDS: Fields checked by ``has_prices()``. Each entry
            must be the name of a model field on the subclass.
    """

    CURRENCIES: ClassVar[tuple[str, ...]] = ()
    _PRICE_FIELDS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: object) -> None:
        """Validates _PRICE_FIELDS against model fields.

        Ensures every entry in ``_PRICE_FIELDS`` corresponds to an
        actual model field on the subclass, raising ``TypeError`` if
        any entry is not a field. This catches typos and drift at
        class definition time rather than silently returning wrong
        results at runtime.

        Note: ``CURRENCIES`` is not validated against model fields
        because its semantics differ per subclass. For
        ``ScryfallPricing`` each currency code is also a field name,
        but for single-currency providers (TCGPlayer, Cardmarket) the
        currency code describes all fields rather than naming one.

        Args:
            **kwargs: Forwarded by Pydantic.

        Raises:
            TypeError: If any entry in ``_PRICE_FIELDS`` is not a
                model field on the subclass.
        """
        super().__pydantic_init_subclass__(**kwargs)  # type: ignore[misc]
        field_names = set(cls.model_fields)
        for field in cls._PRICE_FIELDS:
            if field not in field_names:
                raise TypeError(
                    f"{cls.__name__}._PRICE_FIELDS references "
                    f"unknown field {field!r}; must be one of "
                    f"{sorted(field_names)}"
                )
            # Validate that the field is a price field (float | None).
            # Non-price fields (e.g., metadata) would cause has_prices()
            # to return True for non-price data.
            annotation = cls.model_fields[field].annotation
            # Parens make precedence explicit: | binds tighter than !=,
            # so this is `annotation != (float | None)`.
            if annotation != (float | None):
                raise TypeError(
                    f"{cls.__name__}._PRICE_FIELDS entry {field!r} "
                    f"has type {annotation!r}; expected float | None "
                    f"for price fields."
                )

    def has_prices(self) -> bool:
        """Returns whether any price field is set.

        Checks only the fields listed in ``_PRICE_FIELDS`` so that
        non-price fields (if any are added in the future) do not
        produce false positives. Note that this checks all price
        fields, not just normal-print prices; callers needing
        normal-print-only checks should inspect specific fields.

        Returns:
            True if at least one price field is not None, False otherwise.
        """
        return any(getattr(self, field) is not None for field in self._PRICE_FIELDS)


class ScryfallPricing(_ProviderPricingBase):
    """Pricing information from Scryfall.

    Scryfall provides pricing in multiple currencies and for different
    print variations (normal, foil, etched). The ``CURRENCIES``
    ClassVar declares the supported currency codes (usd, eur, tix, cad,
    gbp, jpy, cny). Use ``get_normal_print_currencies()`` to retrieve
    the normal-print prices for these currencies.

    Attributes:
        usd: Price in USD for normal prints.
        usd_foil: Price in USD for foil prints.
        usd_etched: Price in USD for etched foil prints.
        eur: Price in EUR for normal prints.
        eur_foil: Price in EUR for foil prints.
        tix: Price in MTGO tix for normal prints.
        cad: Price in CAD for normal prints.
        cad_foil: Price in CAD for foil prints.
        gbp: Price in GBP for normal prints.
        gbp_foil: Price in GBP for foil prints.
        jpy: Price in JPY for normal prints.
        jpy_foil: Price in JPY for foil prints.
        cny: Price in CNY for normal prints.
        cny_foil: Price in CNY for foil prints.
    """

    # Currency codes supported by this provider's pricing model. If
    # modified, update the class docstring and Attributes section to match.
    CURRENCIES: ClassVar[tuple[str, ...]] = (
        "usd",
        "eur",
        "tix",
        "cad",
        "gbp",
        "jpy",
        "cny",
    )

    usd: float | None = None
    usd_foil: float | None = None
    usd_etched: float | None = None
    eur: float | None = None
    eur_foil: float | None = None
    tix: float | None = None
    cad: float | None = None
    cad_foil: float | None = None
    gbp: float | None = None
    gbp_foil: float | None = None
    jpy: float | None = None
    jpy_foil: float | None = None
    cny: float | None = None
    cny_foil: float | None = None

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: object) -> None:
        """Validates CURRENCIES entries are actual model fields.

        For ScryfallPricing, each currency code in ``CURRENCIES`` is
        also a model field name (e.g., ``usd``, ``eur``, ``tix``), so
        typos would cause ``get_normal_print_currencies()`` to silently
        return ``None``. This hook catches such typos at class
        definition time.

        Args:
            **kwargs: Forwarded by Pydantic.

        Raises:
            TypeError: If any entry in ``CURRENCIES`` is not a model
                field on the subclass.
        """
        super().__pydantic_init_subclass__(**kwargs)
        field_names = set(cls.model_fields)
        for currency in cls.CURRENCIES:
            if currency not in field_names:
                raise TypeError(
                    f"{cls.__name__}.CURRENCIES references "
                    f"unknown field {currency!r}; must be one of "
                    f"{sorted(field_names)}"
                )

    def get_normal_print_currencies(self) -> dict[str, float | None]:
        """Returns the currency codes and normal-print prices tracked.

        Only normal-print prices are included; foil and etched variants
        share the same currency as their normal-print counterpart but
        are not returned by this method.

        Returns:
            A dict mapping currency code to the normal-print price for
            that currency. Currencies with no price set map to None.
        """
        # No default needed: __pydantic_init_subclass__ validates that
        # every entry in CURRENCIES is an actual model field name.
        return {currency: getattr(self, currency) for currency in self.CURRENCIES}


class TCGPlayerPricing(_ProviderPricingBase):
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

    # Currency code supported by this provider's pricing model. Unlike
    # ScryfallPricing, this code does NOT correspond to a model field
    # name (the fields are market, mid, etc.); it describes the currency
    # of all fields. Therefore it is not validated against model_fields.
    # If modified, update the class docstring and Attributes section.
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

    # Price fields checked by has_prices(). Validated against model
    # fields at class creation time by _ProviderPricingBase, so typos
    # or drift raise TypeError immediately.
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


class CardmarketPricing(_ProviderPricingBase):
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

    # Currency code supported by this provider's pricing model. Unlike
    # ScryfallPricing, this code does NOT correspond to a model field
    # name (the fields are avg1, avg7, etc.); it describes the currency
    # of all fields. Therefore it is not validated against model_fields.
    # If modified, update the class docstring and Attributes section.
    CURRENCIES: ClassVar[tuple[str, ...]] = ("eur",)

    avg1: float | None = None
    avg7: float | None = None
    avg30: float | None = None
    low: float | None = None
    low_ex: float | None = None
    trend: float | None = None

    # Price fields checked by has_prices(). Validated against model
    # fields at class creation time by _ProviderPricingBase, so typos
    # or drift raise TypeError immediately.
    _PRICE_FIELDS: ClassVar[tuple[str, ...]] = (
        "avg1",
        "avg7",
        "avg30",
        "low",
        "low_ex",
        "trend",
    )


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
            present or none have prices set; an empty result means
            no currencies are populated, not that currencies are
            consistent.
        """
        result: dict[str, list[str]] = {}
        if self.scryfall is not None:
            currencies = self.scryfall.get_normal_print_currencies()
            for currency, value in currencies.items():
                if value is not None:
                    result.setdefault(currency, []).append("scryfall")
        # TCGPlayer and Cardmarket are single-currency providers: if
        # has_prices() is True, all their declared currencies are
        # populated. If they ever support multiple currencies, this
        # logic must be updated to check individual currency fields
        # rather than relying on has_prices() alone. The helper below
        # warns maintainers if CURRENCIES grows beyond one entry.
        if self.tcgplayer is not None and self.tcgplayer.has_prices():
            self._add_single_currency_provider(result, "tcgplayer", self.tcgplayer)
        if self.cardmarket is not None and self.cardmarket.has_prices():
            self._add_single_currency_provider(result, "cardmarket", self.cardmarket)
        return result

    @staticmethod
    def _add_single_currency_provider(
        result: dict[str, list[str]],
        provider_name: str,
        provider: _ProviderPricingBase,
    ) -> None:
        """Adds a single-currency provider's currencies to the result.

        Warns if the provider's ``CURRENCIES`` has multiple entries,
        since this method assumes single-currency providers. Skips
        providers with empty ``CURRENCIES``.

        Args:
            result: The result dict being built by
                ``validate_currency_consistency``.
            provider_name: The name of the provider (e.g.,
                ``"tcgplayer"``).
            provider: The provider pricing instance.
        """
        currencies = provider.CURRENCIES
        if not currencies:
            return
        if len(currencies) > 1:
            raise NotImplementedError(
                f"{type(provider).__name__}.CURRENCIES has "
                f"{len(currencies)} entries; validate_currency_consistency "
                f"only supports single-currency providers. Update this "
                f"method to check individual currency fields before "
                f"adding multiple currencies to a provider."
            )
        for currency in currencies:
            result.setdefault(currency, []).append(provider_name)
