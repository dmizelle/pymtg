


import pytest
from pymtg.scryfall import ScryfallClient, CardNotFoundError

@pytest.mark.asyncio
async def test_fetch_card():
    client = ScryfallClient()
    card = await client.fetch_card("Black Lotus")
    assert card.name == "Black Lotus"

@pytest.mark.asyncio
async def test_fetch_nonexistent_card():
    client = ScryfallClient()
    with pytest.raises(CardNotFoundError):
        await client.fetch_card("Nonexistent Card")


