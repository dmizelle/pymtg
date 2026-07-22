"""Card and card-related models for Magic: The Gathering.

This module provides the main Card model and related models (CardFace, DeckCard)
for representing Magic: The Gathering cards in a normalized format across all
providers.
"""

import warnings
from typing import Any, ClassVar

from pydantic import Field, model_validator

from pymtg.models.base import PyMTGBaseModel
from pymtg.models.enums import Color, Format, Rarity
from pymtg.models.pricing import Pricing


class CardFace(PyMTGBaseModel):
    """Represents a single face of a Magic: The Gathering card.

    Some cards (like transform, modal dual-faced, or flip cards) have multiple
    faces. Each face is represented by a CardFace object.

    Attributes:
        name: Name of the face.
        mana_cost: Mana cost of the face.
        type_line: Type line of the face.
        oracle_text: Oracle rules text of the face.
        power: Power of the face (as string to handle non-numeric values).
        toughness: Toughness of the face (as string to handle non-numeric values).
        colors: Colors in the mana cost of this face.
        color_indicator: Colors in the color indicator of this face.
        loyalty: Loyalty value (for planeswalkers).
        defense: Defense value (for battles).
        flavor_text: Flavor text of the face.
        artist: Artist name.
        artist_id: Scryfall artist ID.
        illustration_id: Scryfall illustration ID.
        image_uris: Dictionary of image URIs for this face.
    """

    name: str
    mana_cost: str | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None
    colors: list[Color] | None = None
    color_indicator: list[Color] | None = None
    loyalty: str | None = None
    defense: str | None = None
    flavor_text: str | None = None
    artist: str | None = None
    artist_id: str | None = None
    illustration_id: str | None = None
    image_uris: dict[str, str] | None = None


class Legality(PyMTGBaseModel):
    """Represents the legality of a card in a format.

    Attributes:
        format: The format name.
        status: The legality status (legal, not_legal, restricted, banned).
    """

    format: Format
    status: str


class Card(PyMTGBaseModel):
    """Normalized Magic: The Gathering card model.

    This model represents a Magic: The Gathering card in a normalized format
    that is consistent across all supported providers. It includes all the
    essential fields needed for Card Lookup, Deck Aggregator, and Universal
    Search functionality.

    Attributes:
        id: Provider-specific card ID.
        scryfall_id: Canonical Scryfall UUID (None if not available from provider).
        oracle_id: Oracle ID for the card text (same across printings).
        name: Card name.
        printed_name: The name as printed on the card.
        mana_cost: Raw mana cost string.
        cmc: Converted mana cost (float to handle fractional costs).
        type_line: Full type line string.
        printed_type_line: The type line as printed on the card.
        oracle_text: Oracle rules text.
        printed_text: The rules text as printed on the card.
        flavors: List of flavor text strings.
        colors: List of colors in mana cost.
        color_identity: List of colors in color identity.
        color_indicator: List of colors in color indicator.
        keywords: List of keyword abilities.
        all_parts: List of IDs for cards in the same cycle/part.
        card_faces: List of CardFace objects for multi-faced cards.
        set_code: Set code (e.g., "LEA", "M20").
        set_name: Full set name.
        set_type: Set type (e.g., "core", "expansion").
        rarity: Card rarity.
        collector_number: Collector number.
        power: Power (string to handle non-numeric values like "*").
        toughness: Toughness (string).
        loyalty: Loyalty (string for planeswalkers).
        defense: Defense (string for battles).
        layout: Card layout (normal, split, transform, etc.).
        image_uris: Dictionary of image URIs.
        image_status: Status of image availability.
        pricing: Pricing information (nullable, eager-loaded).
        legalities: Dictionary of format legalities.
        released_at: Date the card was released.
        reserved: Whether the card is on the Reserved List.
        foil: Whether the card is foil.
        nonfoil: Whether the card is non-foil.
        oversized: Whether the card is oversized.
        promo: Whether the card is a promo.
        reprint: Whether the card is a reprint.
        variation: Whether the card is a variation.
        multiverse_ids: List of Multiverse IDs for the card.
        tcgplayer_id: TCGPlayer product ID.
        cardmarket_id: Cardmarket ID.
        prints_search_uri: URI to search for all prints of this card.
        rulings_uri: URI to the card's rulings on Scryfall.
        scryfall_uri: URI to the card on Scryfall.
        uri: URI to the card on the provider's site.
        source: Provider name that provided this card data.
    """

    _SHARED_FACE_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "mana_cost",
        "type_line",
        "oracle_text",
        "power",
        "toughness",
        "colors",
        "color_indicator",
        "loyalty",
        "defense",
        "artist",
        "artist_id",
        "illustration_id",
        "image_uris",
    )

    # Opt-in flag for the _warn_main_face_inconsistency validator.
    # Defaults to False so bulk imports are not penalized with per-card
    # warnings; set to True to surface face/top-level field mismatches.
    _warn_face_inconsistency: ClassVar[bool] = False

    id: str
    scryfall_id: str | None = None
    oracle_id: str | None = None
    name: str
    printed_name: str | None = None
    mana_cost: str | None = None
    cmc: float | None = None
    type_line: str | None = None
    printed_type_line: str | None = None
    oracle_text: str | None = None
    printed_text: str | None = None
    flavors: list[str] | None = None
    colors: list[Color] | None = None
    color_identity: list[Color] | None = None
    color_indicator: list[Color] | None = None
    keywords: list[str] | None = None
    all_parts: list[str] | None = None
    card_faces: list[CardFace] | None = None
    set_code: str | None = None
    set_name: str | None = None
    set_type: str | None = None
    rarity: Rarity | None = None
    collector_number: str | None = None
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    defense: str | None = None
    layout: str | None = None
    image_uris: dict[str, str] | None = None
    image_status: str | None = None
    artist: str | None = None
    artist_id: str | None = None
    illustration_id: str | None = None
    pricing: Pricing | None = None
    legalities: dict[str, str] | None = None
    released_at: str | None = None
    reserved: bool | None = None
    foil: bool | None = None
    nonfoil: bool | None = None
    oversized: bool | None = None
    promo: bool | None = None
    reprint: bool | None = None
    variation: bool | None = None
    multiverse_ids: list[int] | None = None
    tcgplayer_id: int | None = None
    cardmarket_id: int | None = None
    prints_search_uri: str | None = None
    rulings_uri: str | None = None
    scryfall_uri: str | None = None
    uri: str | None = None
    source: str | None = None

    def is_white(self) -> bool:
        """Check if this card is white.

        Returns:
            True if the card's color identity contains white.
        """
        return Color.WHITE in (self.color_identity or [])

    def is_blue(self) -> bool:
        """Check if this card is blue.

        Returns:
            True if the card's color identity contains blue.
        """
        return Color.BLUE in (self.color_identity or [])

    def is_black(self) -> bool:
        """Check if this card is black.

        Returns:
            True if the card's color identity contains black.
        """
        return Color.BLACK in (self.color_identity or [])

    def is_red(self) -> bool:
        """Check if this card is red.

        Returns:
            True if the card's color identity contains red.
        """
        return Color.RED in (self.color_identity or [])

    def is_green(self) -> bool:
        """Check if this card is green.

        Returns:
            True if the card's color identity contains green.
        """
        return Color.GREEN in (self.color_identity or [])

    def is_colorless(self) -> bool:
        """Check if this card is colorless.

        A card is colorless when its color identity is absent, empty, or
        contains only the colorless marker (the empty string).

        Returns:
            True if the card has no color identity.
        """
        if not self.color_identity:
            return True

        def _val(c: Color | str) -> str:
            return c.value if isinstance(c, Color) else c

        return all(_val(c) == "" for c in self.color_identity)

    def is_multicolor(self) -> bool:
        """Check if this card is multicolor.

        Returns:
            True if the card has multiple colors in its identity.
        """
        return self.color_identity is not None and len(self.color_identity) > 1

    def get_color_identity_string(self) -> str:
        """Get the color identity as a string.

        Colors are sorted in WUBRG order (White, Blue, Black, Red, Green) to match
        Magic: The Gathering conventions for mana costs and color identities.

        Returns:
            A string representation of the color identity (e.g., "WUBRG").
        """
        if self.color_identity is None:
            return ""
        # WUBRG order for sorting
        color_order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
        # Decompose each entry into individual single-character colors
        # before sorting. With use_enum_values=True, list elements are
        # stored as raw strings, which may be multi-char combinations
        # (e.g. Color.AZORIUS == "WU") that must be split apart.
        result_chars: list[str] = []
        for c in self.color_identity:
            val = c.value if isinstance(c, Color) else c
            if not val:
                continue
            result_chars.extend(list(val))
        # Deduplicate while preserving WUBRG order.
        seen: set[str] = set()
        ordered: list[str] = []
        for ch in sorted(result_chars, key=lambda x: color_order.get(x.upper(), 5)):
            if ch not in seen:
                seen.add(ch)
                ordered.append(ch)
        return "".join(ordered)

    def get_mana_value(self) -> float:
        """Get the mana value (converted mana cost) of the card.

        Returns:
            The converted mana cost as a float, or 0.0 if not available.
        """
        return self.cmc or 0.0

    def _type_tokens(self) -> set[str]:
        """Returns the set of whitespace-delimited tokens in the type line.

        Strips the em-dash separator used to split the supertype/subtype
        portions of an MTG type line so each token is matched
        independently rather than via fragile substring containment.

        Returns:
            A set of tokens, or an empty set if type_line is unset.
        """
        if not self.type_line:
            return set()
        return {t for t in self.type_line.replace("—", " ").split()}

    def is_creature(self) -> bool:
        """Check if this card is a creature.

        Returns:
            True if the card's type line contains "Creature".
        """
        return "Creature" in self._type_tokens()

    def is_instant(self) -> bool:
        """Check if this card is an instant.

        Returns:
            True if the card's type line contains "Instant".
        """
        return "Instant" in self._type_tokens()

    def is_sorcery(self) -> bool:
        """Check if this card is a sorcery.

        Returns:
            True if the card's type line contains "Sorcery".
        """
        return "Sorcery" in self._type_tokens()

    def is_artifact(self) -> bool:
        """Check if this card is an artifact.

        Returns:
            True if the card's type line contains "Artifact".
        """
        return "Artifact" in self._type_tokens()

    def is_enchantment(self) -> bool:
        """Check if this card is an enchantment.

        Returns:
            True if the card's type line contains "Enchantment".
        """
        return "Enchantment" in self._type_tokens()

    def is_land(self) -> bool:
        """Check if this card is a land.

        Returns:
            True if the card's type line contains "Land".
        """
        return "Land" in self._type_tokens()

    def is_planeswalker(self) -> bool:
        """Check if this card is a planeswalker.

        Returns:
            True if the card's type line contains "Planeswalker".
        """
        return "Planeswalker" in self._type_tokens()

    def is_battle(self) -> bool:
        """Check if this card is a battle.

        Returns:
            True if the card's type line contains "Battle".
        """
        return "Battle" in self._type_tokens()

    def get_main_face(self) -> CardFace | None:
        """Get the main face of the card.

        Returns:
            The first CardFace if card_faces is not None and not empty, else None.
        """
        if self.card_faces:
            return self.card_faces[0]
        return None

    def validate_main_face_consistency(self) -> dict[str, tuple[Any, Any]]:
        """Validates that top-level Card fields match the main face's fields.

        For multi-faced cards (transform, modal dual-faced, etc.), the
        top-level Card fields should match the corresponding fields on the
        main face (card_faces[0]). This method checks all fields shared
        between Card and CardFace for consistency.

        Returns:
            A dict mapping mismatched field names to tuples of
            (card_value, face_value). Returns an empty dict if all shared
            fields are consistent or if the card has no faces.
        """
        main_face = self.get_main_face()
        if main_face is None:
            return {}

        mismatches: dict[str, tuple[Any, Any]] = {}
        for field in self._SHARED_FACE_FIELDS:
            card_value = getattr(self, field, None)
            face_value = getattr(main_face, field, None)
            if card_value != face_value:
                mismatches[field] = (card_value, face_value)
        return mismatches

    @model_validator(mode="after")
    def _warn_main_face_inconsistency(self) -> "Card":
        """Warns if top-level Card fields differ from the main face's fields.

        Emits a ``UserWarning`` for each shared field whose top-level
        value does not match the corresponding ``card_faces[0]`` value.
        Stays silent when the card has no faces or all shared fields are
        consistent.

        This validator is gated behind the class-level
        ``_warn_face_inconsistency`` flag (default ``False``) so that
        bulk-import paths are not penalized with per-card warnings.
        Subclasses or callers that want the warnings can set
        ``Card._warn_face_inconsistency = True``. Callers who want hard
        enforcement can invoke ``validate_main_face_consistency()``
        directly and raise on any non-empty result.

        Returns:
            The validated Card instance (unchanged).
        """
        if not getattr(self, "_warn_face_inconsistency", False):
            return self
        mismatches = self.validate_main_face_consistency()
        for field, (card_value, face_value) in mismatches.items():
            warnings.warn(
                f"Card.{field}={card_value!r} does not match "
                f"card_faces[0].{field}={face_value!r}; "
                f"call synchronize_from_main_face() to align them "
                f"(this will overwrite top-level fields).",
                UserWarning,
                stacklevel=2,
            )
        return self

    def synchronize_from_main_face(self) -> dict[str, tuple[Any, Any]]:
        """Copies shared field values from the main face to top-level fields.

        Overwrites each top-level Card field listed in
        ``_SHARED_FACE_FIELDS`` with the value from ``card_faces[0]``.
        Useful when the data source may have populated the top-level fields
        with combined or stale values (e.g., split cards) and the caller
        wants the main face's values to take precedence.

        Returns:
            A dict mapping field names that were changed to tuples of
            (old_value, new_value). Returns an empty dict if the card has
            no faces or all shared fields already match.
        """
        main_face = self.get_main_face()
        if main_face is None:
            return {}

        changes: dict[str, tuple[Any, Any]] = {}
        for field in self._SHARED_FACE_FIELDS:
            card_value = getattr(self, field, None)
            face_value = getattr(main_face, field, None)
            if card_value != face_value:
                # Note: validate_assignment is not enabled in model_config,
                # so setattr bypasses re-validation. The face value was
                # already validated when the CardFace was constructed. If
                # validate_assignment is ever enabled, switch to
                # self.model_copy(update=...) for atomic, validated updates.
                setattr(self, field, face_value)
                changes[field] = (card_value, face_value)
        return changes


class DeckCard(PyMTGBaseModel):
    """Represents a card in a deck with count and board information.

    This model represents a card within a deck, including how many copies
    are in the deck and which board (main, sideboard, commander, etc.) it belongs to.

    Attributes:
        card: The Card object.
        count: Number of copies of this card in the deck.
        board: The board this card belongs to.
    """

    card: Card
    count: int = Field(
        ge=0,
        description=(
            "Number of copies of this card in the deck; zero is allowed "
            "to represent template/slot placeholders."
        ),
    )
    board: str | None = None
