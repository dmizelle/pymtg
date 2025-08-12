
from typing import List, Optional, Dict, Any

class Card:
    def __init__(
        self,
        name: str,
        converted_mana_cost: float,
        type_line: str,
        oracle_text: Optional[str] = None,
        colors: Optional[List[str]] = None,
        color_identity: Optional[List[str]] = None,
        power: Optional[str] = None,
        toughness: Optional[str] = None,
        loyalty: Optional[str] = None,
        image_uris: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.converted_mana_cost = converted_mana_cost
        self.type_line = type_line
        self.oracle_text = oracle_text
        self.colors = colors
        self.color_identity = color_identity
        self.power = power
        self.toughness = toughness
        self.loyalty = loyalty
        self.image_uris = image_uris

    def __repr__(self):
        return f"Card(name={self.name}, cmc={self.converted_mana_cost})"
