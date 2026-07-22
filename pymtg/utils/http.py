"""HTTP client utilities for the pymtg library.

This module provides HTTP client utilities and User-Agent header handling
for making requests to MTG API providers.
"""

import logging
import posixpath
from typing import Any, cast
from urllib.parse import unquote

import requests
from requests.structures import CaseInsensitiveDict

from pymtg.exceptions import NetworkError

logger = logging.getLogger(__name__)

# Default User-Agent for pymtg
DEFAULT_USER_AGENT = "pymtg/0.1.0 (+https://github.com/pymtg/pymtg)"


def _build_request_options(
    allow_redirects: bool | None = None,
    verify: bool | str | None = None,
    proxies: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    auth: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """Build a keyword-argument dict for requests.Session methods.

    Only non-None values are included so that requests' own defaults
    are preserved for unspecified options.

    Args:
        allow_redirects: Whether to follow redirects.
        verify: SSL verification (True/False) or path to CA bundle.
        proxies: Proxy URL mapping per scheme.
        cookies: Cookies to send with the request.
        auth: Basic auth (username, password) tuple.

    Returns:
        Dictionary suitable for splatting into a requests.Session method.
    """
    opts: dict[str, Any] = {}
    if allow_redirects is not None:
        opts["allow_redirects"] = allow_redirects
    if verify is not None:
        opts["verify"] = verify
    if proxies is not None:
        opts["proxies"] = proxies
    if cookies is not None:
        opts["cookies"] = cookies
    if auth is not None:
        opts["auth"] = auth
    return opts


class HTTPClient:
    """HTTP client for making requests to MTG API providers.

    This class wraps the requests library to provide consistent HTTP
    functionality across all providers, including User-Agent header
    handling, timeout management, and error handling.

    Note:
        The requests.Session used internally is not thread-safe.
        Do not share HTTPClient instances across threads.

    Attributes:
        session: The requests Session instance used for making requests.
        base_url: The base URL for the API.
        timeout: Request timeout in seconds.
        user_agent: User-Agent string to use for requests.
    """

    # Critical headers that cannot be overridden
    CRITICAL_HEADERS: frozenset[str] = frozenset({"user-agent", "accept"})

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        user_agent: str | None = None,
    ) -> None:
        """Initialize an HTTPClient.

        Args:
            base_url: The base URL for the API. Must start with http:// or https://.
            timeout: Request timeout in seconds. Defaults to 30.0.
            user_agent: User-Agent string to use for requests.
                Defaults to the pymtg default User-Agent.

        Raises:
            ValueError: If base_url is not a valid URL (must start with
                http:// or https://), or if timeout is not a positive number.
        """
        if not isinstance(base_url, str):
            raise ValueError("base_url must be a string")
        base_url = base_url.strip()
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise ValueError(
                "base_url must be a valid URL starting with http:// or https://"
            )
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise ValueError("timeout must be a positive number")
        if timeout <= 0:
            raise ValueError("timeout must be a positive number")
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
        allow_redirects: bool | None = None,
        verify: bool | str | None = None,
        proxies: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> requests.Response:
        """Make a GET request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            params: Query parameters for the request.
            headers: Additional headers for the request.
            allow_redirects: Whether to follow redirects.
            verify: SSL verification (True/False) or path to CA bundle.
            proxies: Proxy URL mapping per scheme.
            cookies: Cookies to send with the request.
            auth: Basic auth (username, password) tuple.

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)
        opts = _build_request_options(
            allow_redirects=allow_redirects,
            verify=verify,
            proxies=proxies,
            cookies=cookies,
            auth=auth,
        )

        try:
            logger.debug("GET %s with params: %s", url, params)
            response = self.session.get(
                url,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **opts,
            )
            logger.debug("Response status: %s", response.status_code)
            return response
        except requests.exceptions.RequestException as e:
            logger.error("Network error on GET %s: %s", url, e)
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
        allow_redirects: bool | None = None,
        verify: bool | str | None = None,
        proxies: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> requests.Response:
        """Make a POST request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            data: Form data for the request.
            json: JSON data for the request.
            params: Query parameters for the request.
            headers: Additional headers for the request.
            allow_redirects: Whether to follow redirects.
            verify: SSL verification (True/False) or path to CA bundle.
            proxies: Proxy URL mapping per scheme.
            cookies: Cookies to send with the request.
            auth: Basic auth (username, password) tuple.

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)
        opts = _build_request_options(
            allow_redirects=allow_redirects,
            verify=verify,
            proxies=proxies,
            cookies=cookies,
            auth=auth,
        )

        try:
            logger.debug("POST %s", url)
            response = self.session.post(
                url,
                data=data,
                json=json,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **opts,
            )
            logger.debug("Response status: %s", response.status_code)
            return response
        except requests.exceptions.RequestException as e:
            logger.error("Network error on POST %s: %s", url, e)
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
        allow_redirects: bool | None = None,
        verify: bool | str | None = None,
        proxies: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> requests.Response:
        """Make a PUT request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            data: Form data for the request.
            json: JSON data for the request.
            params: Query parameters for the request.
            headers: Additional headers for the request.
            allow_redirects: Whether to follow redirects.
            verify: SSL verification (True/False) or path to CA bundle.
            proxies: Proxy URL mapping per scheme.
            cookies: Cookies to send with the request.
            auth: Basic auth (username, password) tuple.

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)
        opts = _build_request_options(
            allow_redirects=allow_redirects,
            verify=verify,
            proxies=proxies,
            cookies=cookies,
            auth=auth,
        )

        try:
            logger.debug("PUT %s", url)
            response = self.session.put(
                url,
                data=data,
                json=json,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **opts,
            )
            logger.debug("Response status: %s", response.status_code)
            return response
        except requests.exceptions.RequestException as e:
            logger.error("Network error on PUT %s: %s", url, e)
            raise NetworkError(
                f"Network error on PUT {url}",
                original_exception=e,
            ) from e

    def delete(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_redirects: bool | None = None,
        verify: bool | str | None = None,
        proxies: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> requests.Response:
        """Make a DELETE request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            params: Query parameters for the request.
            headers: Additional headers for the request.
            allow_redirects: Whether to follow redirects.
            verify: SSL verification (True/False) or path to CA bundle.
            proxies: Proxy URL mapping per scheme.
            cookies: Cookies to send with the request.
            auth: Basic auth (username, password) tuple.

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)
        opts = _build_request_options(
            allow_redirects=allow_redirects,
            verify=verify,
            proxies=proxies,
            cookies=cookies,
            auth=auth,
        )

        try:
            logger.debug("DELETE %s", url)
            response = self.session.delete(
                url,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **opts,
            )
            logger.debug("Response status: %s", response.status_code)
            return response
        except requests.exceptions.RequestException as e:
            logger.error("Network error on DELETE %s: %s", url, e)
            raise NetworkError(
                f"Network error on DELETE {url}",
                original_exception=e,
            ) from e

    def patch(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_redirects: bool | None = None,
        verify: bool | str | None = None,
        proxies: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> requests.Response:
        """Make a PATCH request to the API.

        Args:
            endpoint: The API endpoint (appended to base_url).
            data: Form data for the request.
            json: JSON data for the request.
            params: Query parameters for the request.
            headers: Additional headers for the request.
            allow_redirects: Whether to follow redirects.
            verify: SSL verification (True/False) or path to CA bundle.
            proxies: Proxy URL mapping per scheme.
            cookies: Cookies to send with the request.
            auth: Basic auth (username, password) tuple.

        Returns:
            The requests.Response object.

        Raises:
            NetworkError: If there is a network-related error.
        """
        url = self._build_url(endpoint)
        merged_headers = self._merge_headers(headers)
        opts = _build_request_options(
            allow_redirects=allow_redirects,
            verify=verify,
            proxies=proxies,
            cookies=cookies,
            auth=auth,
        )

        try:
            logger.debug("PATCH %s", url)
            response = self.session.patch(
                url,
                data=data,
                json=json,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
                **opts,
            )
            logger.debug("Response status: %s", response.status_code)
            return response
        except requests.exceptions.RequestException as e:
            logger.error("Network error on PATCH %s: %s", url, e)
            raise NetworkError(
                f"Network error on PATCH {url}",
                original_exception=e,
            ) from e

    def _build_url(self, endpoint: str) -> str:
        """Build a full URL from the base URL and endpoint.

        The endpoint is always joined to ``base_url``; absolute URLs in
        ``endpoint`` are rejected to prevent SSRF (a caller-controlled
        ``endpoint`` must not redirect requests to an arbitrary host).
        Path traversal (``..`` segments that would escape the base path)
        is also rejected.

        Args:
            endpoint: The API endpoint. Must be a non-empty string.

        Returns:
            The full URL.

        Raises:
            ValueError: If endpoint is empty, is an absolute URL (which
                would bypass ``base_url`` and enable SSRF), or contains
                ``..`` segments that escape the base path.
        """
        if not isinstance(endpoint, str):
            raise ValueError("endpoint must be a string")
        endpoint = endpoint.strip()
        if not endpoint:
            raise ValueError("endpoint must be a non-empty string")
        # Reject absolute URLs to prevent SSRF: a caller-supplied endpoint
        # must not override base_url and redirect to an arbitrary host.
        if endpoint.startswith(("http://", "https://")):
            raise ValueError(
                "absolute URLs are not permitted as endpoints; the "
                "endpoint is always joined to base_url to prevent SSRF"
            )
        # Reject protocol-relative URLs (e.g. "//evil.com/path") which
        # could bypass the absolute-URL check and enable SSRF.
        if endpoint.startswith("//"):
            raise ValueError(
                "protocol-relative URLs are not permitted as endpoints; "
                "the endpoint is always joined to base_url to prevent SSRF"
            )
        # base_url already has trailing slashes stripped in __init__;
        # ensure the endpoint has no leading slash to avoid a double slash.
        path = endpoint.lstrip("/")
        # Decode percent-encoded sequences before normalization so that
        # encoded traversal (e.g. %2e%2e or ..%2f) is caught by the
        # normpath check below rather than bypassing it. Decode
        # iteratively to prevent double-encoding bypass (e.g.
        # %252e%252e%252fadmin), stopping once the string stabilizes.
        decoded = path
        for _ in range(5):
            new_decoded = unquote(decoded)
            if new_decoded == decoded:
                break
            decoded = new_decoded
        # Treat backslashes as path separators. posixpath.normpath treats
        # backslashes as regular characters, so a backslash-encoded
        # traversal (e.g. "..%5c..%5cadmin" or "..\\..\\admin") would
        # otherwise bypass the traversal check below.
        decoded = decoded.replace("\\", "/")
        # Normalize the path and reject traversal that escapes the base.
        normalized = posixpath.normpath(decoded)
        if normalized == ".." or normalized.startswith("../"):
            raise ValueError("endpoint must not escape the base path")
        if normalized == ".":
            raise ValueError("endpoint must not collapse to the base path")
        return f"{self.base_url}/{normalized}"

    def _merge_headers(
        self, additional_headers: dict[str, str] | None
    ) -> dict[str, str]:
        """Merge additional headers with default headers.

        The merge is performed using a case-insensitive mapping so that a
        caller-supplied header with different casing than a session default
        (e.g. ``accept-encoding`` vs ``Accept-Encoding``) overwrites the
        existing entry instead of producing a duplicate key.

        Args:
            additional_headers: Additional headers to merge.

        Returns:
            The merged headers dictionary.

        Note:
            Critical headers (User-Agent, Accept) cannot be overridden.
        """
        headers = CaseInsensitiveDict(self.session.headers)
        if additional_headers:
            # Prevent overriding critical headers (case-insensitive check)
            for key, value in additional_headers.items():
                if key.lower() not in self.CRITICAL_HEADERS:
                    headers[key] = value
                else:
                    logger.warning(
                        "Attempted to override critical header %s. "
                        "This header is protected and cannot be overridden.",
                        key,
                    )
        return cast(dict[str, str], dict(headers))

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
