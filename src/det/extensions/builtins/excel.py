"""Built-in connector for Microsoft Excel (.xlsx) workbooks."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class ExcelConnector(BaseConnector):
    """Connector reading Microsoft Excel (.xlsx) spreadsheets via DuckDB excel extension."""

    key = "excel"
    label = "Excel Workbook"
    description = "Read Microsoft Excel (.xlsx) workbooks directly into DuckDB."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="Workbook Path",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="data/spreadsheets/*.xlsx",
                description="Local path or glob to .xlsx workbook files.",
            ),
            ConnectorField(
                name="sheet",
                label="Sheet Name",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="Sheet1",
                description="Optional specific worksheet name to query.",
            ),
            ConnectorField(
                name="header",
                label="Has Header",
                field_type=FieldType.BOOLEAN,
                default=True,
                description="Whether the first row contains column headers.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        path = str(options.get("path", "")).replace("'", "''")
        sheet = options.get("sheet")
        header = "true" if options.get("header", True) else "false"

        sheet_clause = f", sheet='{sheet}'" if sheet else ""
        return f"read_xlsx('{path}'{sheet_clause}, header={header})"

    def get_attach_sql(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str | None:
        return None

    def test_connection(
        self,
        con: duckdb.DuckDBPyConnection,
        options: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bool:
        sql = f"SELECT 1 FROM ({self.get_read_sql(options)}) LIMIT 1"
        con.execute(sql).fetchall()
        return True

