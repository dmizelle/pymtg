"""Tests for the Universal Search Aggregator.

This module contains unit tests for the Aggregator class, covering
all major functionality including multi-provider search, error handling,
and timing tracking.
"""

import unittest

from pymtg.models.card import Card
from pymtg.models.enums import Color
from pymtg.providers.base import BaseProvider
from pymtg.search.aggregator import Aggregator


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    def __init__(self, name: str = "mock", should_fail: bool = False) -> None:
        """Initialize mock provider.

        Args:
            name: Provider name.
            should_fail: If True, search methods will raise exceptions.
        """
        self.name = name
        self.base_url = f"https://api.{name}.com"
        self.should_fail = should_fail
        self.search_calls = []
        self.search_syntax_calls = []

    def search(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
        **kwargs,
    ) -> list[Card]:
        """Mock search implementation."""
        self.search_calls.append(
            {
                "name": name,
                "colors": colors,
                "identity": identity,
                "type_line": type_line,
                "limit": limit,
                "page": page,
                "order": order,
                "kwargs": kwargs,
            }
        )

        if self.should_fail:
            raise Exception(f"{self.name} intentionally failed")

        # Return mock cards
        return [
            Card(
                id=f"{self.name}_1",
                scryfall_id=None,
                name=f"{self.name}_card_1",
                source=self.name,
            ),
            Card(
                id=f"{self.name}_2",
                scryfall_id=None,
                name=f"{self.name}_card_2",
                source=self.name,
            ),
        ]

    def search_syntax(self, query: str, limit: int = 20, **kwargs) -> list[Card]:
        """Mock search_syntax implementation."""
        self.search_syntax_calls.append(
            {
                "query": query,
                "limit": limit,
                "kwargs": kwargs,
            }
        )

        if self.should_fail:
            raise Exception(f"{self.name} intentionally failed")

        return [
            Card(
                id=f"{self.name}_syntax_1",
                scryfall_id=None,
                name=f"{self.name}_syntax_card",
                source=self.name,
            ),
        ]

    def get_card(self, card_id: str, **kwargs) -> Card:
        """Mock get_card implementation."""
        return Card(
            id=card_id,
            scryfall_id=None,
            name=f"{self.name}_single_card",
            source=self.name,
        )


class TestAggregatorInitialization(unittest.TestCase):
    """Test Aggregator initialization."""

    def test_default_initialization(self):
        """Test that Aggregator initializes with empty provider list."""
        aggregator = Aggregator()
        self.assertEqual(aggregator.providers, [])
        self.assertEqual(aggregator.provider_map, {})

    def test_initialization_with_providers(self):
        """Test that Aggregator initializes with provided providers."""
        provider1 = MockProvider("test1")
        provider2 = MockProvider("test2")
        aggregator = Aggregator(providers=[provider1, provider2])

        self.assertEqual(len(aggregator.providers), 2)
        self.assertEqual(len(aggregator.provider_map), 2)
        self.assertIn("test1", aggregator.provider_map)
        self.assertIn("test2", aggregator.provider_map)


class TestAggregatorProviderManagement(unittest.TestCase):
    """Test Aggregator provider management methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.aggregator = Aggregator()
        self.provider1 = MockProvider("provider1")
        self.provider2 = MockProvider("provider2")

    def test_add_provider(self):
        """Test adding a provider."""
        self.aggregator.add_provider(self.provider1)
        self.assertIn("provider1", self.aggregator.provider_map)
        self.assertEqual(len(self.aggregator.providers), 1)

    def test_add_duplicate_provider_raises(self):
        """Test that adding duplicate provider raises ValueError."""
        self.aggregator.add_provider(self.provider1)
        with self.assertRaises(ValueError) as context:
            self.aggregator.add_provider(MockProvider("provider1"))
        self.assertIn("already exists", str(context.exception))

    def test_remove_provider(self):
        """Test removing a provider."""
        self.aggregator.add_provider(self.provider1)
        self.aggregator.add_provider(self.provider2)

        result = self.aggregator.remove_provider("provider1")
        self.assertTrue(result)
        self.assertNotIn("provider1", self.aggregator.provider_map)
        self.assertEqual(len(self.aggregator.providers), 1)

    def test_remove_nonexistent_provider(self):
        """Test removing a non-existent provider returns False."""
        result = self.aggregator.remove_provider("nonexistent")
        self.assertFalse(result)

    def test_get_provider(self):
        """Test getting a provider by name."""
        self.aggregator.add_provider(self.provider1)
        provider = self.aggregator.get_provider("provider1")
        self.assertEqual(provider, self.provider1)

    def test_get_nonexistent_provider_raises(self):
        """Test that getting non-existent provider raises KeyError."""
        with self.assertRaises(KeyError):
            self.aggregator.get_provider("nonexistent")

    def test_get_available_providers(self):
        """Test getting list of available provider names."""
        self.aggregator.add_provider(self.provider1)
        self.aggregator.add_provider(self.provider2)
        providers = self.aggregator.get_available_providers()
        self.assertEqual(set(providers), {"provider1", "provider2"})

    def test_clear(self):
        """Test clearing all providers."""
        self.aggregator.add_provider(self.provider1)
        self.aggregator.add_provider(self.provider2)
        self.aggregator.clear()
        self.assertEqual(len(self.aggregator.providers), 0)
        self.assertEqual(len(self.aggregator.provider_map), 0)


class TestAggregatorSearch(unittest.TestCase):
    """Test Aggregator search functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.aggregator = Aggregator()
        self.provider1 = MockProvider("provider1")
        self.provider2 = MockProvider("provider2")
        self.aggregator.add_provider(self.provider1)
        self.aggregator.add_provider(self.provider2)

    def test_search_all_providers(self):
        """Test searching across all providers."""
        results = self.aggregator.search(name="test", limit=5)

        self.assertIn("provider1", results)
        self.assertIn("provider2", results)

        # Check results structure
        for provider_name, result in results.items():
            self.assertIn("cards", result)
            self.assertIn("error", result)
            self.assertIn("timing", result)
            self.assertIsNone(result["error"])
            self.assertEqual(len(result["cards"]), 2)
            self.assertIn("duration", result["timing"])

    def test_search_specific_sources(self):
        """Test searching only specific providers."""
        results = self.aggregator.search(name="test", limit=5, sources=["provider1"])

        self.assertIn("provider1", results)
        self.assertNotIn("provider2", results)

    def test_search_empty_results(self):
        """Test searching returns empty dict when no providers configured."""
        empty_aggregator = Aggregator()
        results = empty_aggregator.search(name="test")
        self.assertEqual(results, {})

    def test_search_with_color_parameter(self):
        """Test searching with color parameter."""
        self.aggregator.search(name="test", colors=[Color.BLUE], limit=5)

        # Verify the color parameter was passed through
        for provider in [self.provider1, self.provider2]:
            self.assertEqual(len(provider.search_calls), 1)
            self.assertEqual(provider.search_calls[0]["colors"], [Color.BLUE])

    def test_search_syntax_all_providers(self):
        """Test search_syntax across all providers."""
        results = self.aggregator.search_syntax(query="c:U type:creature", limit=5)

        self.assertIn("provider1", results)
        self.assertIn("provider2", results)

        for provider_name, result in results.items():
            self.assertIn("cards", result)
            self.assertIn("error", result)
            self.assertIn("timing", result)
            self.assertIsNone(result["error"])

    def test_search_syntax_specific_sources(self):
        """Test search_syntax with specific sources."""
        results = self.aggregator.search_syntax(
            query="c:U", limit=5, sources=["provider1"]
        )

        self.assertIn("provider1", results)
        self.assertNotIn("provider2", results)

    def test_search_with_failing_provider(self):
        """Test searching with a provider that raises an exception."""
        failing_provider = MockProvider("failing", should_fail=True)
        self.aggregator.add_provider(failing_provider)

        results = self.aggregator.search(name="test", limit=5)

        # The failing provider should be in results with an error
        self.assertIn("failing", results)
        self.assertIsNotNone(results["failing"]["error"])
        self.assertEqual(results["failing"]["error"]["type"], "Exception")

        # Other providers should still succeed
        self.assertIn("provider1", results)
        self.assertIsNone(results["provider1"]["error"])

    def test_search_syntax_with_failing_provider(self):
        """Test search_syntax with a failing provider."""
        failing_provider = MockProvider("failing", should_fail=True)
        self.aggregator.add_provider(failing_provider)

        results = self.aggregator.search_syntax(query="test", limit=5)

        self.assertIn("failing", results)
        self.assertIsNotNone(results["failing"]["error"])

    def test_timing_tracked(self):
        """Test that timing is tracked for each provider."""
        results = self.aggregator.search(name="test", limit=5)

        for provider_name, result in results.items():
            timing = result["timing"]
            self.assertIn("start_time", timing)
            self.assertIn("end_time", timing)
            self.assertIn("duration", timing)
            self.assertGreaterEqual(timing["duration"], 0)
            self.assertGreater(timing["end_time"], timing["start_time"])


class TestAggregatorRepr(unittest.TestCase):
    """Test Aggregator string representation."""

    def test_repr_empty(self):
        """Test repr with no providers."""
        aggregator = Aggregator()
        repr_str = repr(aggregator)
        self.assertIn("Aggregator", repr_str)
        self.assertIn("providers=0", repr_str)

    def test_repr_with_providers(self):
        """Test repr with providers."""
        provider = MockProvider("test")
        aggregator = Aggregator(providers=[provider])
        repr_str = repr(aggregator)
        self.assertIn("providers=1", repr_str)
        self.assertIn("test", repr_str)


if __name__ == "__main__":
    unittest.main()
