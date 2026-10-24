"""Validation utilities for identifiers, names, and SQL safety."""

import re

# Valid SQL identifier: starts with letter or underscore, followed by letters, digits, or underscores
IDENTIFIER_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SQL_RESERVED_KEYWORDS = {
    "all", "alter", "and", "as", "between", "by", "case", "cast", "check", "column",
    "constraint", "create", "cross", "database", "default", "delete", "distinct",
    "drop", "else", "end", "except", "false", "foreign", "from", "full", "group",
    "having", "in", "index", "inner", "insert", "intersect", "into", "is", "join",
    "key", "left", "like", "limit", "natural", "not", "null", "offset", "on", "or",
    "order", "outer", "primary", "references", "right", "select", "set", "table",
    "then", "to", "true", "union", "unique", "update", "user", "values", "view",
    "when", "where", "with",
}


def validate_identifier(name: str, entity_type: str = "Identifier") -> str:
    """Validate that name is a safe, valid SQL identifier without spaces or special characters.

    Raises ValueError with diagnostic feedback if invalid.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{entity_type} cannot be empty.")

    if any(c.isspace() for c in name):
        raise ValueError(
            f"{entity_type} '{name}' cannot contain spaces or whitespace. "
            "Use underscores ('_') instead (e.g. 'my_model_name')."
        )

    clean_name = name.strip()

    if clean_name[0].isdigit():
        raise ValueError(
            f"{entity_type} '{clean_name}' cannot start with a number. "
            "It must begin with a letter or an underscore."
        )

    if not IDENTIFIER_REGEX.match(clean_name):
        raise ValueError(
            f"{entity_type} '{clean_name}' contains illegal characters. "
            "Only letters, numbers, and underscores ('_') are allowed (no hyphens, dots, or symbols)."
        )

    if len(clean_name) > 64:
        raise ValueError(
            f"{entity_type} '{clean_name}' exceeds maximum length of 64 characters (has {len(clean_name)})."
        )

    if clean_name.lower() in SQL_RESERVED_KEYWORDS:
        raise ValueError(
            f"{entity_type} '{clean_name}' is a reserved SQL keyword and cannot be used as an identifier."
        )

    return clean_name
