"""Tests for the pymtg._version module.

This module tests that the version string follows PEP 440
and that the runtime validation logic in pymtg._version._validate_version
works correctly. Invalid versions are expected to raise
packaging.version.InvalidVersion.
"""

import pytest
from packaging.version import InvalidVersion

from pymtg import __version__
from pymtg._version import _validate_version


class TestVersion:
    """Tests for version validation."""

    def test_version_is_string(self) -> None:
        """Test that __version__ is a string."""
        assert isinstance(__version__, str)

    def test_version_is_valid_pep440(self) -> None:
        """Test that __version__ follows PEP 440."""
        # Should not raise an exception
        _validate_version(__version__)

    @pytest.mark.parametrize(
        "version",
        [
            "1.0.0",
            "0.1.0",
            "10.20.30",
            "1.0.0-alpha",
            "1.0.0+build123",
            "1.0.0-alpha+build123",
            "1!1.0.0",  # Epoch version (valid per PEP 440)
            "1.0.0+local",  # Local version identifier (valid per PEP 440)
            "1!1.0.0a1",  # Epoch with pre-release (valid per PEP 440)
            "1",  # Major only (valid per PEP 440)
            "1.0",  # Major.minor (valid per PEP 440)
            "v1.0.0",  # 'v' prefix (valid per PEP 440)
            "1.0.0.0",  # Four parts (valid per PEP 440)
        ],
    )
    def test_validate_version_accepts_valid_versions(self, version: str) -> None:
        """Test that valid version strings pass validation.

        Args:
            version: A valid version string to test.
        """
        _validate_version(version)

    @pytest.mark.parametrize(
        "version",
        [
            "",
            "not-a-version",
            "1. 0.0",  # Internal whitespace is not allowed per PEP 440
            "   ",  # Whitespace-only string
            "!!!",  # Only special characters
            "1..0.0",  # Double dot
            "1.0.0-",  # Dangling hyphen with no pre-release identifier
            ".1.0",  # Leading dot
        ],
    )
    def test_validate_version_rejects_invalid_versions(self, version: str) -> None:
        """Test that invalid version strings raise packaging.version.InvalidVersion.

        Args:
            version: An invalid version string to test.
        """
        with pytest.raises(InvalidVersion):
            _validate_version(version)

    @pytest.mark.parametrize(
        "version",
        [None, ["1.0.0"]],
    )
    def test_validate_version_rejects_non_strings(self, version: object) -> None:
        """Test that non-string inputs raise TypeError, not InvalidVersion.

        ``_validate_version`` has no runtime type guard; it forwards its
        argument to ``packaging.version.Version``, which raises
        ``TypeError`` for non-string inputs. This pins that behavior so
        future readers do not assume ``InvalidVersion`` is the only
        failure mode.

        Only types that are guaranteed to raise ``TypeError`` across all
        ``packaging`` versions are included here. Numeric values like
        ``1`` and ``1.0`` are intentionally omitted because some versions
        of ``packaging`` coerce them to strings, which would make this
        test brittle.

        Args:
            version: A non-string value to test.
        """
        with pytest.raises(TypeError):
            _validate_version(version)  # type: ignore[arg-type]
