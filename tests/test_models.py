"""Tests for pymtg data models.

This module contains comprehensive tests for all pymtg data models including:
- Card, CardFace, DeckCard models
- Deck model
- Set model
- Pricing models (ScryfallPricing, TCGPlayerPricing, CardmarketPricing, Pricing)
- Enums (Color, Rarity, Format, Board, SetType)
- Base model (PyMTGBaseModel)

Tests cover:
- Model creation with all required fields
- Model creation with optional fields missing
- Model validation (invalid types, etc.)
- Helper methods (is_multicolor, get_color_identity_string, etc.)
- Serialization/deserialization
"""

import json

import pytest
from pydantic import ValidationError

from pymtg.models import (
    Board,
    Card,
    CardFace,
    CardmarketPricing,
    Color,
    Deck,
    DeckCard,
    Format,
    Pricing,
    PyMTGBaseModel,
    Rarity,
    ScryfallPricing,
    Set,
    SetType,
    TCGPlayerPricing,
)


class TestColorEnum:
    """Tests for the Color enum."""

    def test_color_single_values(self) -> None:
        """Test that single color values are correct."""
        assert Color.WHITE.value == "W"
        assert Color.BLUE.value == "U"
        assert Color.BLACK.value == "B"
        assert Color.RED.value == "R"
        assert Color.GREEN.value == "G"
        assert Color.COLORLESS.value == ""

    def test_color_full_names(self) -> None:
        """Test that color full names are correct."""
        assert Color.WHITE.full_name == "White"
        assert Color.BLUE.full_name == "Blue"
        assert Color.BLACK.full_name == "Black"
        assert Color.RED.full_name == "Red"
        assert Color.GREEN.full_name == "Green"
        assert Color.COLORLESS.full_name == "Colorless"

    def test_color_two_color_combinations(self) -> None:
        """Test that two-color combination values are correct."""
        assert Color.AZORIUS.value == "WU"
        assert Color.DIMIR.value == "UB"
        assert Color.RAKDOS.value == "BR"
        assert Color.GRUEL.value == "RG"
        assert Color.SELESNYA.value == "GW"
        assert Color.ORZHOV.value == "WB"
        assert Color.GOLGARI.value == "BG"
        assert Color.SIMIC.value == "UG"
        assert Color.BOROS.value == "RW"
        assert Color.IZZET.value == "UR"

    def test_color_three_color_combinations(self) -> None:
        """Test that three-color combination values are correct."""
        assert Color.BANT.value == "WUG"
        assert Color.ESPER.value == "WUB"
        assert Color.GRIXIS.value == "UBR"
        assert Color.JUND.value == "BRG"
        assert Color.NAYA.value == "RGW"
        assert Color.ABZAN.value == "WBG"
        assert Color.JESKAI.value == "WUR"
        assert Color.SULTIA.value == "URG"
        assert Color.MARDEK.value == "BWG"
        assert Color.TEMPO.value == "GWU"

    def test_color_four_color_combinations(self) -> None:
        """Test that four-color combination values are correct."""
        assert Color.WUBR.value == "WUBR"
        assert Color.WUBG.value == "WUBG"
        assert Color.WURG.value == "WURG"
        assert Color.WBRG.value == "WBRG"
        assert Color.UBRG.value == "UBRG"

    def test_color_five_color_combination(self) -> None:
        """Test that five-color combination value is correct."""
        assert Color.WUBRG.value == "WUBRG"

    def test_color_from_full_name(self) -> None:
        """Test from_full_name classmethod."""
        assert Color.from_full_name("White") == Color.WHITE
        assert Color.from_full_name("Blue") == Color.BLUE
        assert Color.from_full_name("Black") == Color.BLACK
        assert Color.from_full_name("Red") == Color.RED
        assert Color.from_full_name("Green") == Color.GREEN
        assert Color.from_full_name("Colorless") == Color.COLORLESS
        # Unknown color should return COLORLESS
        assert Color.from_full_name("Unknown") == Color.COLORLESS

    def test_color_from_colors(self) -> None:
        """Test from_colors classmethod for combining colors."""
        # Single color
        result = Color.from_colors([Color.WHITE])
        assert result == Color.WHITE

        # Two colors - WUBRG order: W then U = WU (AZORIUS)
        result = Color.from_colors([Color.WHITE, Color.BLUE])
        assert result == Color.AZORIUS
        assert result.value == "WU"

        # Two colors - input order shouldn't matter, output is WUBRG sorted
        result = Color.from_colors([Color.BLUE, Color.WHITE])
        assert result == Color.AZORIUS
        assert result.value == "WU"

        # Three colors - WUBRG order: W(0), U(1), G(4) = WUG
        result = Color.from_colors([Color.WHITE, Color.BLUE, Color.GREEN])
        assert result.value == "WUG"

    def test_color_contains(self) -> None:
        """Test __contains__ method."""
        assert Color.WHITE in Color.WUBRG
        assert Color.BLUE in Color.WUBRG
        assert Color.BLACK in Color.WUBRG
        assert Color.RED in Color.WUBRG
        assert Color.GREEN in Color.WUBRG
        assert Color.WHITE in Color.AZORIUS
        assert Color.BLUE in Color.AZORIUS
        assert Color.BLACK not in Color.AZORIUS

    def test_color_is_multicolor(self) -> None:
        """Test is_multicolor method."""
        assert not Color.WHITE.is_multicolor()
        assert not Color.COLORLESS.is_multicolor()
        assert Color.AZORIUS.is_multicolor()
        assert Color.WUBRG.is_multicolor()


class TestRarityEnum:
    """Tests for the Rarity enum."""

    def test_rarity_values(self) -> None:
        """Test that rarity values are correct."""
        assert Rarity.COMMON.value == "common"
        assert Rarity.UNCOMMON.value == "uncommon"
        assert Rarity.RARE.value == "rare"
        assert Rarity.MYTHIC.value == "mythic"
        assert Rarity.SPECIAL.value == "special"
        assert Rarity.BONUS.value == "bonus"


class TestFormatEnum:
    """Tests for the Format enum."""

    def test_format_values(self) -> None:
        """Test that format values are correct."""
        assert Format.STANDARD.value == "standard"
        assert Format.MODERN.value == "modern"
        assert Format.LEGACY.value == "legacy"
        assert Format.VINTAGE.value == "vintage"
        assert Format.COMMANDER.value == "commander"
        assert Format.PAUPER.value == "pauper"
        assert Format.PIONEER.value == "pioneer"


class TestBoardEnum:
    """Tests for the Board enum."""

    def test_board_values(self) -> None:
        """Test that board values are correct."""
        assert Board.MAIN.value == "main"
        assert Board.SIDEBOARD.value == "sideboard"
        assert Board.COMMANDER.value == "commander"
        assert Board.MAYBEBOARD.value == "maybeboard"


class TestSetTypeEnum:
    """Tests for the SetType enum."""

    def test_set_type_values(self) -> None:
        """Test that set type values are correct."""
        assert SetType.CORE.value == "core"
        assert SetType.EXPANSION.value == "expansion"
        assert SetType.REPRINT.value == "reprint"
        assert SetType.COMMANDER.value == "commander"


class TestCardFace:
    """Tests for the CardFace model."""

    def test_card_face_creation_with_all_fields(self) -> None:
        """Test CardFace creation with all fields."""
        face = CardFace(
            name="Black Lotus",
            mana_cost="{0}",
            type_line="Artifact",
            oracle_text="{T}, Sacrifice Black Lotus: Add {C}{C}{C}{C}{C}{C}{C}.",
            power=None,
            toughness=None,
            colors=[],
            color_indicator=None,
            loyalty=None,
            defense=None,
            flavor_text="The most powerful artifact in Magic.",
            artist="Christopher Rush",
            artist_id="c3187c14-28d6-4d66-8250-17735164d542",
            illustration_id="37a73755-584d-4508-8097-3847b839698a",
            image_uris={"small": "https://example.com/small.jpg"},
        )
        assert face.name == "Black Lotus"
        assert face.mana_cost == "{0}"
        assert face.type_line == "Artifact"
        assert face.flavor_text == "The most powerful artifact in Magic."

    def test_card_face_creation_minimal(self) -> None:
        """Test CardFace creation with minimal required fields."""
        face = CardFace(name="Test Face")
        assert face.name == "Test Face"
        assert face.mana_cost is None
        assert face.type_line is None

    def test_card_face_creation_missing_required_field(self) -> None:
        """Test CardFace creation fails when name is missing."""
        with pytest.raises(ValidationError) as exc_info:
            CardFace(mana_cost="{1}")  # type: ignore  # Intentional missing required parameter
        assert "name" in str(exc_info.value)


class TestLegality:
    """Tests for the Legality model."""

    def test_legality_creation(self) -> None:
        """Test Legality creation."""
        from pymtg.models.card import Legality

        legality = Legality(format=Format.STANDARD, status="legal")
        assert legality.format == Format.STANDARD
        assert legality.status == "legal"


class TestCard:
    """Tests for the Card model."""

    def test_card_creation_with_all_fields(self) -> None:
        """Test Card creation with all fields."""
        card = Card(
            id="test-id",
            scryfall_id="scryfall-uuid",
            oracle_id="oracle-uuid",
            name="Black Lotus",
            printed_name=None,
            mana_cost="{0}",
            cmc=0.0,
            type_line="Artifact",
            printed_type_line=None,
            oracle_text="{T}, Sacrifice Black Lotus: Add {C}{C}{C}{C}{C}{C}{C}.",
            printed_text=None,
            flavors=["The most powerful artifact in Magic."],
            colors=[],
            color_identity=[],
            color_indicator=None,
            keywords=["Sacrifice"],
            all_parts=None,
            card_faces=None,
            set_code="LEA",
            set_name="Limited Edition Alpha",
            set_type="core",
            rarity=Rarity.RARE,
            collector_number="1",
            power=None,
            toughness=None,
            loyalty=None,
            defense=None,
            layout="normal",
            image_uris={"small": "https://example.com/small.jpg"},
            image_status="highres_scan",
            pricing=None,
            legalities={"standard": "banned"},
            released_at="1993-08-05",
            reserved=True,
            foil=False,
            nonfoil=True,
            oversized=False,
            promo=True,
            reprint=False,
            variation=False,
            multiverse_ids=[1],
            tcgplayer_id=12345,
            cardmarket_id=67890,
            prints_search_uri="https://api.scryfall.com/cards/search?order=set&q=%211",
            rulings_uri="https://api.scryfall.com/cards/uuid/rulings",
            scryfall_uri="https://scryfall.com/card/lea/1/black-lotus",
            uri="https://example.com/black-lotus",
            source="scryfall",
        )
        assert card.name == "Black Lotus"
        assert card.set_code == "LEA"
        assert card.rarity == Rarity.RARE
        assert card.cmc == 0.0

    def test_card_creation_minimal(self) -> None:
        """Test Card creation with minimal required fields."""
        card = Card(id="test-id", name="Test Card")
        assert card.id == "test-id"
        assert card.name == "Test Card"
        assert card.scryfall_id is None
        assert card.mana_cost is None
        assert card.type_line is None

    def test_card_creation_missing_required_fields(self) -> None:
        """Test Card creation fails when required fields are missing."""
        with pytest.raises(ValidationError) as exc_info:
            Card(name="Test Card")  # type: ignore  # Intentional missing required parameter
        assert "id" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            Card(id="test-id")  # type: ignore  # Intentional missing required parameter
        assert "name" in str(exc_info.value)

    def test_card_color_helper_methods(self) -> None:
        """Test Card color helper methods."""
        # White card
        white_card = Card(
            id="white-id",
            name="White Card",
            color_identity=[Color.WHITE],
        )
        assert white_card.is_white() is True
        assert white_card.is_blue() is False
        assert white_card.is_black() is False
        assert white_card.is_red() is False
        assert white_card.is_green() is False
        assert white_card.is_colorless() is False
        assert white_card.is_multicolor() is False

        # Blue card
        blue_card = Card(
            id="blue-id",
            name="Blue Card",
            color_identity=[Color.BLUE],
        )
        assert blue_card.is_blue() is True
        assert blue_card.is_white() is False

        # Multicolor card
        multicolor_card = Card(
            id="multi-id",
            name="Multicolor Card",
            color_identity=[Color.WHITE, Color.BLUE, Color.BLACK],
        )
        assert multicolor_card.is_multicolor() is True
        assert multicolor_card.is_white() is True
        assert multicolor_card.is_blue() is True
        assert multicolor_card.is_black() is True
        assert multicolor_card.is_colorless() is False

        # Colorless card
        colorless_card = Card(
            id="colorless-id",
            name="Colorless Card",
            color_identity=[],
        )
        assert colorless_card.is_colorless() is True
        assert colorless_card.is_multicolor() is False

        # Card with no color_identity
        no_color_card = Card(id="no-color-id", name="No Color Card")
        assert no_color_card.is_colorless() is True

    def test_card_get_color_identity_string(self) -> None:
        """Test Card get_color_identity_string method."""
        # Single color - W
        card1 = Card(
            id="test1",
            name="Test1",
            color_identity=[Color.WHITE],
        )
        # With use_enum_values=True, Color.WHITE becomes "W"
        assert card1.get_color_identity_string() == "W"

        # Two colors - U and R, WUBRG order: U then R = UR
        card2 = Card(
            id="test2",
            name="Test2",
            color_identity=[Color.BLUE, Color.RED],
        )
        # BLUE.value="U", RED.value="R", WUBRG order: U(1) < R(3) = "UR"
        assert card2.get_color_identity_string() == "UR"

        # No color identity
        card3 = Card(id="test3", name="Test3")
        assert card3.get_color_identity_string() == ""

    def test_card_get_mana_value(self) -> None:
        """Test Card get_mana_value method."""
        card1 = Card(id="test1", name="Test1", cmc=3.5)
        assert card1.get_mana_value() == 3.5

        card2 = Card(id="test2", name="Test2")
        assert card2.get_mana_value() == 0.0

    def test_card_type_helper_methods(self) -> None:
        """Test Card type helper methods."""
        # Creature
        creature = Card(
            id="creature-id",
            name="Creature",
            type_line="Creature — Human Soldier",
        )
        assert creature.is_creature() is True
        assert creature.is_instant() is False
        assert creature.is_sorcery() is False
        assert creature.is_artifact() is False
        assert creature.is_enchantment() is False
        assert creature.is_land() is False
        assert creature.is_planeswalker() is False
        assert creature.is_battle() is False

        # Instant
        instant = Card(
            id="instant-id",
            name="Instant",
            type_line="Instant",
        )
        assert instant.is_instant() is True
        assert instant.is_creature() is False

        # Sorcery
        sorcery = Card(
            id="sorcery-id",
            name="Sorcery",
            type_line="Sorcery",
        )
        assert sorcery.is_sorcery() is True

        # Artifact
        artifact = Card(
            id="artifact-id",
            name="Artifact",
            type_line="Artifact",
        )
        assert artifact.is_artifact() is True

        # Enchantment
        enchantment = Card(
            id="enchantment-id",
            name="Enchantment",
            type_line="Enchantment",
        )
        assert enchantment.is_enchantment() is True

        # Land
        land = Card(
            id="land-id",
            name="Land",
            type_line="Land",
        )
        assert land.is_land() is True

        # Planeswalker
        planeswalker = Card(
            id="planeswalker-id",
            name="Planeswalker",
            type_line="Legendary Planeswalker — Jace",
        )
        assert planeswalker.is_planeswalker() is True

        # Battle
        battle = Card(
            id="battle-id",
            name="Battle",
            type_line="Battle — Siege",
        )
        assert battle.is_battle() is True

        # Card with no type line
        no_type = Card(id="no-type-id", name="No Type")
        assert no_type.is_creature() is False
        assert no_type.is_instant() is False

    def test_card_get_main_face(self) -> None:
        """Test Card get_main_face method."""
        # Card with faces
        face1 = CardFace(name="Front")
        face2 = CardFace(name="Back")
        card_with_faces = Card(
            id="test-id",
            name="Transform Card",
            card_faces=[face1, face2],
        )
        assert card_with_faces.get_main_face() == face1

        # Card without faces
        card_no_faces = Card(id="test-id", name="Normal Card")
        assert card_no_faces.get_main_face() is None

        # Card with empty faces list
        card_empty_faces = Card(id="test-id", name="Empty Faces", card_faces=[])
        assert card_empty_faces.get_main_face() is None

    def test_card_validate_main_face_consistency_consistent(self) -> None:
        """Test validate_main_face_consistency with matching fields.

        Verifies that when all shared fields between Card and its main face
        (card_faces[0]) are equal, the method returns an empty dict.
        """
        face = CardFace(
            name="Delver of Secrets",
            mana_cost="{1}{U}",
            type_line="Creature — Human Wizard",
            power="1",
            toughness="1",
        )
        card = Card(
            id="test-id",
            name="Delver of Secrets",
            mana_cost="{1}{U}",
            type_line="Creature — Human Wizard",
            power="1",
            toughness="1",
            card_faces=[face, CardFace(name="Insectile Aberration")],
        )
        assert card.validate_main_face_consistency() == {}

    def test_card_validate_main_face_consistency_mismatch(self) -> None:
        """Test validate_main_face_consistency with mismatched fields.

        Verifies that when shared fields between Card and its main face
        differ, the method returns a dict mapping field names to
        (card_value, face_value) tuples.
        """
        face = CardFace(
            name="Front Face",
            power="2",
            toughness="2",
        )
        card = Card(
            id="test-id",
            name="Top-Level Name",
            power="3",
            toughness="3",
            card_faces=[face],
        )
        mismatches = card.validate_main_face_consistency()
        assert "name" in mismatches
        assert mismatches["name"] == ("Top-Level Name", "Front Face")
        assert "power" in mismatches
        assert mismatches["power"] == ("3", "2")
        assert "toughness" in mismatches
        assert mismatches["toughness"] == ("3", "2")

    def test_card_validate_main_face_consistency_no_faces(self) -> None:
        """Test validate_main_face_consistency with no card_faces.

        Verifies that the method returns an empty dict when the card has
        no card_faces populated (card_faces defaults to None).
        """
        card = Card(id="test-id", name="Normal Card")
        assert card.validate_main_face_consistency() == {}

    def test_card_validate_main_face_consistency_explicit_none_faces(self) -> None:
        """Test validate_main_face_consistency with card_faces=None.

        Verifies that the method returns an empty dict when card_faces
        is explicitly set to None.
        """
        card = Card(id="test-id", name="None Faces", card_faces=None)
        assert card.validate_main_face_consistency() == {}

    def test_card_validate_main_face_consistency_empty_faces(self) -> None:
        """Test validate_main_face_consistency with empty card_faces list.

        Verifies that the method returns an empty dict when card_faces
        is an empty list.
        """
        card = Card(id="test-id", name="Empty Faces", card_faces=[])
        assert card.validate_main_face_consistency() == {}

    def test_card_validate_main_face_consistency_single_face(self) -> None:
        """Test validate_main_face_consistency with a single face.

        Verifies that the method works correctly for single-faced cards
        where all shared fields match between Card and card_faces[0].
        """
        face = CardFace(name="Single Face", power="2", toughness="2")
        card = Card(
            id="test-id",
            name="Single Face",
            power="2",
            toughness="2",
            card_faces=[face],
        )
        assert card.validate_main_face_consistency() == {}

    def test_card_validate_main_face_consistency_all_shared_fields(self) -> None:
        """Test validate_main_face_consistency with all shared fields matching.

        Verifies that the method returns an empty dict when all 14 fields
        shared between Card and CardFace are equal, including oracle_text,
        colors, color_indicator, loyalty, defense, artist, artist_id,
        illustration_id, and image_uris.
        """
        face = CardFace(
            name="Test Card",
            mana_cost="{1}{U}",
            type_line="Creature — Human Wizard",
            oracle_text="Test oracle text",
            power="1",
            toughness="1",
            colors=[Color.BLUE],
            color_indicator=[Color.BLUE],
            artist="Test Artist",
            artist_id="test-artist-id",
            illustration_id="test-illustration-id",
            image_uris={"small": "test-uri"},
        )
        card = Card(
            id="test-id",
            name="Test Card",
            mana_cost="{1}{U}",
            type_line="Creature — Human Wizard",
            oracle_text="Test oracle text",
            power="1",
            toughness="1",
            colors=[Color.BLUE],
            color_indicator=[Color.BLUE],
            artist="Test Artist",
            artist_id="test-artist-id",
            illustration_id="test-illustration-id",
            image_uris={"small": "test-uri"},
            card_faces=[face],
        )
        assert card.validate_main_face_consistency() == {}

    def test_card_validate_main_face_consistency_none_face_fields(self) -> None:
        """Test validate_main_face_consistency with None values in face fields.

        Verifies that the method correctly handles None values for
        individual face fields (e.g., power=None, toughness=None) using
        the != comparison, which treats None == None as consistent.
        """
        face = CardFace(
            name="Test Card",
            mana_cost=None,
            type_line=None,
            power=None,
            toughness=None,
        )
        card = Card(
            id="test-id",
            name="Test Card",
            mana_cost=None,
            type_line=None,
            power=None,
            toughness=None,
            card_faces=[face],
        )
        assert card.validate_main_face_consistency() == {}

    def test_card_validate_main_face_consistency_asymmetric_none(self) -> None:
        """Test validate_main_face_consistency with asymmetric None values.

        Verifies that the method correctly detects mismatches when one
        side has None and the other has a value (e.g., card.power=None
        vs face.power='2').
        """
        face = CardFace(name="Test Card", power="2", toughness="2")
        card = Card(
            id="test-id",
            name="Test Card",
            power=None,
            toughness="2",
            card_faces=[face],
        )
        mismatches = card.validate_main_face_consistency()
        assert "power" in mismatches
        assert mismatches["power"] == (None, "2")
        assert "toughness" not in mismatches

    def test_card_validate_main_face_consistency_none_in_faces_raises(self) -> None:
        """Test that None values in card_faces are rejected by pydantic.

        Verifies that pydantic enforces the list[CardFace] type and
        rejects None values in card_faces, preventing the edge case
        where get_main_face would return None for a non-empty list.

        Note:
            The `# type: ignore` comment is used because passing None
            as a list element is intentionally invalid input to test
            pydantic's runtime validation, but static type checkers
            would flag it as a type error.
        """
        with pytest.raises(ValidationError):
            Card(
                id="test-id",
                name="None Face",
                card_faces=[None],  # type: ignore  # Intentional invalid list element
            )

    def test_card_serialization(self) -> None:
        """Test Card serialization and deserialization."""
        card = Card(
            id="test-id",
            name="Test Card",
            set_code="TEST",
            rarity=Rarity.COMMON,
            cmc=2.0,
        )

        # Test model_dump
        data = card.model_dump()
        assert data["id"] == "test-id"
        assert data["name"] == "Test Card"
        assert data["set_code"] == "TEST"
        assert data["rarity"] == "common"
        assert data["cmc"] == 2.0

        # Test model_dump_json
        json_str = card.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["id"] == "test-id"
        assert parsed["name"] == "Test Card"

        # Test model_validate (deserialization)
        restored = Card.model_validate(data)
        assert restored.id == card.id
        assert restored.name == card.name
        assert restored.set_code == card.set_code
        assert restored.rarity == card.rarity

    def test_card_validation_invalid_types(self) -> None:
        """Test Card validation with invalid types."""
        # Invalid cmc type
        with pytest.raises(ValidationError):
            Card(id="test-id", name="Test", cmc="not-a-float")  # type: ignore  # Intentional invalid type

        # Invalid rarity type
        with pytest.raises(ValidationError):
            Card(id="test-id", name="Test", rarity="invalid_rarity")  # type: ignore  # Intentional invalid type


class TestDeckCard:
    """Tests for the DeckCard model."""

    def test_deck_card_creation(self) -> None:
        """Test DeckCard creation."""
        card = Card(id="card-id", name="Test Card")
        deck_card = DeckCard(card=card, count=4, board=Board.MAIN.value)
        assert deck_card.card == card
        assert deck_card.count == 4
        assert deck_card.board == Board.MAIN.value

    def test_deck_card_creation_minimal(self) -> None:
        """Test DeckCard creation with minimal fields."""
        card = Card(id="card-id", name="Test Card")
        deck_card = DeckCard(card=card, count=1)
        assert deck_card.card == card
        assert deck_card.count == 1
        assert deck_card.board is None

    def test_deck_card_validation(self) -> None:
        """Test DeckCard validation."""
        card = Card(id="card-id", name="Test Card")

        # Count field has no constraints, so various values are allowed
        # Test that DeckCard accepts different count values
        deck_card_zero = DeckCard(card=card, count=0)
        assert deck_card_zero.count == 0

        deck_card_negative = DeckCard(card=card, count=-1)
        assert deck_card_negative.count == -1

        deck_card_large = DeckCard(card=card, count=100)
        assert deck_card_large.count == 100


class TestDeck:
    """Tests for the Deck model."""

    def test_deck_creation_with_all_fields(self) -> None:
        """Test Deck creation with all fields."""
        card1 = Card(id="card1", name="Card 1")
        card2 = Card(id="card2", name="Card 2")
        deck_card1 = DeckCard(card=card1, count=4)
        deck_card2 = DeckCard(card=card2, count=2)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            description="A test deck",
            format=Format.STANDARD,
            commander=["card1"],
            cards=[deck_card1],
            sideboard=[deck_card2],
            maybe_board=[],
            source="test",
            source_id="source-id",
            url="https://example.com/deck",
            created_at="2024-01-01",
            updated_at="2024-01-02",
            views=100,
            upvotes=10,
            downvotes=2,
            tags=["test", "deck"],
            categories=["category1"],
            privacy="public",
            owner="testuser",
            owner_id="owner-id",
            collapsed=False,
        )
        assert deck.name == "Test Deck"
        assert deck.format == Format.STANDARD
        assert deck.cards == [deck_card1]
        assert deck.sideboard == [deck_card2]

    def test_deck_creation_minimal(self) -> None:
        """Test Deck creation with minimal fields."""
        deck = Deck(id="deck-id", name="Test Deck")
        assert deck.id == "deck-id"
        assert deck.name == "Test Deck"
        assert deck.description is None
        assert deck.cards is None

    def test_deck_get_main_deck_cards(self) -> None:
        """Test Deck get_main_deck_cards method."""
        card1 = Card(id="card1", name="Card 1")
        card2 = Card(id="card2", name="Card 2")
        card3 = Card(id="card3", name="Card 3")

        deck_card1 = DeckCard(card=card1, count=4, board=Board.MAIN.value)
        deck_card2 = DeckCard(card=card2, count=2, board=Board.SIDEBOARD.value)
        deck_card3 = DeckCard(card=card3, count=1, board=Board.MAIN.value)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            cards=[deck_card1, deck_card2, deck_card3],
        )

        main_cards = deck.get_main_deck_cards()
        assert len(main_cards) == 2
        assert deck_card1 in main_cards
        assert deck_card3 in main_cards
        assert deck_card2 not in main_cards

    def test_deck_get_sideboard_cards(self) -> None:
        """Test Deck get_sideboard_cards method."""
        card1 = Card(id="card1", name="Card 1")
        card2 = Card(id="card2", name="Card 2")

        deck_card1 = DeckCard(card=card1, count=4, board=Board.MAIN.value)
        deck_card2 = DeckCard(card=card2, count=2, board=Board.SIDEBOARD.value)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            cards=[deck_card1, deck_card2],
        )

        sideboard_cards = deck.get_sideboard_cards()
        assert len(sideboard_cards) == 1
        assert deck_card2 in sideboard_cards

    def test_deck_get_maybeboard_cards(self) -> None:
        """Test Deck get_maybeboard_cards method."""
        card1 = Card(id="card1", name="Card 1")
        maybeboard_card = DeckCard(card=card1, count=1)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            maybe_board=[maybeboard_card],
        )

        maybeboard_cards = deck.get_maybeboard_cards()
        assert len(maybeboard_cards) == 1
        assert maybeboard_card in maybeboard_cards

    def test_deck_get_commander_cards(self) -> None:
        """Test Deck get_commander_cards method."""
        card1 = Card(id="card1", name="Commander 1")
        card2 = Card(id="card2", name="Card 2")

        commander_card = DeckCard(card=card1, count=1, board=Board.COMMANDER.value)
        deck_card = DeckCard(card=card2, count=4, board=Board.MAIN.value)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            cards=[commander_card, deck_card],
        )

        commander_cards = deck.get_commander_cards()
        assert len(commander_cards) == 1
        assert commander_card in commander_cards

    def test_deck_get_total_cards(self) -> None:
        """Test Deck get_total_cards method."""
        card1 = Card(id="card1", name="Card 1")
        card2 = Card(id="card2", name="Card 2")
        card3 = Card(id="card3", name="Card 3")

        main_card1 = DeckCard(card=card1, count=4)
        main_card2 = DeckCard(card=card2, count=2)
        sideboard_card = DeckCard(card=card3, count=3)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            cards=[main_card1, main_card2],
            sideboard=[sideboard_card],
        )

        total = deck.get_total_cards()
        assert total == 9  # 4 + 2 + 3

    def test_deck_get_card_count(self) -> None:
        """Test Deck get_card_count method."""
        card1 = Card(id="card1", name="Lightning Bolt")
        card2 = Card(id="card2", name="Lightning Bolt")  # Same name, different ID
        card3 = Card(id="card3", name="Mountain")

        deck_card1 = DeckCard(card=card1, count=4)
        deck_card2 = DeckCard(card=card2, count=2)  # Should count with card1
        deck_card3 = DeckCard(card=card3, count=1)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            cards=[deck_card1, deck_card2, deck_card3],
        )

        # Should find both Lightning Bolts
        count = deck.get_card_count("Lightning Bolt")
        assert count == 6

        # Case insensitive
        count_lower = deck.get_card_count("lightning bolt")
        assert count_lower == 6

        # Mountain
        count_mountain = deck.get_card_count("Mountain")
        assert count_mountain == 1

        # Non-existent card
        count_none = deck.get_card_count("Non-existent")
        assert count_none == 0

    def test_deck_get_unique_cards(self) -> None:
        """Test Deck get_unique_cards method."""
        card1 = Card(id="card1", name="Lightning Bolt")
        card2 = Card(id="card2", name="Lightning Bolt")  # Same name
        card3 = Card(id="card3", name="Mountain")

        deck_card1 = DeckCard(card=card1, count=4)
        deck_card2 = DeckCard(card=card2, count=2)
        deck_card3 = DeckCard(card=card3, count=1)

        deck = Deck(
            id="deck-id",
            name="Test Deck",
            cards=[deck_card1, deck_card2, deck_card3],
        )

        unique_cards = deck.get_unique_cards()
        # Should have 2 unique names: Lightning Bolt and Mountain
        assert len(unique_cards) == 2

    def test_deck_is_valid_for_format(self) -> None:
        """Test Deck is_valid_for_format method (placeholder)."""
        deck = Deck(id="deck-id", name="Test Deck")
        # This is a placeholder that always returns True
        assert deck.is_valid_for_format() is True


class TestSet:
    """Tests for the Set model."""

    def test_set_creation_with_all_fields(self) -> None:
        """Test Set creation with all fields."""
        set_obj = Set(
            code="LEA",
            name="Limited Edition Alpha",
            set_type=SetType.CORE,
            released_at="1993-08-05",
            block_code="LEA",
            block_name="Limited Edition",
            parent_set_code=None,
            card_count=295,
            printed_size=295,
            digital=False,
            foil_only=False,
            nonfoil_only=False,
            icon_svg_uri="https://example.com/icon.svg",
            search_uri="https://api.scryfall.com/cards/search?order=set&q=%21LEA",
            scryfall_uri="https://scryfall.com/sets/lea",
            uri="https://example.com/sets/lea",
            source="scryfall",
            mtgo_code="LEA",
            arena_code=None,
            tcgplayer_id=1234,
            cardmarket_id=5678,
        )
        assert set_obj.code == "LEA"
        assert set_obj.name == "Limited Edition Alpha"
        assert set_obj.set_type == SetType.CORE
        assert set_obj.card_count == 295

    def test_set_creation_minimal(self) -> None:
        """Test Set creation with minimal fields."""
        set_obj = Set(code="TEST", name="Test Set")
        assert set_obj.code == "TEST"
        assert set_obj.name == "Test Set"
        assert set_obj.set_type is None
        assert set_obj.released_at is None

    def test_set_validation(self) -> None:
        """Test Set validation."""
        # Missing required fields
        with pytest.raises(ValidationError):
            Set(code="TEST")  # type: ignore  # Intentional missing required parameter

        with pytest.raises(ValidationError):
            Set(name="Test Set")  # type: ignore  # Intentional missing required parameter


class TestScryfallPricing:
    """Tests for the ScryfallPricing model."""

    def test_scryfall_pricing_creation(self) -> None:
        """Test ScryfallPricing creation."""
        pricing = ScryfallPricing(
            usd=10.50,
            usd_foil=15.75,
            usd_etched=20.00,
            eur=8.99,
            eur_foil=12.99,
            tix=10.0,
        )
        assert pricing.usd == 10.50
        assert pricing.usd_foil == 15.75
        assert pricing.tix == 10.0

    def test_scryfall_pricing_creation_minimal(self) -> None:
        """Test ScryfallPricing creation with all fields None."""
        pricing = ScryfallPricing()
        assert pricing.usd is None
        assert pricing.usd_foil is None
        assert pricing.tix is None


class TestTCGPlayerPricing:
    """Tests for the TCGPlayerPricing model."""

    def test_tcgplayer_pricing_creation(self) -> None:
        """Test TCGPlayerPricing creation."""
        pricing = TCGPlayerPricing(
            market=10.50,
            mid=10.00,
            low=5.00,
            high=20.00,
            direct_low=8.00,
        )
        assert pricing.market == 10.50
        assert pricing.mid == 10.00
        assert pricing.low == 5.00

    def test_tcgplayer_pricing_creation_minimal(self) -> None:
        """Test TCGPlayerPricing creation with all fields None."""
        pricing = TCGPlayerPricing()
        assert pricing.market is None
        assert pricing.mid is None


class TestCardmarketPricing:
    """Tests for the CardmarketPricing model."""

    def test_cardmarket_pricing_creation(self) -> None:
        """Test CardmarketPricing creation."""
        pricing = CardmarketPricing(
            avg1=10.50,
            avg7=10.25,
            avg30=10.00,
            low=5.00,
            low_ex=6.00,
            trend=1.5,
        )
        assert pricing.avg1 == 10.50
        assert pricing.avg7 == 10.25
        assert pricing.low == 5.00

    def test_cardmarket_pricing_creation_minimal(self) -> None:
        """Test CardmarketPricing creation with all fields None."""
        pricing = CardmarketPricing()
        assert pricing.avg1 is None
        assert pricing.avg7 is None


class TestPricing:
    """Tests for the unified Pricing model."""

    def test_pricing_creation_with_all_providers(self) -> None:
        """Test Pricing creation with all provider data."""
        scryfall_data = ScryfallPricing(usd=10.50, eur=8.99)
        tcgplayer_data = TCGPlayerPricing(market=10.00, mid=9.50)
        cardmarket_data = CardmarketPricing(avg1=10.25, low=8.00)

        pricing = Pricing(
            scryfall=scryfall_data,
            tcgplayer=tcgplayer_data,
            cardmarket=cardmarket_data,
        )
        assert pricing.scryfall == scryfall_data
        assert pricing.tcgplayer == tcgplayer_data
        assert pricing.cardmarket == cardmarket_data

    def test_pricing_creation_minimal(self) -> None:
        """Test Pricing creation with all fields None."""
        pricing = Pricing()
        assert pricing.scryfall is None
        assert pricing.tcgplayer is None
        assert pricing.cardmarket is None

    def test_pricing_creation_partial(self) -> None:
        """Test Pricing creation with only some providers."""
        scryfall_data = ScryfallPricing(usd=10.50)
        pricing = Pricing(scryfall=scryfall_data)
        assert pricing.scryfall == scryfall_data
        assert pricing.tcgplayer is None
        assert pricing.cardmarket is None

    def test_scryfall_pricing_currencies_classvar(self) -> None:
        """Test ScryfallPricing declares its CURRENCIES ClassVar."""
        assert ScryfallPricing.CURRENCIES == ("usd", "eur", "tix")

    def test_tcgplayer_pricing_currency_classvar(self) -> None:
        """Test TCGPlayerPricing declares its CURRENCIES ClassVar as usd."""
        assert TCGPlayerPricing.CURRENCIES == ("usd",)

    def test_cardmarket_pricing_currency_classvar(self) -> None:
        """Test CardmarketPricing declares its CURRENCIES ClassVar as eur."""
        assert CardmarketPricing.CURRENCIES == ("eur",)

    def test_scryfall_pricing_get_currencies_all_set(self) -> None:
        """Test get_currencies returns all three currencies when set."""
        pricing = ScryfallPricing(usd=10.0, eur=8.0, tix=5.0)
        assert pricing.get_currencies() == {
            "usd": 10.0,
            "eur": 8.0,
            "tix": 5.0,
        }

    def test_scryfall_pricing_get_currencies_none(self) -> None:
        """Test get_currencies returns None for unset currencies."""
        pricing = ScryfallPricing()
        assert pricing.get_currencies() == {
            "usd": None,
            "eur": None,
            "tix": None,
        }

    def test_scryfall_pricing_get_currencies_partial(self) -> None:
        """Test get_currencies returns only set values, others None."""
        pricing = ScryfallPricing(usd=10.0)
        currencies = pricing.get_currencies()
        assert currencies["usd"] == 10.0
        assert currencies["eur"] is None
        assert currencies["tix"] is None

    def test_tcgplayer_pricing_has_prices_true(self) -> None:
        """Test has_prices returns True when at least one field is set."""
        assert TCGPlayerPricing(market=10.0).has_prices() is True
        assert TCGPlayerPricing(poor=0.50).has_prices() is True

    def test_tcgplayer_pricing_has_prices_false(self) -> None:
        """Test has_prices returns False when no fields are set."""
        assert TCGPlayerPricing().has_prices() is False

    def test_tcgplayer_pricing_has_prices_zero(self) -> None:
        """Test has_prices returns True when a field is set to 0.

        A price of 0.0 is a valid price (e.g., a free card), so it
        should count as having a price set.
        """
        assert TCGPlayerPricing(market=0.0).has_prices() is True

    def test_tcgplayer_pricing_has_prices_explicit_none(self) -> None:
        """Test has_prices returns False when all fields are explicit None."""
        pricing = TCGPlayerPricing(
            market=None,
            mid=None,
            low=None,
            high=None,
            direct_low=None,
        )
        assert pricing.has_prices() is False

    def test_cardmarket_pricing_has_prices_true(self) -> None:
        """Test has_prices returns True when at least one field is set."""
        assert CardmarketPricing(avg1=10.0).has_prices() is True
        assert CardmarketPricing(trend=1.5).has_prices() is True

    def test_cardmarket_pricing_has_prices_false(self) -> None:
        """Test has_prices returns False when no fields are set."""
        assert CardmarketPricing().has_prices() is False

    def test_cardmarket_pricing_has_prices_zero(self) -> None:
        """Test has_prices returns True when a field is set to 0.

        A price of 0.0 is a valid price, so it should count as having
        a price set.
        """
        assert CardmarketPricing(avg1=0.0).has_prices() is True

    def test_cardmarket_pricing_has_prices_explicit_none(self) -> None:
        """Test has_prices returns False when all fields are explicit None."""
        pricing = CardmarketPricing(
            avg1=None,
            avg7=None,
            avg30=None,
            low=None,
            low_ex=None,
            trend=None,
        )
        assert pricing.has_prices() is False

    def test_pricing_validate_currency_consistency_empty(self) -> None:
        """Test validate_currency_consistency with no providers set."""
        assert Pricing().validate_currency_consistency() == {}

    def test_pricing_validate_currency_consistency_providers_no_prices(
        self,
    ) -> None:
        """Test validate_currency_consistency omits providers with no prices."""
        pricing = Pricing(
            scryfall=ScryfallPricing(),
            tcgplayer=TCGPlayerPricing(),
            cardmarket=CardmarketPricing(),
        )
        assert pricing.validate_currency_consistency() == {}

    def test_pricing_validate_currency_consistency_scryfall_only(self) -> None:
        """Test validate_currency_consistency with only Scryfall populated."""
        pricing = Pricing(scryfall=ScryfallPricing(usd=10.0, eur=8.0, tix=5.0))
        result = pricing.validate_currency_consistency()
        assert result == {
            "usd": ["scryfall"],
            "eur": ["scryfall"],
            "tix": ["scryfall"],
        }

    def test_pricing_validate_currency_consistency_scryfall_partial(
        self,
    ) -> None:
        """Test validate_currency_consistency omits unset Scryfall currencies."""
        pricing = Pricing(scryfall=ScryfallPricing(usd=10.0))
        result = pricing.validate_currency_consistency()
        assert result == {"usd": ["scryfall"]}

    def test_pricing_validate_currency_consistency_all_providers(self) -> None:
        """Test validate_currency_consistency with all providers populated."""
        pricing = Pricing(
            scryfall=ScryfallPricing(usd=10.0, eur=8.0, tix=5.0),
            tcgplayer=TCGPlayerPricing(market=10.00),
            cardmarket=CardmarketPricing(avg1=10.25),
        )
        result = pricing.validate_currency_consistency()
        assert result == {
            "usd": ["scryfall", "tcgplayer"],
            "eur": ["scryfall", "cardmarket"],
            "tix": ["scryfall"],
        }

    def test_pricing_validate_currency_consistency_tcgplayer_only(self) -> None:
        """Test validate_currency_consistency with only TCGPlayer populated."""
        pricing = Pricing(tcgplayer=TCGPlayerPricing(market=10.00))
        result = pricing.validate_currency_consistency()
        assert result == {"usd": ["tcgplayer"]}

    def test_pricing_validate_currency_consistency_cardmarket_only(
        self,
    ) -> None:
        """Test validate_currency_consistency with only Cardmarket populated."""
        pricing = Pricing(cardmarket=CardmarketPricing(avg1=10.25))
        result = pricing.validate_currency_consistency()
        assert result == {"eur": ["cardmarket"]}

    def test_pricing_validate_currency_consistency_mixed_partial(self) -> None:
        """Test validate_currency_consistency with mixed partial providers."""
        pricing = Pricing(
            scryfall=ScryfallPricing(usd=10.0),
            tcgplayer=TCGPlayerPricing(),
            cardmarket=CardmarketPricing(avg1=10.25),
        )
        result = pricing.validate_currency_consistency()
        assert result == {
            "usd": ["scryfall"],
            "eur": ["cardmarket"],
        }


class TestPyMTGBaseModel:
    """Tests for the PyMTGBaseModel base class."""

    def test_base_model_configuration(self) -> None:
        """Test that PyMTGBaseModel has correct configuration."""

        # Create a simple model for testing
        class TestModel(PyMTGBaseModel):
            """Test model for base model configuration testing."""

            value: str

        # Test extra fields are forbidden
        with pytest.raises(ValidationError):
            TestModel(value="test", extra_field="not_allowed")  # type: ignore  # Intentional extra field

        # Test from_attributes works
        data = {"value": "test"}
        model = TestModel.model_validate(data)
        assert model.value == "test"

    def test_base_model_strip_whitespace(self) -> None:
        """Test that string fields have whitespace stripped."""

        class TestModel(PyMTGBaseModel):
            """Test model for whitespace stripping testing."""

            value: str

        model = TestModel(value="  test  ")
        assert model.value == "test"

    def test_base_model_use_enum_values(self) -> None:
        """Test that enum values are used correctly."""

        class TestModel(PyMTGBaseModel):
            """Test model for enum value testing."""

            color: Color

        # Should accept enum value string
        model1 = TestModel(color=Color("W"))
        assert model1.color == Color.WHITE

        # Should accept enum instance
        model2 = TestModel(color=Color.BLUE)
        assert model2.color == Color.BLUE


class TestModelSerialization:
    """Tests for model serialization and deserialization."""

    def test_card_json_roundtrip(self) -> None:
        """Test Card JSON serialization and deserialization."""
        original = Card(
            id="test-id",
            name="Black Lotus",
            set_code="LEA",
            rarity=Rarity.RARE,
            cmc=0.0,
            colors=[],
            color_identity=[],
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize from JSON
        restored = Card.model_validate_json(json_str)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.set_code == original.set_code
        assert restored.rarity == original.rarity
        assert restored.cmc == original.cmc

    def test_deck_json_roundtrip(self) -> None:
        """Test Deck JSON serialization and deserialization."""
        card = Card(id="card-id", name="Test Card")
        deck_card = DeckCard(card=card, count=4)

        original = Deck(
            id="deck-id",
            name="Test Deck",
            format=Format.STANDARD,
            cards=[deck_card],
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize from dict
        restored = Deck.model_validate(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.format == original.format
        assert len(restored.cards or []) == 1

    def test_set_json_roundtrip(self) -> None:
        """Test Set JSON serialization and deserialization."""
        original = Set(
            code="LEA",
            name="Limited Edition Alpha",
            set_type=SetType.CORE,
            card_count=295,
        )

        json_str = original.model_dump_json()
        restored = Set.model_validate_json(json_str)

        assert restored.code == original.code
        assert restored.name == original.name
        assert restored.set_type == original.set_type
        assert restored.card_count == original.card_count

    def test_pricing_json_roundtrip(self) -> None:
        """Test Pricing JSON serialization and deserialization."""
        scryfall_data = ScryfallPricing(usd=10.50, eur=8.99)
        original = Pricing(scryfall=scryfall_data)

        json_str = original.model_dump_json()
        restored = Pricing.model_validate_json(json_str)

        assert restored.scryfall is not None
        assert original.scryfall is not None
        assert restored.scryfall.usd == original.scryfall.usd
        assert restored.scryfall.eur == original.scryfall.eur
