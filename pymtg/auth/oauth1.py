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
from requests.auth import AuthBase

from pymtg.auth.base import BaseAuthHandler
from pymtg.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class _OAuth1Signer(AuthBase):
    """Requests auth handler that signs every request with OAuth 1.0a.

    Wraps an :class:`OAuth1Handler` so that ``requests`` invokes the
    signing logic for each :class:`~requests.PreparedRequest` via the
    ``session.auth`` machinery (the only hook ``requests`` dispatches
    natively besides ``response``).

    Attributes:
        _handler: The OAuth1Handler used to sign requests.
    """

    def __init__(self, handler: "OAuth1Handler") -> None:
        """Initialize the signer.

        Args:
            handler: The OAuth1Handler whose signing logic to delegate to.
        """
        self._handler = handler

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        """Sign and return the given prepared request.

        Args:
            request: The prepared request to sign.

        Returns:
            The signed prepared request.
        """
        return self._handler._sign_request(request)


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

            # Update stored credentials. Use explicit None checks (rather
            # than truthiness) so a caller can pass an empty string to
            # intentionally clear a credential without it silently falling
            # through to the previously stored value.
            self._consumer_key = (
                consumer_key if consumer_key is not None else self._consumer_key
            )
            self._consumer_secret = (
                consumer_secret
                if consumer_secret is not None
                else self._consumer_secret
            )
            self._access_token = (
                access_token if access_token is not None else self._access_token
            )
            self._access_token_secret = (
                access_token_secret
                if access_token_secret is not None
                else self._access_token_secret
            )

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

        Registers an ``requests.auth.AuthBase`` signer on the session so that
        every outgoing :class:`~requests.PreparedRequest` is signed with a
        valid OAuth 1.0a ``Authorization`` header. ``requests`` only
        dispatches the ``response`` hook natively; there is no built-in
        ``pre_request`` hook, so signing must be performed via the
        ``session.auth`` machinery (or by overriding the session's
        ``request`` method).

        Args:
            session: The requests.Session to apply authentication to.
        """
        session.auth = _OAuth1Signer(self)

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
            oauth_params = self._generate_oauth_params()

            # Parse and merge with existing query parameters
            all_params = self._merge_with_existing_params(
                str(request.url), oauth_params
            )

            # Build signature base string
            base_string = self._build_signature_base_string(
                request.method or "GET", str(request.url), all_params
            )

            # Generate signature
            signature = self._generate_request_signature(base_string)
            oauth_params["oauth_signature"] = signature

            # Build and apply Authorization header
            auth_header = self._build_oauth_header(oauth_params)
            request.headers["Authorization"] = auth_header

            return request

    def _generate_oauth_params(self) -> dict[str, str | None]:
        """Generate OAuth1 parameters for request signing.

        Returns:
            Dictionary of OAuth1 parameters.

        Raises:
            AuthenticationError: If any required credential is missing.
        """
        # Guard against None credentials before they can flow into the
        # signature base string or Authorization header (where str(None)
        # would produce an invalid, hard-to-diagnose signature).
        if self._consumer_key is None or self._access_token is None:
            raise AuthenticationError(
                "Cannot generate OAuth1 params: missing credentials",
                auth_type="oauth1",
            )
        return {
            "oauth_consumer_key": self._consumer_key,
            "oauth_token": self._access_token,
            "oauth_signature_method": self.signature_method,
            "oauth_timestamp": str(int(time.time())),
            "oauth_nonce": self._generate_nonce(),
            "oauth_version": "1.0",
        }

    def _merge_with_existing_params(
        self, url: str, oauth_params: dict[str, str | None]
    ) -> dict[str, list[str]]:
        """Merge OAuth1 params with existing query parameters from URL.

        Per RFC 5849 §3.4.1.3.2, each key-value pair is a separate parameter
        in the signature base string. Multi-valued query parameters (e.g.
        ``?a=1&a=2``) are therefore preserved as separate entries rather
        than comma-joined into a single string.

        Args:
            url: The request URL.
            oauth_params: OAuth1 parameters to merge.

        Returns:
            Mapping of parameter name to a list of its string values.
        """
        parsed_url = urlparse(url)
        query_string = parsed_url.query or ""
        # keep_blank_values=True preserves empty-valued query parameters
        # (e.g. ?key=) so they are included in the signature base string,
        # as required by the OAuth 1.0a spec for strict providers.
        existing_params = parse_qs(query_string, keep_blank_values=True)

        # Per RFC 5849 §3.4.1.3.2, each key-value pair is a separate
        # parameter in the signature base string — multi-valued params
        # must NOT be comma-joined.
        flat_params: dict[str, list[str]] = {}
        for key, values in existing_params.items():
            flat_params[str(key)] = [str(v) for v in values]

        # Merge oauth params (each is single-valued).
        merged: dict[str, list[str]] = {}
        for k, vs in flat_params.items():
            merged.setdefault(k, []).extend(vs)
        for k, v in oauth_params.items():
            if v is not None:
                merged.setdefault(k, []).append(str(v))
        return merged

    def _build_signature_base_string(
        self, method: str, url: str, params: dict[str, list[str]]
    ) -> str:
        """Build the OAuth1 signature base string.

        Per RFC 5849 §3.4.1.3.2, parameters are sorted by their
        percent-encoded key, then by their percent-encoded value. Because
        ``quote()`` is not a monotonic transform of the raw string (for
        example ``a_b`` sorts after ``a-`` raw but ``a%5Fb`` sorts before
        ``a-`` once encoded, since ``-`` is in the safe set), the sort must
        be performed on the encoded values rather than the raw ones.

        Args:
            method: HTTP method.
            url: Request URL.
            params: Parameters to include in signature, mapped from name to
                a list of string values (multi-valued params are expanded
                into one entry per value).

        Returns:
            The signature base string.
        """
        # Per RFC 5849 §3.4.1.3.2, sort by percent-encoded key then value.
        encoded_pairs: list[tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, list):
                for v in value:
                    encoded_key = quote(str(key), safe="-._~")
                    encoded_value = quote(str(v), safe="-._~")
                    encoded_pairs.append((encoded_key, encoded_value))
            else:
                encoded_key = quote(str(key), safe="-._~")
                encoded_value = quote(str(value), safe="-._~")
                encoded_pairs.append((encoded_key, encoded_value))
        encoded_pairs.sort()
        encoded_params = [f"{k}={v}" for k, v in encoded_pairs]

        param_string = "&".join(encoded_params)

        # Build base string
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        method_upper = method.upper() if method else ""
        return (
            f"{method_upper}&{quote(str(base_url), safe='')}&"
            f"{quote(str(param_string), safe='')}"
        )

    def _generate_request_signature(self, base_string: str) -> str:
        """Generate the OAuth1 signature for a request.

        Args:
            base_string: The signature base string.

        Returns:
            The generated signature.
        """
        # Validate that secrets are present and non-empty
        if not self._consumer_secret:
            raise AuthenticationError(
                "consumer_secret must not be None or empty", auth_type="oauth1"
            )
        if not self._access_token_secret:
            raise AuthenticationError(
                "access_token_secret must not be None or empty", auth_type="oauth1"
            )
        signing_key = (
            f"{quote(str(self._consumer_secret), safe='')}&"
            f"{quote(str(self._access_token_secret), safe='')}"
        )
        return self._generate_signature(base_string, signing_key)

    def _build_oauth_header(self, oauth_params: dict[str, Any]) -> str:
        """Build the OAuth1 Authorization header.

        Args:
            oauth_params: OAuth1 parameters including signature.

        Returns:
            The Authorization header value.
        """
        auth_header_parts = []
        for key in sorted(oauth_params.keys()):
            value = oauth_params[key]
            auth_header_parts.append(
                f'{quote(key, safe="")}="{quote(str(value), safe="")}"'
            )
        return f"OAuth {', '.join(auth_header_parts)}"

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
            # Per OAuth 1.0a, the PLAINTEXT signature IS the signing key
            # (percent-encoded consumer_secret&token_secret) verbatim; it
            # must NOT be base64-encoded.
            return signing_key
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

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickle serialization to exclude sensitive data.

        The deserialized instance will have no stored credentials, so
        ``is_authenticated()`` returns ``False`` and the handler must be
        re-authenticated via :meth:`authenticate` before use.

        Returns:
            Dictionary of attributes to pickle, excluding secrets.
        """
        state = self.__dict__.copy()
        state["_consumer_key"] = None
        state["_consumer_secret"] = None
        state["_access_token"] = None
        state["_access_token_secret"] = None
        # RLock is not reliably picklable: its internal C-level lock state
        # does not survive serialization. Exclude it here and recreate it
        # in __setstate__.
        state["_lock"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Recreate non-picklable state after deserialization.

        Args:
            state: The pickled state dictionary produced by
                :meth:`__getstate__`.
        """
        # Restore attributes via setattr (rather than self.__dict__.update)
        # so the deserialized lock is recreated cleanly below.
        for key, value in state.items():
            setattr(self, key, value)
        self._lock = threading.RLock()

    @property
    def consumer_key(self) -> str | None:
        """Get the consumer key."""
        with self._lock:
            return self._consumer_key

    @property
    def consumer_secret(self) -> str | None:
        """Get the consumer secret."""
        with self._lock:
            return self._consumer_secret

    @property
    def access_token(self) -> str | None:
        """Get the access token."""
        with self._lock:
            return self._access_token

    @property
    def access_token_secret(self) -> str | None:
        """Get the access token secret."""
        with self._lock:
            return self._access_token_secret
