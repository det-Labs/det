"""Secret resolution and credential masking for connection configurations."""

import os
import re
from typing import Any
from det.engine.base import BaseSecretResolver

# Pattern matching ${VAR_NAME} or ${VAR_NAME:-default_value}
ENV_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}")


class SecretResolver(BaseSecretResolver):
    """Resolves environment variables and masks sensitive credential values."""

    def resolve_value(self, raw: str) -> str:
        """Resolve all ${VAR} or ${VAR:-default} occurrences in a string."""
        if not isinstance(raw, str):
            return raw

        def _replace_match(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default_val = match.group(2)
            env_val = os.environ.get(var_name)

            if env_val is not None:
                return env_val
            if default_val is not None:
                return default_val
            raise ValueError(
                f"Missing environment variable: '{var_name}' without default."
            )

        return ENV_PATTERN.sub(_replace_match, raw)

    def mask_secret(self, raw: str) -> str:
        """Mask a sensitive string with asterisks."""
        if not raw:
            return ""
        return "******"

    def resolve_item(self, item: Any) -> Any:
        """Recursively resolve secrets within strings, lists, or dictionaries."""
        if isinstance(item, str):
            return self.resolve_value(item)
        if isinstance(item, dict):
            return {k: self.resolve_item(v) for k, v in item.items()}
        if isinstance(item, list):
            return [self.resolve_item(v) for v in item]
        return item

