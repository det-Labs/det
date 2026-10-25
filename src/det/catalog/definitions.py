"""Connection definition model conforming to the engine Mountable protocol."""

from dataclasses import dataclass, field
from typing import Any

from det.catalog.base import ConnectionTier


@dataclass
class ConnectionDefinition:
    """Represents a declarative data source connection configuration."""

    name: str
    type: str
    tier: ConnectionTier
    options: dict[str, Any] = field(default_factory=dict)
    credentials: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    folder: str = ""

    def __post_init__(self) -> None:
        """Validate connection identifier safety."""
        from det.validation import validate_identifier
        validate_identifier(self.name, "Connection name")

    @property
    def tier_value(self) -> str:
        """String representation of the tier."""
        return self.tier.value

    def get_mount_sql(self) -> str:
        """Generate the DuckDB SQL statement to mount this connection."""
        if self.tier == ConnectionTier.ENTITY:
            return self._build_entity_sql()
        return self._build_database_sql()

    def _build_entity_sql(self) -> str:
        """Construct CREATE OR REPLACE VIEW statement for entity connections."""
        custom_query = self.options.get("query")
        if custom_query:
            return f"CREATE OR REPLACE VIEW {self.name} AS {custom_query}"

        source_path = (
            self.options.get("path")
            or self.options.get("table_path")
            or self.options.get("url", "")
        )
        conn_type = self.type.lower()
        if conn_type == "onelake" and not source_path:
            workspace = str(self.options.get("workspace", "")).strip()
            lakehouse = str(self.options.get("lakehouse", "")).strip()
            table = str(self.options.get("table", "")).strip()
            if workspace and lakehouse and table:
                source_path = (
                    f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com/"
                    f"{lakehouse}.Lakehouse/Tables/{table}"
                )

        if (
            source_path
            and not source_path.startswith(("http://", "https://", "s3://", "gs://", "gcs://", "azure://", "abfss://"))
        ):
            source_path = source_path.replace("\\", "/")

        escaped_path = source_path.replace("'", "''")
        read_expr = self._determine_read_expression(escaped_path)
        return f"CREATE OR REPLACE VIEW {self.name} AS SELECT * FROM {read_expr}"

    def _determine_read_expression(self, path: str) -> str:
        """Determine appropriate DuckDB read function based on type and path."""
        conn_type = self.type.lower()
        if (
            conn_type in ("delta", "delta_lake", "onelake")
            or path.endswith(".delta")
            or "/_delta_log" in path
        ):
            return f"delta_scan('{path}')"
        if conn_type in ("csv",) or path.endswith((".csv", ".tsv")):
            return f"read_csv_auto('{path}')"
        if conn_type in ("json",) or path.endswith((".json", ".ndjson")):
            return f"read_json_auto('{path}')"
        return f"read_parquet('{path}')"

    def get_secret_sql(self, resolver: Any = None) -> str | None:
        """Generate DuckDB CREATE SECRET statement if cloud credentials exist."""
        conn_type = self.type.lower()
        creds = dict(self.credentials)
        if resolver:
            creds = resolver.resolve_item(creds)

        secret_name = f"sec_{self.name}"

        # 1. Google Cloud Storage (GCS)
        if conn_type in ("gcs", "gs"):
            key_id = creds.get("key_id") or creds.get("hmac_key")
            secret_key = creds.get("secret_key") or creds.get("secret")
            bearer_token = creds.get("bearer_token") or creds.get("token")
            endpoint = creds.get("endpoint") or self.options.get("endpoint")

            clauses = ["TYPE GCS"]
            if key_id and secret_key:
                clauses.append(f"KEY_ID '{str(key_id).replace("'", "''")}'")
                clauses.append(f"SECRET '{str(secret_key).replace("'", "''")}'")
            elif bearer_token:
                clauses.append(f"BEARER_TOKEN '{str(bearer_token).replace("'", "''")}'")

            if endpoint:
                clauses.append(f"ENDPOINT '{str(endpoint).replace("'", "''")}'")

            if len(clauses) == 1:
                return None
            return f"CREATE OR REPLACE TEMPORARY SECRET {secret_name} ({', '.join(clauses)})"

        # 2. Azure Blob / ADLS Gen2 / Microsoft Fabric OneLake
        if conn_type in ("azure", "abfss", "onelake"):
            conn_str = creds.get("connection_string") or self.options.get("connection_string")
            tenant_id = creds.get("tenant_id") or self.options.get("tenant_id")
            client_id = creds.get("client_id") or self.options.get("client_id")
            client_secret = creds.get("client_secret") or creds.get("client_secret")
            account_name = creds.get("account_name") or self.options.get("account_name")
            endpoint = creds.get("endpoint") or self.options.get("endpoint")

            clauses = ["TYPE AZURE"]
            if conn_str:
                clauses.append(f"CONNECTION_STRING '{str(conn_str).replace("'", "''")}'")
                return f"CREATE OR REPLACE TEMPORARY SECRET {secret_name} ({', '.join(clauses)})"

            if tenant_id and client_id and client_secret:
                clauses.append("PROVIDER SERVICE_PRINCIPAL")
                clauses.append(f"TENANT_ID '{str(tenant_id).replace("'", "''")}'")
                clauses.append(f"CLIENT_ID '{str(client_id).replace("'", "''")}'")
                clauses.append(f"CLIENT_SECRET '{str(client_secret).replace("'", "''")}'")
                if account_name:
                    clauses.append(f"ACCOUNT_NAME '{str(account_name).replace("'", "''")}'")
                if endpoint:
                    clauses.append(f"ENDPOINT '{str(endpoint).replace("'", "''")}'")
                return f"CREATE OR REPLACE TEMPORARY SECRET {secret_name} ({', '.join(clauses)})"

            if account_name:
                clauses.append(f"ACCOUNT_NAME '{str(account_name).replace("'", "''")}'")
                if endpoint:
                    clauses.append(f"ENDPOINT '{str(endpoint).replace("'", "''")}'")
                return f"CREATE OR REPLACE TEMPORARY SECRET {secret_name} ({', '.join(clauses)})"

            return None

        # 3. AWS S3 / MinIO / R2
        if conn_type in ("s3", "aws") or any(
            k in creds
            for k in (
                "key_id",
                "access_key_id",
                "aws_access_key_id",
                "secret_key",
                "secret_access_key",
            )
        ):
            key_id = (
                creds.get("key_id")
                or creds.get("access_key_id")
                or creds.get("aws_access_key_id")
            )
            secret_key = (
                creds.get("secret_key")
                or creds.get("secret_access_key")
                or creds.get("secret")
            )
            region = creds.get("region") or self.options.get("region")
            endpoint = creds.get("endpoint") or self.options.get("endpoint")
            session_token = creds.get("session_token") or creds.get("aws_session_token")
            url_style = creds.get("url_style") or self.options.get("url_style")
            use_ssl = creds.get("use_ssl", self.options.get("use_ssl"))

            clauses = ["TYPE S3"]
            if key_id:
                clauses.append(f"KEY_ID '{str(key_id).replace("'", "''")}'")
            if secret_key:
                clauses.append(f"SECRET '{str(secret_key).replace("'", "''")}'")
            if region:
                clauses.append(f"REGION '{str(region).replace("'", "''")}'")
            if session_token:
                clauses.append(f"SESSION_TOKEN '{str(session_token).replace("'", "''")}'")
            if endpoint:
                clauses.append(f"ENDPOINT '{str(endpoint).replace("'", "''")}'")
            if url_style:
                clauses.append(f"URL_STYLE '{str(url_style).replace("'", "''")}'")
            if use_ssl is not None:
                clauses.append(f"USE_SSL {str(use_ssl).lower()}")

            # If no credentials provided at all, return None
            if len(clauses) == 1:
                return None
            return f"CREATE OR REPLACE TEMPORARY SECRET {secret_name} ({', '.join(clauses)})"

        return None

    def _build_database_sql(self) -> str:
        """Construct ATTACH statement for database connections."""
        conn_type = self.type.upper()
        conn_str = self._resolve_database_connection_string()
        escaped_str = conn_str.replace("'", "''")

        if self.type.lower() in ("duckdb", ""):
            return f"ATTACH '{escaped_str}' AS {self.name}"
        return f"ATTACH '{escaped_str}' AS {self.name} (TYPE {conn_type})"

    def _resolve_database_connection_string(self) -> str:
        """Extract or compose database connection string."""
        explicit_str = (
            self.credentials.get("connection_string")
            or self.options.get("connection_string")
            or self.options.get("path")
        )
        if explicit_str:
            return str(explicit_str)

        parts: list[str] = []
        for key in ("host", "port", "dbname", "database", "user", "password"):
            val = self.credentials.get(key)
            if val is not None:
                parts.append(f"{key}={val}")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert definition to dictionary representation for YAML export."""
        res = {
            "type": self.type,
            "tier": self.tier.value,
            "options": self.options,
            "credentials": self.credentials,
            "description": self.description,
        }
        if self.folder:
            res["folder"] = self.folder
        return res

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "ConnectionDefinition":
        """Instantiate connection definition from a parsed dictionary."""
        raw_tier = data.get("tier", ConnectionTier.ENTITY.value)
        tier = ConnectionTier(raw_tier)
        return cls(
            name=name,
            type=str(data.get("type", "csv")),
            tier=tier,
            options=dict(data.get("options", {})),
            credentials=dict(data.get("credentials", {})),
            description=str(data.get("description", "")),
            folder=str(data.get("folder", "")),
        )

