"""Tests for the Universal Search Aggregator.

This module contains unit tests for the Aggregator class, covering
all major functionality including multi-provider search, error handling,
and timing tracking.
"""

import threading
import unittest
from unittest.mock import patch

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
        # Initialize BaseProvider so base-class attributes (config,
        # http_client, rate_limit, _lock) are set up. The custom name and
        # base_url are applied afterward.
        super().__init__()
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

    def search_syntax(
        self,
        query: str,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
    ) -> list[Card]:
        """Mock search_syntax implementation."""
        self.search_syntax_calls.append(
            {
                "query": query,
                "limit": limit,
                "page": page,
                "order": order,
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

    def get_card(self, card_id: str) -> Card:
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

    def test_initialization_creates_lock(self):
        """Test that Aggregator initializes with a reentrant lock."""
        aggregator = Aggregator()
        self.assertTrue(hasattr(aggregator._lock, "acquire"))
        self.assertTrue(hasattr(aggregator._lock, "release"))
        self.assertTrue(callable(aggregator._lock.acquire))
        self.assertTrue(callable(aggregator._lock.release))
        # Verify the lock is reentrant (RLock, not Lock).
        aggregator._lock.acquire()
        try:
            aggregator._lock.acquire()  # Should not block.
            aggregator._lock.release()
        finally:
            aggregator._lock.release()


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
        """Test searching with color parameter and parameter passthrough.

        Verifies that colors, identity, type_line, page, and order are
        forwarded to each provider by search().
        """
        self.aggregator.search(
            name="test",
            colors=[Color.BLUE],
            identity=[Color.BLUE],
            type_line="Creature",
            limit=5,
            page=2,
            order="name",
        )

        # Verify the parameters were passed through
        for provider in [self.provider1, self.provider2]:
            self.assertEqual(len(provider.search_calls), 1)
            call = provider.search_calls[0]
            self.assertEqual(call["colors"], [Color.BLUE])
            self.assertEqual(call["identity"], [Color.BLUE])
            self.assertEqual(call["type_line"], "Creature")
            self.assertEqual(call["page"], 2)
            self.assertEqual(call["order"], "name")

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
        err = results["failing"]["error"]
        self.assertIsNotNone(err)
        self.assertEqual(err["type"], "Exception")
        self.assertIn("intentionally failed", err["message"])
        self.assertIsInstance(err["exception"], Exception)

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


class TestAggregatorThreadSafety(unittest.TestCase):
    """Test Aggregator thread safety for provider_map access."""

    def test_get_provider_acquires_lock(self):
        """Test that get_provider acquires the lock before reading."""
        aggregator = Aggregator()
        aggregator.add_provider(MockProvider("test"))

        with patch.object(aggregator, "_lock") as mock_lock:
            aggregator.get_provider("test")
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_add_provider_acquires_lock(self):
        """Test that add_provider acquires the lock before modifying."""
        aggregator = Aggregator()

        with patch.object(aggregator, "_lock") as mock_lock:
            aggregator.add_provider(MockProvider("test"))
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_remove_provider_acquires_lock(self):
        """Test that remove_provider acquires the lock before modifying."""
        aggregator = Aggregator()
        aggregator.add_provider(MockProvider("test"))

        with patch.object(aggregator, "_lock") as mock_lock:
            aggregator.remove_provider("test")
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_clear_acquires_lock(self):
        """Test that clear acquires the lock before modifying."""
        aggregator = Aggregator()
        aggregator.add_provider(MockProvider("test"))

        with patch.object(aggregator, "_lock") as mock_lock:
            aggregator.clear()
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_get_available_providers_acquires_lock(self):
        """Test that get_available_providers acquires the lock."""
        aggregator = Aggregator()
        aggregator.add_provider(MockProvider("test"))

        with patch.object(aggregator, "_lock") as mock_lock:
            aggregator.get_available_providers()
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_repr_acquires_lock(self):
        """Test that __repr__ acquires the lock before reading."""
        aggregator = Aggregator()
        aggregator.add_provider(MockProvider("test"))

        with patch.object(aggregator, "_lock") as mock_lock:
            repr(aggregator)
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_concurrent_add_and_get_no_errors(self):
        """Test that concurrent add and get operations don't raise errors."""
        aggregator = Aggregator()
        errors: list[Exception] = []

        def add_providers() -> None:
            for i in range(50):
                try:
                    aggregator.add_provider(MockProvider(f"provider-{i}"))
                except Exception as e:
                    # Record every exception (including ValueError) so a
                    # re-raised exception does not silently kill the
                    # thread and bypass the errors check below.
                    errors.append(e)

        def get_providers() -> None:
            for i in range(50):
                try:
                    aggregator.get_available_providers()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=add_providers),
            threading.Thread(target=get_providers),
            threading.Thread(target=get_providers),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent errors: {errors}")
        self.assertEqual(len(aggregator.provider_map), 50)
        # Verify providers list and map are consistent (no lost updates).
        self.assertEqual(len(aggregator.providers), 50)
        # Verify no duplicate names in the providers list.
        names = [p.name for p in aggregator.providers]
        self.assertEqual(len(names), len(set(names)))

    def test_concurrent_add_and_remove_consistent(self):
        """Test that concurrent add/remove leaves consistent state."""
        aggregator = Aggregator()
        errors: list[Exception] = []

        def add_and_remove(thread_id: int) -> None:
            for i in range(20):
                name = f"p-{thread_id}-{i}"
                try:
                    aggregator.add_provider(MockProvider(name))
                    aggregator.remove_provider(name)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=add_and_remove, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent errors: {errors}")
        # Verify both providers list and map are empty and consistent.
        self.assertEqual(len(aggregator.provider_map), 0)
        self.assertEqual(len(aggregator.providers), 0)


if __name__ == "__main__":
    unittest.main()
