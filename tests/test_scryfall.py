"""
Tests for the ScryfallClient class.

This module contains tests for the ScryfallClient class to ensure it fetches card data correctly.
"""

import pytest
from pymtg.scryfall import ScryfallClient, CardNotFoundError


@pytest.mark.asyncio
async def test_fetch_card():
    """
    Test fetching a card that exists.

    This test ensures that the ScryfallClient can fetch a card that exists.
    """
    client = ScryfallClient()
    card = await client.fetch_card("Black Lotus")
    assert card.name == "Black Lotus"


@pytest.mark.asyncio
async def test_fetch_nonexistent_card():
    """
    Test fetching a card that does not exist.

    This test ensures that the ScryfallClient raises a CardNotFoundError when a card does not exist.
    """
    client = ScryfallClient()
    with pytest.raises(CardNotFoundError):
        await client.fetch_card("Nonexistent Card")
