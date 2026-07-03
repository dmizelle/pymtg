"""HTTP client utilities for the pymtg library.

This module provides HTTP client utilities and User-Agent header handling
for making requests to MTG API providers.
"""

import logging
from typing import Any, cast

import requests

from pymtg.exceptions import NetworkError

logger = logging.getLogger(__name__)

# Default User-Agent for pymtg
DEFAULT_USER_AGENT = "pymtg/0.1.0 (+https://github.com/pymtg/pymtg)"


class HTTPClient:
    """HTTP client for making requests to MTG API providers.

    This class wraps the requests library to provide consistent HTTP
    functionality across all providers, including User-Agent header
    handling, timeout management, and error handling.

    Attributes:
        session: The requests Session instance used for making requests.
        base_url: The base URL for the API.
        timeout: Request timeout in seconds.
        user_agent: User-Agent string to use for requests.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        user_agent: str | None = None,
    ) -> None:
        """Initialize an HTTPClient.

        Args:
            base_url: The base URL for the API.
            timeout: Request timeout in seconds. Defaults to 30.
            user_agent: User-Agent string to use for requests.
                Defaults to the pymtg default User-Agent.
        """
        self.session = requests.Session()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent or DEFAULT_USER_AGENT

        # Set default headers
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
        )

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a GET request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            params: Query parameters for the request.
            headers: Additional headers for the request.
            **kwargs: Additional keyword arguments passed to session.get().

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)

        try:
            logger.debug(f"GET {url} with params: {params}")
            response = self.session.get(
                url,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **kwargs,
            )
            logger.debug(f"Response status: {response.status_code}")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on GET {url}: {e}")
            raise NetworkError(
                f"Network error on GET {url}",
                original_exception=e,
            ) from e

    def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a POST request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            data: Form data for the request.
            json: JSON data for the request.
            params: Query parameters for the request.
            headers: Additional headers for the request.
            **kwargs: Additional keyword arguments passed to session.post().

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)

        try:
            logger.debug(f"POST {url}")
            response = self.session.post(
                url,
                data=data,
                json=json,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **kwargs,
            )
            logger.debug(f"Response status: {response.status_code}")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on POST {url}: {e}")
            raise NetworkError(
                f"Network error on POST {url}",
                original_exception=e,
            ) from e

    def put(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a PUT request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            data: Form data for the request.
            json: JSON data for the request.
            params: Query parameters for the request.
            headers: Additional headers for the request.
            **kwargs: Additional keyword arguments passed to session.put().

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)

        try:
            logger.debug(f"PUT {url}")
            response = self.session.put(
                url,
                data=data,
                json=json,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **kwargs,
            )
            logger.debug(f"Response status: {response.status_code}")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on PUT {url}: {e}")
            raise NetworkError(
                f"Network error on PUT {url}",
                original_exception=e,
            ) from e

    def delete(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a DELETE request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            params: Query parameters for the request.
            headers: Additional headers for the request.
            **kwargs: Additional keyword arguments passed to session.delete().

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)

        try:
            logger.debug(f"DELETE {url}")
            response = self.session.delete(
                url,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **kwargs,
            )
            logger.debug(f"Response status: {response.status_code}")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on DELETE {url}: {e}")
            raise NetworkError(
                f"Network error on DELETE {url}",
                original_exception=e,
            ) from e

    def _build_url(self, endpoint: str) -> str:
        """Build a full URL from the base URL and endpoint.

        Args:
            endpoint: The API endpoint.

        Returns:
            The full URL.
        """
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _merge_headers(
        self, additional_headers: dict[str, str] | None
    ) -> dict[str, str]:
        """Merge additional headers with default headers.

        Args:
            additional_headers: Additional headers to merge.

        Returns:
            The merged headers dictionary.
        """
        headers = dict(self.session.headers)
        if additional_headers:
            headers.update(additional_headers)
        return cast(dict[str, str], headers)

    def close(self) -> None:
        """Close the HTTP client session."""
        self.session.close()

    def __enter__(self) -> "HTTPClient":
        """Enter a context manager.

        Returns:
            The HTTPClient instance.
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit a context manager.

        Args:
            exc_type: The exception type.
            exc_val: The exception value.
            exc_tb: The exception traceback.
        """
        self.close()
