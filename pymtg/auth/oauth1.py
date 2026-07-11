"""OAuth 1.0a authentication handler for providers using OAuth 1.0a.

This module provides the OAuth1Handler for providers like Cardmarket that use
OAuth 1.0a authentication flow.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import threading
import time
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import requests

from pymtg.auth.base import BaseAuthHandler
from pymtg.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class OAuth1Handler(BaseAuthHandler):
    """Authentication handler for providers using OAuth 1.0a.

    This handler manages OAuth 1.0a authentication for providers that require
    consumer key/secret and access token/secret.

    Attributes:
        consumer_key: The OAuth1 consumer key.
        consumer_secret: The OAuth1 consumer secret.
        access_token: The OAuth1 access token.
        access_token_secret: The OAuth1 access token secret.
        signature_method: The signature method (default: HMAC-SHA1).
        timestamp: Current timestamp for OAuth1 requests.
        nonce: Random nonce for OAuth1 requests.
        authenticated: Whether authentication is valid.
    """

    def __init__(
        self,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
        signature_method: str = "HMAC-SHA1",
    ) -> None:
        """Initialize the OAuth1Handler.

        Args:
            consumer_key: The OAuth1 consumer key.
            consumer_secret: The OAuth1 consumer secret.
            access_token: The OAuth1 access token (if already obtained).
            access_token_secret: The OAuth1 access token secret
                (if already obtained).
            signature_method: The OAuth1 signature method (default: HMAC-SHA1).
        """
        self._lock = threading.RLock()

        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_token = access_token
        self._access_token_secret = access_token_secret
        self.signature_method = signature_method
        # Validate all 4 credentials for consistency with is_authenticated()
        self._authenticated = bool(
            consumer_key and consumer_secret and access_token and access_token_secret
        )

    def authenticate(
        self,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Authenticate with OAuth1 credentials.

        For OAuth 1.0a, this typically means storing the pre-obtained access
        token and secret, as the full OAuth1 flow (request token, authorize,
        access token exchange) is usually done out-of-band.

        Args:
            consumer_key: The OAuth1 consumer key
                (overrides initialization value).
            consumer_secret: The OAuth1 consumer secret
                (overrides initialization value).
            access_token: The OAuth1 access token
                (overrides initialization value).
            access_token_secret: The OAuth1 access token secret
                (overrides initialization value).
            **kwargs: Additional authentication parameters.

        Raises:
            AuthenticationError: If authentication fails
                (missing required credentials), or if partial credential
                pairs are provided (e.g. consumer_key without
                consumer_secret).
        """
        with self._lock:
            # Validate credential pairs before any updates to prevent
            # inconsistent state where one credential in a pair is updated
            # while the other retains its previous value.
            if (consumer_key is not None) != (consumer_secret is not None):
                raise AuthenticationError(
                    "consumer_key and consumer_secret must be provided "
                    "together; partial updates are not allowed",
                    auth_type="oauth1",
                )
            if (access_token is not None) != (access_token_secret is not None):
                raise AuthenticationError(
                    "access_token and access_token_secret must be provided "
                    "together; partial updates are not allowed",
                    auth_type="oauth1",
                )

            # Update stored credentials
            self._consumer_key = consumer_key or self._consumer_key
            self._consumer_secret = consumer_secret or self._consumer_secret
            self._access_token = access_token or self._access_token
            self._access_token_secret = access_token_secret or self._access_token_secret

            # Validate required credentials
            if not self._consumer_key or not self._consumer_secret:
                raise AuthenticationError(
                    "Consumer key and consumer secret are required for "
                    "OAuth1 authentication",
                    auth_type="oauth1",
                )

            # For OAuth1, we typically need the access token/secret pre-obtained
            # If they're provided, we're authenticated
            if self._access_token and self._access_token_secret:
                self._authenticated = True
                logger.info("OAuth1 authentication configured successfully")
            else:
                # In some cases, we might implement the full OAuth1 flow
                # But for Cardmarket, the user provides the pre-obtained tokens
                self._authenticated = False
                logger.warning(
                    "OAuth1 access token/secret not provided. "
                    "Some endpoints may require authenticated requests."
                )

    def is_authenticated(self) -> bool:
        """Check if authentication is valid.

        Returns:
            True if access token and secret are present, False otherwise.
        """
        with self._lock:
            return self._authenticated and bool(
                self._consumer_key
                and self._consumer_secret
                and self._access_token
                and self._access_token_secret
            )

    def refresh(self) -> None:
        """Refresh OAuth1 authentication.

        For OAuth1, this typically requires re-acquiring the access token
        through the full OAuth1 flow, which is not supported in this basic
        implementation. Users need to provide new access token/secret.

        Raises:
            AuthenticationError: If refresh is not supported or
                credentials missing.
        """
        # OAuth1 doesn't have a simple refresh mechanism like OAuth2
        # The full flow needs to be repeated out-of-band
        raise AuthenticationError(
            "OAuth1 does not support automatic token refresh. "
            "Please obtain new access token and secret and re-authenticate.",
            auth_type="oauth1",
        )

    def apply_auth(self, session: requests.Session) -> None:
        """Apply OAuth1 authentication to a requests session.

        This adds the Authorization header with the OAuth1 signature to
            all requests.

        Args:
            session: The requests.Session to apply authentication to.
        """
        # Store the session for signing requests
        # We'll use a hook to sign each request
        # Ensure the pre_request hooks list exists
        if "pre_request" not in session.hooks:
            session.hooks["pre_request"] = []
        session.hooks["pre_request"].append(self._sign_request)  # type: ignore[arg-type]

    def _sign_request(
        self,
        request: requests.PreparedRequest,
        **kwargs: Any,
    ) -> requests.PreparedRequest:
        """Sign a request using OAuth1.

        Args:
            request: The prepared request to sign.

        Returns:
            The signed prepared request.
        """
        with self._lock:
            if not self.is_authenticated():
                return request

            # Generate OAuth1 parameters
            oauth_params = {
                "oauth_consumer_key": self._consumer_key,
                "oauth_token": self._access_token,
                "oauth_signature_method": self.signature_method,
                "oauth_timestamp": str(int(time.time())),
                "oauth_nonce": self._generate_nonce(),
                "oauth_version": "1.0",
            }

            # Get the base URL and parameters
            url = request.url
            method = request.method

            # Parse existing query parameters

            parsed_url = urlparse(url)
            query_string = parsed_url.query or ""
            existing_params = parse_qs(query_string)  # type: ignore[arg-type]

            # Flatten existing params
            # OAuth1 allows comma-separated values for parameters with multiple values
            flat_params: dict[str, str] = {}
            for key, values in existing_params.items():
                str_key = str(key)
                if len(values) == 1:
                    flat_params[str_key] = str(values[0])
                else:
                    flat_params[str_key] = ",".join(str(v) for v in values)  # type: ignore[arg-type]

            # Merge OAuth params with existing params
            all_params = {**flat_params, **oauth_params}

            # Build the signature base string
            # Sort parameters by key
            sorted_params = sorted(all_params.items())

            # URL encode parameters
            encoded_params = []
            for key, value in sorted_params:
                encoded_key = quote(str(key), safe="-._~")
                encoded_value = quote(str(value), safe="-._~")
                encoded_params.append(f"{encoded_key}={encoded_value}")

            param_string = "&".join(encoded_params)

            # Build base string
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            method_upper = method.upper() if method else ""
            base_string = (
                f"{method_upper}&{quote(str(base_url), safe='')}&"
                f"{quote(str(param_string), safe='')}"
            )

            # Generate signature
            signing_key = (
                f"{quote(str(self._consumer_secret), safe='')}&"
                f"{quote(str(self._access_token_secret), safe='')}"
            )
            signature = self._generate_signature(base_string, signing_key)

            # Add signature to OAuth params
            oauth_params["oauth_signature"] = signature

            # Build Authorization header
            auth_header_parts = []
            for key in sorted(oauth_params.keys()):
                value = oauth_params[key]
                auth_header_parts.append(
                    f'{quote(key, safe="")}="{quote(str(value), safe="")}"'
                )

            auth_header = f"OAuth {', '.join(auth_header_parts)}"

            # Add Authorization header to request
            request.headers["Authorization"] = auth_header

            return request

    def _generate_nonce(self) -> str:
        """Generate a random nonce for OAuth1 requests.

        Returns:
            A random nonce string.
        """
        return str(secrets.randbelow(2**64))

    def _generate_signature(self, base_string: str, signing_key: str) -> str:
        """Generate an OAuth1 signature.

        Args:
            base_string: The OAuth1 base string to sign.
            signing_key: The signing key (consumer_secret&token_secret).

        Returns:
            The base64-encoded signature.
        """
        if self.signature_method == "HMAC-SHA1":
            signature = hmac.new(
                signing_key.encode(),
                base_string.encode(),
                hashlib.sha1,
            ).digest()
        elif self.signature_method == "HMAC-SHA256":
            signature = hmac.new(
                signing_key.encode(),
                base_string.encode(),
                hashlib.sha256,
            ).digest()
        elif self.signature_method == "PLAINTEXT":
            signature = signing_key.encode()
        else:
            raise ValueError(f"Unsupported signature method: {self.signature_method}")

        return base64.b64encode(signature).decode()

    def clear_auth(self) -> None:
        """Clear OAuth1 authentication credentials."""
        with self._lock:
            self._consumer_key = None
            self._consumer_secret = None
            self._access_token = None
            self._access_token_secret = None
            self._authenticated = False

    @property
    def consumer_key(self) -> str | None:
        """Get the consumer key."""
        return self._consumer_key

    @property
    def consumer_secret(self) -> str | None:
        """Get the consumer secret."""
        return self._consumer_secret

    @property
    def access_token(self) -> str | None:
        """Get the access token."""
        return self._access_token

    @property
    def access_token_secret(self) -> str | None:
        """Get the access token secret."""
        return self._access_token_secret
