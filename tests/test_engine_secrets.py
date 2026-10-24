"""Tests for secret resolution and credential masking."""

import os
import pytest
from det.engine.secrets import SecretResolver


def test_resolve_raw_string_without_variables() -> None:
    """Verify raw strings without variables remain unchanged."""
    resolver = SecretResolver()
    assert resolver.resolve_value("regular_password") == "regular_password"


def test_resolve_existing_env_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ${VAR} resolves to environment variable value."""
    monkeypatch.setenv("TEST_DB_PASS", "s3cr3t_v@l")
    resolver = SecretResolver()
    assert resolver.resolve_value("${TEST_DB_PASS}") == "s3cr3t_v@l"


def test_resolve_env_variable_with_default_fallback() -> None:
    """Verify ${VAR:-default} uses default when env var is absent."""
    resolver = SecretResolver()
    resolved = resolver.resolve_value("${NON_EXISTENT_VAR:-my_default}")
    assert resolved == "my_default"


def test_resolve_missing_env_variable_raises() -> None:
    """Verify ${VAR} without default raises ValueError if not set."""
    resolver = SecretResolver()
    with pytest.raises(ValueError, match="Missing environment variable"):
        resolver.resolve_value("${TOTALLY_ABSENT_VAR_12345}")


def test_mask_secret() -> None:
    """Verify masking returns asterisks."""
    resolver = SecretResolver()
    assert resolver.mask_secret("my_super_secret") == "******"
    assert resolver.mask_secret("") == ""


def test_resolve_nested_dictionary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify recursive resolution on dict structures."""
    monkeypatch.setenv("DET_USER", "admin")
    resolver = SecretResolver()
    data = {
        "user": "${DET_USER}",
        "port": 5432,
        "nested": {"db": "${DET_DB:-postgres}"},
        "tags": ["${DET_USER}"],
    }
    resolved = resolver.resolve_item(data)
    assert resolved == {
        "user": "admin",
        "port": 5432,
        "nested": {"db": "postgres"},
        "tags": ["admin"],
    }

