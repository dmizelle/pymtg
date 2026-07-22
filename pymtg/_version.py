"""Version information for pymtg.

This module contains the version information for the pymtg library.
The version follows PEP 440 versioning and is validated at import time
to ensure compliance.
"""

from packaging.version import Version

__version__ = "0.1.0"


def _validate_version(version: str) -> None:
    """Validate that a version string follows PEP 440.

    Args:
        version: The version string to validate.

    Raises:
        packaging.version.InvalidVersion: If the version string is not a valid
            PEP 440 version.
    """
    Version(version)


# Validate the version at import time
_validate_version(__version__)
