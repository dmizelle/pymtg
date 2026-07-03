"""Authentication handlers for various MTG API providers.

This module provides authentication handling for different provider
requirements, including no auth, session cookies, OAuth1, OAuth2, and API keys.
"""

from pymtg.auth.api_key import APIKeyAuthHandler
from pymtg.auth.base import BaseAuthHandler
from pymtg.auth.no_auth import NoAuthHandler
from pymtg.auth.oauth1 import OAuth1Handler
from pymtg.auth.oauth2 import OAuth2ClientCredentialsHandler
from pymtg.auth.session import SessionAuthHandler

__all__ = [
    "BaseAuthHandler",
    "NoAuthHandler",
    "SessionAuthHandler",
    "OAuth1Handler",
    "OAuth2ClientCredentialsHandler",
    "APIKeyAuthHandler",
]
