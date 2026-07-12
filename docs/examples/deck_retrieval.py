#!/usr/bin/env python3
"""Deck Retrieval Example for pymtg.

This example demonstrates deck retrieval functionality using authenticated providers.
It shows how to:
- Work with deckbuilding providers (Archidekt, Moxfield)
- Retrieve decks by ID
- Get user decks
- Search for decks
- Work with the returned Deck objects
- Handle authentication

Note: This example uses placeholder credentials. You must replace them with your
actual credentials or set environment variables for authentication to work.

Environment Variables:
    ARCHIDEKT_USERNAME: Your Archidekt username
    ARCHIDEKT_PASSWORD: Your Archidekt password
    MOXFIELD_API_KEY: Your Parse.bot API key for Moxfield
    TCGPLAYER_CLIENT_ID: Your TCGPlayer OAuth2 client ID
    TCGPLAYER_CLIENT_SECRET: Your TCGPlayer OAuth2 client secret
    CARDMARKET_CLIENT_ID: Your Cardmarket OAuth2 client ID
    CARDMARKET_CLIENT_SECRET: Your Cardmarket OAuth2 client secret

Usage:
    uv run python docs/examples/deck_retrieval.py
"""

import os
import pymtg
from pymtg.models import Format


def get_archidekt_credentials():
    """Get Archidekt credentials from environment variables.
    
    Returns:
        Tuple of (username, password).
    
    Raises:
        ValueError: If ARCHIDEKT_USERNAME or ARCHIDEKT_PASSWORD is not set.
    """
    username = os.getenv("ARCHIDEKT_USERNAME")
    password = os.getenv("ARCHIDEKT_PASSWORD")
    if not username or not password:
        raise ValueError(
            "ARCHIDEKT_USERNAME and ARCHIDEKT_PASSWORD environment variables "
            "must both be set. Please set them before running this example."
        )
    return username, password


def get_moxfield_api_key():
    """Get Moxfield API key from environment variables.

    Returns:
        The Moxfield API key.

    Raises:
        ValueError: If MOXFIELD_API_KEY environment variable is not set.
    """
    api_key = os.getenv("MOXFIELD_API_KEY")
    if not api_key:
        raise ValueError(
            "MOXFIELD_API_KEY environment variable is not set. "
            "Please set it before running this example."
        )
    return api_key


def main():
    """Demonstrate deck retrieval functionality."""
    print("=== pymtg Deck Retrieval Example ===\n")

    # =========================================================================
    # Example 1: Scryfall - No authentication needed (public API)
    # =========================================================================
    print("1. Scryfall Provider (no authentication required)...")
    print("   Note: Scryfall is a card database, not a deckbuilding site.")
    print("   For decks, use Archidekt or Moxfield below.\n")

    # =========================================================================
    # Example 2: Archidekt - Session-based authentication
    # =========================================================================
    print("2. Archidekt Provider (session authentication)...")
    username, password = get_archidekt_credentials()

    if not username or not password:
        print("   Skipping Archidekt examples - no credentials provided.")
        print("   Set ARCHIDEKT_USERNAME and ARCHIDEKT_PASSWORD environment variables.")
        print()
    else:
        try:
            # Initialize with credentials
            print("   Initializing Archidekt provider...")
            archidekt = pymtg.Archidekt(username=username, password=password)

            # Check authentication
            print(f"   Authenticated: {archidekt.is_authenticated()}")
            print()

            # Example: Get a specific deck by ID
            # Replace with an actual deck ID from your account
            print("   a) Getting a specific deck by ID...")
            try:
                # This is a placeholder - use a real deck ID
                # deck_id = "your-deck-id-here"
                # deck = archidekt.get_deck(deck_id)
                print("      Note: Provide a deck ID to fetch a specific deck")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

            # Example: Get user's decks
            print("   b) Getting user's decks...")
            try:
                user_decks = archidekt.get_user_decks(limit=3)
                print(f"      Found {len(user_decks)} decks:")
                for deck in user_decks:
                    print(f"        - {deck.name} ({deck.format})")
                    if deck.cards:
                        print(f"          Cards: {len(deck.cards)} total")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

            # Example: Search for decks
            print("   c) Searching for decks...")
            try:
                # Search for Commander decks
                decks = archidekt.search(format=Format.COMMANDER, limit=3)
                print(f"      Found {len(decks)} Commander decks:")
                for deck in decks:
                    print(f"        - {deck.name}")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

            # Example: Deck with all details
            print("   d) Getting deck with full details...")
            try:
                # This would get a deck with all cards, sideboard, etc.
                # deck = archidekt.get_deck("your-deck-id", include_cards=True)
                print("      Note: Use include_cards=True to get full deck details")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

            # Rate limit info
            print("   e) Rate limit information...")
            try:
                rate_status = archidekt.get_rate_limit_status()
                print(f"      Rate limit status: {rate_status}")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

        except Exception as e:
            print(f"   Error initializing Archidekt: {e}")
            print()

    # =========================================================================
    # Example 3: Moxfield - API Key authentication (via Parse.bot)
    # =========================================================================
    print("3. Moxfield Provider (API key authentication via Parse.bot)...")
    api_key = get_moxfield_api_key()

    if not api_key:
        print("   Skipping Moxfield examples - no API key provided.")
        print("   Set MOXFIELD_API_KEY environment variable.")
        print()
    else:
        try:
            # Initialize with API key
            print("   Initializing Moxfield provider with Parse.bot API key...")
            moxfield = pymtg.Moxfield(api_key=api_key)

            # Check authentication
            print(f"   Authenticated: {moxfield.is_authenticated()}")
            print()

            # Example: Get a specific deck by ID
            print("   a) Getting a specific deck by ID...")
            try:
                # deck_id = "your-moxfield-deck-id"
                # deck = moxfield.get_deck(deck_id)
                print("      Note: Provide a deck ID to fetch a specific deck")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

            # Example: Get user's decks
            print("   b) Getting user's decks...")
            try:
                user_decks = moxfield.get_user_decks(limit=3)
                print(f"      Found {len(user_decks)} decks:")
                for deck in user_decks:
                    print(f"        - {deck.name} ({deck.format})")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

            # Example: Search for decks
            print("   c) Searching for decks...")
            try:
                decks = moxfield.search(q="commander", limit=3)
                print(f"      Found {len(decks)} decks matching 'commander':")
                for deck in decks:
                    print(f"        - {deck.name}")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

            # Example: Autocomplete for deck names
            print("   d) Autocomplete for deck names...")
            try:
                suggestions = moxfield.autocomplete("dragon", limit=5)
                print("      Suggestions for 'dragon':")
                for suggestion in suggestions:
                    print(f"        - {suggestion}")
                print()
            except Exception as e:
                print(f"      Error: {e}")
                print()

        except Exception as e:
            print(f"   Error initializing Moxfield: {e}")
            print()

    # =========================================================================
    # Example 4: Working with Deck objects
    # =========================================================================
    print("4. Working with Deck objects...")
    print("   Note: This shows how to work with Deck objects from any provider.")
    print()

    # Create a sample deck manually for demonstration
    print("   Creating a sample deck for demonstration...")
    from pymtg.models import Deck, DeckCard, Card, Board

    # Create some sample cards
    card1 = Card(
        id="sample-card-1",
        name="Lightning Bolt",
        mana_cost="{R}",
        type_line="Instant",
        set_code="M10",
    )
    card2 = Card(
        id="sample-card-2",
        name="Mountain",
        mana_cost="",
        type_line="Land",
        set_code="M10",
    )
    card3 = Card(
        id="sample-card-3",
        name="Shock",
        mana_cost="{R}",
        type_line="Instant",
        set_code="M10",
    )

    # Create deck cards
    deck_card1 = DeckCard(card=card1, count=4, board=Board.MAIN.value)
    deck_card2 = DeckCard(card=card2, count=20, board=Board.MAIN.value)
    deck_card3 = DeckCard(card=card3, count=2, board=Board.SIDEBOARD.value)

    # Create a deck
    sample_deck = Deck(
        id="sample-deck-1",
        name="Sample Red Deck",
        format=Format.STANDARD,
        cards=[deck_card1, deck_card2, deck_card3],
        source="sample",
    )

    print(f"   Deck: {sample_deck.name}")
    print(f"   Format: {sample_deck.format}")
    print(f"   Total cards: {sample_deck.get_total_cards()}")
    print()

    # Get main deck cards
    print("   Main deck cards:")
    for card in sample_deck.get_main_deck_cards():
        print(f"     - {card.count}x {card.card.name}")
    print()

    # Get sideboard cards
    print("   Sideboard cards:")
    for card in sample_deck.get_sideboard_cards():
        print(f"     - {card.count}x {card.card.name}")
    print()

    # Get count of a specific card
    print("   Count of Lightning Bolt:", sample_deck.get_card_count("Lightning Bolt"))
    print()

    # Get unique cards
    print("   Unique cards:")
    for card in sample_deck.get_unique_cards():
        print(f"     - {card.card.name}")
    print()

    # =========================================================================
    # Example 5: Universal Search Aggregator with decks
    # =========================================================================
    print("5. Using Universal Search Aggregator...")
    print("   Note: The Aggregator can search across multiple providers.")
    print()

    try:
        aggregator = pymtg.Aggregator()
        print(f"   Aggregator initialized with {len(aggregator.providers)} providers")
        print()

        # Search across all providers
        print("   a) Searching for 'Lightning Bolt' across all providers...")
        results = aggregator.search(name="Lightning Bolt", limit=1)
        print(f"      Found results from {len(results)} providers:")
        for provider_name, cards in results.items():
            print(f"        - {provider_name}: {len(cards)} cards")
        print()

        # Search with specific providers
        print("   b) Searching with specific providers...")
        results = aggregator.search(name="Black Lotus", sources=["scryfall"], limit=1)
        print(f"      Found {len(results.get('scryfall', []))} results from Scryfall")
        print()

    except Exception as e:
        print(f"   Error: {e}")
        print()

    print("=== Example complete ===")


if __name__ == "__main__":
    main()
