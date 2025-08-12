"""
A class representing a Magic: The Gathering card.

This class is used to store and manage card data.

Attributes:
    name (str): The name of the card.
    converted_mana_cost (float): The converted mana cost of the card.
    type_line (str): The type line of the card.
    oracle_text (str | None): The oracle text of the card.
    colors (list[str] | None): The colors of the card.
    color_identity (list[str] | None): The color identity of the card.
    power (str | None): The power of the card.
    toughness (str | None): The toughness of the card.
    loyalty (str | None): The loyalty of the card.
    image_uris (dict[str, str] | None): The image URIs of the card.
"""

from typing import List, Dict, Any


class Card:
    """
    A class representing a Magic: The Gathering card.
    """

    def __init__(
        self,
        name: str,
        converted_mana_cost: float,
        type_line: str,
        oracle_text: str | None = None,
        colors: list[str] | None = None,
        color_identity: list[str] | None = None,
        power: str | None = None,
        toughness: str | None = None,
        loyalty: str | None = None,
        image_uris: dict[str, str] | None = None,
    ):
        """
        Initialize a new Card instance.

        Args:
            name (str): The name of the card.
            converted_mana_cost (float): The converted mana cost of the card.
            type_line (str): The type line of the card.
            oracle_text (str | None): The oracle text of the card.
            colors (list[str] | None): The colors of the card.
            color_identity (list[str] | None): The color identity of the card.
            power (str | None): The power of the card.
            toughness (str | None): The toughness of the card.
            loyalty (str | None): The loyalty of the card.
            image_uris (dict[str, str] | None): The image URIs of the card.
        """
        self.name: str = name  # The name of the card.
        self.converted_mana_cost: float = (
            converted_mana_cost  # The converted mana cost of the card.
        )
        self.type_line: str = type_line  # The type line of the card.
        self.oracle_text: str | None = oracle_text  # The oracle text of the card.
        self.colors: list[str] | None = colors  # The colors of the card.
        self.color_identity: list[str] | None = (
            color_identity  # The color identity of the card.
        )
        self.power: str | None = power  # The power of the card.
        self.toughness: str | None = toughness  # The toughness of the card.
        self.loyalty: str | None = loyalty  # The loyalty of the card.
        self.image_uris: dict[str, str] | None = (
            image_uris  # The image URIs of the card.
        )

    def __repr__(self) -> str:
        """
        Return a string representation of the Card instance.

        Returns:
            str: A string representation of the Card instance.
        """
        return f"Card(name={self.name}, cmc={self.converted_mana_cost})"
