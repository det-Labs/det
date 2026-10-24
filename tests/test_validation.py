"""Unit tests for identifier validation and SQL safety restrictions."""

import pytest

from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.models.definition import ModelDefinition
from det.validation import validate_identifier


def test_valid_identifiers() -> None:
    """Verify standard legal SQL identifiers pass validation."""
    valid_names = [
        "stg_orders",
        "customers_data",
        "fct_sales_2024",
        "_internal_table",
        "my_long_table_name_with_underscores_123",
        "UPPERCASE_MODEL",
        "CamelCaseModel",
    ]
    for name in valid_names:
        assert validate_identifier(name, "Model name") == name


def test_invalid_identifiers_with_spaces() -> None:
    """Verify names with spaces or tabs are rejected."""
    bad_names = ["my model", " stg_orders", "customers ", "fct\tsales", "hello world"]
    for name in bad_names:
        with pytest.raises(ValueError, match="cannot contain spaces"):
            validate_identifier(name, "Model name")


def test_invalid_identifiers_starting_with_number() -> None:
    """Verify names starting with digits are rejected."""
    bad_names = ["123_orders", "1stg", "9sales"]
    for name in bad_names:
        with pytest.raises(ValueError, match="cannot start with a number"):
            validate_identifier(name, "Model name")


def test_invalid_identifiers_with_special_characters() -> None:
    """Verify hyphens, dots, slashes, and symbols are rejected."""
    bad_names = [
        "stg-orders",
        "dim.users",
        "sales/2024",
        "calc+col",
        "cust#id",
        "model;drop",
        "test@db",
        "name!",
        "order(1)",
    ]
    for name in bad_names:
        with pytest.raises(ValueError, match="contains illegal characters"):
            validate_identifier(name, "Model name")


def test_reserved_sql_keywords_rejected() -> None:
    """Verify SQL keywords cannot be used as names."""
    keywords = ["select", "from", "where", "table", "view", "order", "group", "having", "join"]
    for kw in keywords:
        with pytest.raises(ValueError, match="reserved SQL keyword"):
            validate_identifier(kw, "Model name")
        with pytest.raises(ValueError, match="reserved SQL keyword"):
            validate_identifier(kw.upper(), "Connection name")


def test_empty_or_too_long_identifier() -> None:
    """Verify empty names and names exceeding 64 characters are rejected."""
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_identifier("", "Connection name")

    long_name = "a" * 65
    with pytest.raises(ValueError, match="exceeds maximum length"):
        validate_identifier(long_name, "Model name")


def test_model_and_connection_definitions_enforce_validation() -> None:
    """Verify ModelDefinition and ConnectionDefinition reject invalid names upon instantiation."""
    with pytest.raises(ValueError, match="cannot contain spaces"):
        ModelDefinition(name="invalid model name")

    with pytest.raises(ValueError, match="contains illegal characters"):
        ConnectionDefinition(
            name="invalid-conn-name",
            type="duckdb",
            tier=ConnectionTier.DATABASE,
        )

