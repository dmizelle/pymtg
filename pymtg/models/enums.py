"""Enums for Magic: The Gathering data types.

This module provides enumerations for various MTG data types including
colors, rarities, formats, board types, and set types. These enums ensure
type safety and provide consistent values across all providers.
"""

from enum import StrEnum
from typing import Union


class Color(StrEnum):
    """Color enum for Magic: The Gathering card colors.

    This enum represents all possible color identities and color combinations
    in Magic: The Gathering. It uses single-letter values (W, U, B, R, G) that
    match MTG conventions and Scryfall API responses.

    Attributes:
        WHITE: White color (W).
        BLUE: Blue color (U).
        BLACK: Black color (B).
        RED: Red color (R).
        GREEN: Green color (G).
        COLORLESS: Colorless (empty string).
        AZORIUS: Azorius color combination (WU).
        DIMIR: Dimir color combination (UB).
        RAKDOS: Rakdos color combination (BR).
        GRUEL: Gruul color combination (RG).
        SELESNYA: Selesnya color combination (GW).
        ORZHOV: Orzhov color combination (WB).
        GOLGARI: Golgari color combination (BG).
        SIMIC: Simic color combination (UG).
        BOROS: Boros color combination (RW).
        IZZET: Izzet color combination (UR).
        BANT: Bant color combination (WUG).
        ESPER: Esper color combination (WUB).
        GRIXIS: Grixis color combination (UBR).
        JUND: Jund color combination (BRG).
        NAYA: Naya color combination (RGW).
        ABZAN: Abzan color combination (WBG).
        JESKAI: Jeskai color combination (WUR).
        SULTAI: Sultai color combination (UBG).
        MARDU: Mardu color combination (RGW).
        TEMUR: Temur color combination (URG).
        WUBR: Four-color combination (WUBR).
        WUBG: Four-color combination (WUBG).
        WURG: Four-color combination (WURG).
        WBRG: Four-color combination (WBRG).
        UBRG: Four-color combination (UBRG).
        WUBRG: Five-color combination (WUBRG).
    """

    # Single colors
    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"
    COLORLESS = ""

    # Color combinations (two-color pairs)
    AZORIUS = "WU"
    DIMIR = "UB"
    RAKDOS = "BR"
    GRUEL = "RG"
    SELESNYA = "GW"
    ORZHOV = "WB"
    GOLGARI = "BG"
    SIMIC = "UG"
    BOROS = "RW"
    IZZET = "UR"

    # Three-color shards
    BANT = "WUG"
    ESPER = "WUB"
    GRIXIS = "UBR"
    JUND = "BRG"
    NAYA = "WRG"
    ABZAN = "WBG"
    JESKAI = "WUR"
    SULTAI = "UBG"
    MARDU = "WRG"
    TEMUR = "URG"

    # Four-color combinations
    WUBR = "WUBR"
    WUBG = "WUBG"
    WURG = "WURG"
    WBRG = "WBRG"
    UBRG = "UBRG"

    # Five-color
    WUBRG = "WUBRG"

    @property
    def full_name(self) -> str:
        """Return the full display name for the color or color combination.

        Returns:
            The full name(s) of the color(s), separated by spaces.
        """
        names = {
            "W": "White",
            "U": "Blue",
            "B": "Black",
            "R": "Red",
            "G": "Green",
            "": "Colorless",
        }
        if not self.value:
            return names[""]
        return " ".join(names[c] for c in self.value)

    @classmethod
    def from_full_name(cls, name: str) -> "Color":
        """Convert a full color name to Color enum value.

        Args:
            name: The full color name (e.g., "White", "Blue", "Colorless").

        Returns:
            The corresponding Color enum value.
        """
        mapping = {
            "White": cls.WHITE,
            "Blue": cls.BLUE,
            "Black": cls.BLACK,
            "Red": cls.RED,
            "Green": cls.GREEN,
            "Colorless": cls.COLORLESS,
        }
        return mapping.get(name, cls.COLORLESS)

    @classmethod
    def from_colors(cls, colors: list["Color"]) -> "Color":
        """Create a color combination from a list of individual colors.

        Colors are sorted in WUBRG order (White, Blue, Black, Red, Green) to match
        Magic: The Gathering conventions for mana costs and color identities.

        Args:
            colors: List of Color enum values to combine.

        Returns:
            A Color enum value representing the combination.
        """
        # WUBRG order for sorting
        color_order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
        # Sort by WUBRG order, not alphabetically
        sorted_colors = sorted(
            (c for c in colors if c.value),
            key=lambda c: color_order.get(c.value, 5),
        )
        combined = "".join(c.value for c in sorted_colors)
        # Try to find exact match in enum
        for member in cls:
            if member.value == combined:
                return member
        # If no exact match, return as combined string (will still be valid)
        return cls(combined)

    def __contains__(self, color: Union[str, "Color"]) -> bool:  # type: ignore[override]
        """Check if this color combination contains a specific color.

        Args:
            color: The Color to check for.

        Returns:
            True if this color combination contains the specified color.
        """
        if isinstance(color, Color):
            return color.value in self.value
        return color in self.value

    def is_multicolor(self) -> bool:
        """Check if this is a multicolor combination.

        Returns:
            True if this color has multiple colors.
        """
        return len(self.value) > 1


class Rarity(StrEnum):
    """Rarity enum for Magic: The Gathering card rarities.

    Attributes:
        COMMON: Common rarity.
        UNCOMMON: Uncommon rarity.
        RARE: Rare rarity.
        MYTHIC: Mythic Rare rarity.
        SPECIAL: Special rarity.
        BONUS: Bonus rarity.
    """

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    MYTHIC = "mythic"
    SPECIAL = "special"
    BONUS = "bonus"


class Format(StrEnum):
    """Format enum for Magic: The Gathering game formats.

    Attributes:
        STANDARD: Standard format.
        MODERN: Modern format.
        LEGACY: Legacy format.
        VINTAGE: Vintage format.
        COMMANDER: Commander format.
        PAUPER: Pauper format.
        PIONEER: Pioneer format.
        EXPLORER: Explorer format.
        HISTORIC: Historic format.
        BRAWL: Brawl format.
        DRAFT: Draft format.
        SEALED: Sealed format.
        TWO_HEADED_GIANT: Two-Headed Giant format.
        ARCHENEMY: Archenemy format.
        PLANECHASE: Planechase format.
        CONSPIRACY: Conspiracy format.
        OATHBREAKER: Oathbreaker format.
        FUTURE_STANDARD: Future Standard format.
        GLOBE: Globe format.
        OLD_SCHOOL: Old School format.
    """

    STANDARD = "standard"
    MODERN = "modern"
    LEGACY = "legacy"
    VINTAGE = "vintage"
    COMMANDER = "commander"
    PAUPER = "pauper"
    PIONEER = "pioneer"
    EXPLORER = "explorer"
    HISTORIC = "historic"
    BRAWL = "brawl"
    DRAFT = "draft"
    SEALED = "sealed"
    TWO_HEADED_GIANT = "two-headed giant"
    ARCHENEMY = "archenemy"
    PLANECHASE = "planechase"
    CONSPIRACY = "conspiracy"
    OATHBREAKER = "oathbreaker"
    FUTURE_STANDARD = "future standard"
    GLOBE = "globe"
    OLD_SCHOOL = "old school"


class Board(StrEnum):
    """Board enum for deck board types.

    Attributes:
        MAIN: Main deck.
        SIDEBOARD: Sideboard.
        COMMANDER: Commander zone.
        MAYBEBOARD: Maybe board.
    """

    MAIN = "main"
    SIDEBOARD = "sideboard"
    COMMANDER = "commander"
    MAYBEBOARD = "maybeboard"


class SetType(StrEnum):
    """SetType enum for Magic: The Gathering set types.

    Attributes:
        CORE: Core set.
        EXPANSION: Expansion set.
        REPRINT: Reprint set.
        COMMANDER: Commander set.
        PLANECHASE: Planechase set.
        ARCHENEMY: Archenemy set.
        CONSPIRACY: Conspiracy set.
        BATTLEBOX: Battlebox set.
        DRAFT_INNOVATION: Draft Innovation set.
        TREASURE_CHEST: Treasure Chest set.
        MASTERPIECE: Masterpiece set.
        FROM_THE_VAULT: From the Vault set.
        SPELLBOOK: Spellbook series.
        PREMIUM_DECK: Premium Deck Series.
        DUEL_DECK: Duel Deck.
        COMMANDERS_ARSENAL: Commander's Arsenal.
        PROMO: Promo set.
        STARTER: Starter set.
        BOX: Box set.
        MEME: Memes set (joke cards).
        MINIGAME: Mini game set.
        ALPHA: Alpha edition.
        BETA: Beta edition.
        UNLIMITED: Unlimited edition.
    """

    CORE = "core"
    EXPANSION = "expansion"
    REPRINT = "reprint"
    COMMANDER = "commander"
    PLANECHASE = "planechase"
    ARCHENEMY = "archenemy"
    CONSPIRACY = "conspiracy"
    BATTLEBOX = "battlebox"
    DRAFT_INNOVATION = "draft_innovation"
    TREASURE_CHEST = "treasure_chest"
    MASTERPIECE = "masterpiece"
    FROM_THE_VAULT = "from_the_vault"
    SPELLBOOK = "spellbook"
    PREMIUM_DECK = "premium_deck"
    DUEL_DECK = "duel_deck"
    COMMANDERS_ARSENAL = "commanders_arsenal"
    PROMO = "promo"
    STARTER = "starter"
    BOX = "box"
    MEME = "meme"
    MINIGAME = "minigame"
    ALPHA = "alpha"
    BETA = "beta"
    UNLIMITED = "unlimited"
