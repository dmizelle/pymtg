#!/usr/bin/env python3
"""Basic Search Example for pymtg.

This example demonstrates basic search functionality using the Scryfall provider.
It shows how to:
- Initialize a provider
- Search for cards using various parameters
- Work with the returned Card objects
- Handle common search scenarios

Usage:
    uv run python docs/examples/basic_search.py
"""

import pymtg
from pymtg.models import Color


def main():
    """Demonstrate basic search functionality."""
    print("=== pymtg Basic Search Example ===\n")

    # Initialize the Scryfall provider
    print("1. Initializing Scryfall provider...")
    scryfall = pymtg.Scryfall()
    print(f"   Provider: {scryfall.name}")
    print(f"   Base URL: {scryfall.base_url}")
    print(f"   Authenticated: {scryfall.is_authenticated()}")
    print()

    # Example 1: Search by name
    print("2. Searching for cards by name...")
    try:
        cards = scryfall.search(name="Lotus", limit=5)
        print(f"   Found {len(cards)} cards matching 'Lotus':")
        for card in cards:
            print(f"     - {card.name} ({card.set_name})")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 2: Search by color
    print("3. Searching for blue cards...")
    try:
        blue_cards = scryfall.search(colors=[Color.BLUE], limit=3)
        print(f"   Found {len(blue_cards)} blue cards:")
        for card in blue_cards:
            print(f"     - {card.name} ({card.mana_cost})")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 3: Search by type
    print("4. Searching for creatures...")
    try:
        creatures = scryfall.search(type_line="Creature", limit=3)
        print(f"   Found {len(creatures)} creatures:")
        for card in creatures:
            print(f"     - {card.name} ({card.type_line})")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 4: Search using query syntax
    print("5. Using Scryfall query syntax...")
    try:
        # Find blue creatures with CMC >= 3
        blue_creatures = scryfall.search_syntax("c:U type:creature cmc>=3", limit=3)
        print(f"   Found {len(blue_creatures)} blue creatures with CMC >= 3:")
        for card in blue_creatures:
            print(f"     - {card.name} ({card.cmc} mana)")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 5: Get autocomplete suggestions
    print("6. Getting autocomplete suggestions...")
    try:
        suggestions = scryfall.autocomplete("Ligh", limit=5)
        print("   Autocomplete suggestions for 'Ligh':")
        for suggestion in suggestions:
            print(f"     - {suggestion}")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 6: Get specific card by ID
    print("7. Getting a specific card by ID...")
    try:
        # Black Lotus Scryfall ID
        black_lotus_id = "38625902-0567-4f24-85b0-a00843553997"
        card = scryfall.get_card(black_lotus_id)
        print(f"   Card: {card.name}")
        print(f"   Mana Cost: {card.mana_cost}")
        print(f"   Type: {card.type_line}")
        print(f"   Oracle Text: {card.oracle_text}")
        print(f"   Set: {card.set_name} ({card.set_code})")
        print(f"   Rarity: {card.rarity}")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 7: Look up cards by name
    print("8. Looking up cards by name...")
    try:
        printings = scryfall.get_cards_by_name("Lightning Bolt", fuzzy=True)
        print(f"   Found {len(printings)} printings of Lightning Bolt:")
        for card in printings[:3]:  # Show first 3 printings
            print(f"     - {card.set_name} ({card.collector_number})")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 8: Working with card properties
    print("9. Working with card properties...")
    try:
        card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")

        # Color information
        if card.color_identity:
            print(f"   Color Identity: {card.get_color_identity_string()}")
        else:
            print("   Color Identity: Colorless")

        # Card characteristics
        print(f"   Is Creature: {card.is_creature()}")
        print(f"   Is Artifact: {card.is_artifact()}")
        print(f"   Is Land: {card.is_land()}")
        print(f"   Is White: {card.is_white()}")
        print(f"   Is Blue: {card.is_blue()}")
        print(f"   Is Black: {card.is_black()}")
        print(f"   Is Red: {card.is_red()}")
        print(f"   Is Green: {card.is_green()}")
        print(f"   Is Multicolor: {card.is_multicolor()}")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 9: Pagination with iter_search
    print("10. Using pagination with iter_search...")
    try:
        count = 0
        print("   First 5 blue creatures:")
        for card in scryfall.iter_search(
            colors=[Color.BLUE], type_line="Creature", limit=5, page_size=5
        ):
            count += 1
            print(f"     {count}. {card.name} ({card.cmc} mana)")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    # Example 10: Rate limit information
    print("11. Rate limit information...")
    try:
        rate_status = scryfall.get_rate_limit_status()
        print(f"   Search limit: {rate_status['search_limit']}")
        print(f"   Other limit: {rate_status['other_limit']}")
        print()
    except Exception as e:
        print(f"   Error: {e}")
        print()

    print("=== Example complete ===")


if __name__ == "__main__":
    main()
