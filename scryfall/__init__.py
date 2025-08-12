"""
A client for interacting with the Scryfall API.

This module provides a client to fetch Magic: The Gathering card data from the Scryfall API.
"""

import aiohttp

from ..card import Card


class CardNotFoundError(Exception):
    """
    Exception raised when a card is not found.
    """

    pass


class ScryfallClient:
    """
    A client for interacting with the Scryfall API.
    """

    def __init__(self):
        """
        Initialize a new ScryfallClient instance.
        """
        self.base_url: str = (
            "https://api.scryfall.com"  # The base URL for the Scryfall API.
        )

    async def fetch_card(self, card_name: str) -> Card | None:
        """
        Fetch a card by its name.

        Args:
            card_name (str): The name of the card to fetch.

        Returns:
            Card | None: The card data if found, otherwise None.

        Raises:
            CardNotFoundError: If the card is not found.
        """
        async with aiohttp.ClientSession() as session:
            url: str = f"{self.base_url}/cards/named?exact={card_name}"
            async with session.get(url) as response:
                if response.status == 404:
                    raise CardNotFoundError(f"Card '{card_name}' not found.")
                response.raise_for_status()
                data = await response.json()

                return Card(
                    name=data.get("name"),
                    converted_mana_cost=data.get("cmc"),
                    type_line=data.get("type_line"),
                    oracle_text=data.get("oracle_text"),
                    colors=data.get("colors"),
                    color_identity=data.get("color_identity"),
                    power=data.get("power"),
                    toughness=data.get("toughness"),
                    loyalty=data.get("loyalty"),
                    image_uris=data.get("image_uris"),
                )
