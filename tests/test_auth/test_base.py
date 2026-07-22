"""Tests for the base authentication handler module.

This module tests that pymtg.auth.base correctly exposes the
AuthenticationError exception referenced in its abstract method
docstrings, and that the abstract interface is well-formed.
"""

import inspect
import typing

import pytest
import requests

from pymtg.auth.base import BaseAuthHandler
from pymtg.exceptions import AuthenticationError


class TestBaseAuthHandlerImports:
    """Tests that BaseAuthHandler module exposes referenced exceptions."""

    def test_authentication_error_imported_in_base_module(self):
        """Test that AuthenticationError is available in pymtg.auth.base.

        The abstract method docstrings reference AuthenticationError in
        their `Raises:` sections. This test verifies the exception is
        importable from the base module's namespace, so callers and
        subclasses can catch it by reference from either location.
        """
        import pymtg.auth.base as base_module

        assert base_module.AuthenticationError is AuthenticationError

    def test_authentication_error_importable_from_base(self):
        """Test that AuthenticationError can be imported from pymtg.auth.base."""
        from pymtg.auth.base import AuthenticationError as ImportedError

        assert ImportedError is AuthenticationError


class TestBaseAuthHandlerInterface:
    """Tests for the BaseAuthHandler abstract interface."""

    def test_base_auth_handler_is_abstract(self):
        """Test that BaseAuthHandler cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract methods"):
            BaseAuthHandler()  # type: ignore[abstract]  # intentional

    def test_abstract_methods_exist(self):
        """Test that all required abstract methods are defined."""
        abstract_methods = {
            "authenticate",
            "is_authenticated",
            "refresh",
            "apply_auth",
            "clear_auth",
        }
        for method_name in abstract_methods:
            assert hasattr(
                BaseAuthHandler, method_name
            ), f"BaseAuthHandler must define {method_name}"

    def test_abstract_methods_are_abstract(self):
        """Test that interface methods are marked as abstract."""
        abstract_methods = [
            "authenticate",
            "is_authenticated",
            "refresh",
            "apply_auth",
            "clear_auth",
        ]
        for method_name in abstract_methods:
            method = getattr(BaseAuthHandler, method_name)
            assert getattr(
                method, "__isabstractmethod__", False
            ), f"{method_name} must be marked as abstract"

    def test_authenticate_docstring_references_authentication_error(self):
        """Test that authenticate docstring mentions AuthenticationError."""
        doc = BaseAuthHandler.authenticate.__doc__ or ""
        assert "AuthenticationError" in doc

    def test_refresh_docstring_references_authentication_error(self):
        """Test that refresh docstring mentions AuthenticationError."""
        doc = BaseAuthHandler.refresh.__doc__ or ""
        assert "AuthenticationError" in doc

    def test_authenticate_signature(self):
        """Test that authenticate is a callable method with no required params."""
        sig = inspect.signature(BaseAuthHandler.authenticate)
        params = list(sig.parameters.values())
        # authenticate should accept only self (no required args beyond self)
        required = [
            p
            for p in params
            if p.default is inspect.Parameter.empty
            and p.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        ]
        assert (
            len(required) == 1
        ), "authenticate must not require parameters beyond self"

    def test_is_authenticated_returns_bool(self):
        """Test that is_authenticated is annotated to return bool."""
        try:
            hints = typing.get_type_hints(BaseAuthHandler.is_authenticated)
        except NameError:
            hints = {}
        assert (
            hints.get("return") is bool
        ), "is_authenticated must be annotated to return bool"

    def test_apply_auth_accepts_session(self):
        """Test that apply_auth accepts a requests.Session parameter."""
        sig = inspect.signature(BaseAuthHandler.apply_auth)
        assert "session" in sig.parameters, "apply_auth must accept a session parameter"
        assert sig.parameters["session"].annotation is requests.Session
