

import aiohttp
from typing import Optional
from ..card import Card

class CardNotFoundError(Exception):
    pass

class ScryfallClient:
    def __init__(self):
        self.base_url = "https://api.scryfall.com"

    async def fetch_card(self, card_name: str) -> Optional[Card]:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/cards/named?exact={card_name}"
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

