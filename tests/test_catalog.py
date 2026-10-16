"""Tests for YAML catalog storage and connector metadata."""

import tempfile
import unittest
import uuid
from pathlib import Path

from det.api import configure_ui, infer_connection_schema, preview_connection
from det.catalog import CatalogStore
from det.connectors import CSV_CONNECTOR, connector_metadata
from det.workspace import initialize_workspace


class CatalogStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.store = CatalogStore(self.workspace)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_catalog_items_have_unique_guids_and_default_folder(self) -> None:
        catalog = self.store.read()["catalog"]
        self.assertEqual(len(catalog["folders"]), 1)
        self.assertEqual(catalog["folders"][0]["name"], "Default")
        identifiers = [
            catalog["id"],
            *(folder["id"] for folder in catalog["folders"]),
        ]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for identifier in identifiers:
            self.assertEqual(str(uuid.UUID(identifier)), identifier)

    def test_datafusion_schema_inference_and_preview(self) -> None:
        initialize_workspace(self.workspace)
        configure_ui(self.workspace)
        source_path = self.workspace / "orders.csv"
        source_path.write_text(
            "order_id,region\n1,north\n2,south\n",
            encoding="utf-8",
        )
        folder_id = self.store.read()["catalog"]["folders"][0]["id"]
        connection = self.store.add_connection(
            folder_id,
            {
                "name": "Orders",
                "connector": CSV_CONNECTOR.guid,
                "options": {
                    "path": str(source_path),
                    "has_header": True,
                },
            },
        )["catalog"]["folders"][0]["connections"][0]

        inferred = infer_connection_schema(connection["id"])
        self.assertEqual(
            [column["name"] for column in inferred["columns"]],
            ["order_id", "region"],
        )
        preview = preview_connection(connection["id"])
        self.assertEqual(preview["row_limit"], 50)
        self.assertEqual(len(preview["rows"]), 2)
        self.assertEqual(preview["rows"][0]["region"], "north")

    def test_catalog_create_switch_folder_and_connection_round_trip(self) -> None:
        created = self.store.create_catalog("Analytics")
        self.assertEqual(created["catalog"]["name"], "Analytics")
        reopened = self.store.create_catalog("Analytics")
        self.assertEqual(reopened["filename"], created["filename"])
        self.assertEqual(reopened["catalog"]["id"], created["catalog"]["id"])
        new_folder = self.store.add_folder("Inputs")
        folder_id = new_folder["catalog"]["folders"][1]["id"]
        saved = self.store.add_connection(
            folder_id,
            {
                "name": "Orders",
                "folder_id": folder_id,
                "connector": CSV_CONNECTOR.guid,
                "is_source": True,
                "is_destination": True,
                "description": "Daily order extracts.",
                "options": {
                    "path": "data/orders",
                    "write_mode": "append",
                },
                "columns": [
                    {
                        "name": "order_id",
                        "data_type": "int64",
                        "description": "Stable order identifier.",
                    }
                ],
            },
        )
        connection = saved["catalog"]["folders"][1]["connections"][0]
        self.assertEqual(connection["options"]["write_mode"], "append")
        self.assertEqual(connection["columns"][0]["description"], "Stable order identifier.")
        self.assertEqual(self.store.get_connection(connection["id"])["folder_id"], folder_id)
        self.assertEqual(self.store.select("default.yaml")["catalog"]["name"], "Default catalog")

    def test_schema_inference_preserves_column_guid_and_description(self) -> None:
        folder_id = self.store.read()["catalog"]["folders"][0]["id"]
        self.store.add_connection(
            folder_id,
            {
                "name": "Orders",
                "connector": CSV_CONNECTOR.guid,
                "columns": [
                    {
                        "name": "order_id",
                        "data_type": "int64",
                        "description": "Stable order identifier.",
                    }
                ],
            },
        )
        connection_id = self.store.read()["catalog"]["folders"][0]["connections"][0]["id"]
        original_column_id = self.store.get_connection(connection_id)["columns"][0]["id"]
        saved = self.store.save_connection_columns(
            connection_id,
            [{"name": "order_id", "data_type": "int32", "nullable": False}],
        )
        column = saved["columns"][0]
        self.assertEqual(column["id"], original_column_id)
        self.assertEqual(column["description"], "Stable order identifier.")
        self.assertEqual(column["data_type"], "int32")
        self.assertFalse(column["nullable"])

    def test_catalog_must_keep_a_folder(self) -> None:
        folder_id = self.store.read()["catalog"]["folders"][0]["id"]
        with self.assertRaisesRegex(ValueError, "at least one folder"):
            self.store.delete_folder(folder_id)

    def test_connections_must_have_at_least_one_role(self) -> None:
        folder_id = self.store.read()["catalog"]["folders"][0]["id"]
        with self.assertRaisesRegex(ValueError, "must be marked"):
            self.store.add_connection(
                folder_id,
                {
                    "name": "Orders",
                    "connector": CSV_CONNECTOR.guid,
                    "is_source": False,
                    "is_destination": False,
                },
            )

    def test_connection_names_must_be_valid_sql_identifiers(self) -> None:
        folder_id = self.store.read()["catalog"]["folders"][0]["id"]
        for invalid_name in ("Sales data", "1Sales", "sales-name", "x" * 101):
            with self.subTest(name=invalid_name):
                with self.assertRaises(ValueError):
                    self.store.add_connection(
                        folder_id,
                        {
                            "name": invalid_name,
                            "connector": CSV_CONNECTOR.guid,
                        },
                    )

    def test_profile_crud_and_bulk_add_connections(self) -> None:
        from det.catalog import resolve_connection_options
        from det.connectors import POSTGRESQL_CONNECTOR

        # 1. Add Profile
        doc = self.store.add_profile({
            "name": "analytics_pg",
            "connector": POSTGRESQL_CONNECTOR.guid,
            "options": {
                "host": "db.example.com",
                "port": 5432,
                "database": "analytics",
                "user": "analyst",
                "password": "secret_password",
            },
        })
        profiles = doc["catalog"]["profiles"]
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["name"], "analytics_pg")
        profile_id = profiles[0]["id"]

        # 2. Get Profile
        fetched = self.store.get_profile(profile_id)
        self.assertEqual(fetched["name"], "analytics_pg")
        self.assertEqual(fetched["options"]["database"], "analytics")

        # 3. Bulk Add Connections referencing profile
        folder_id = doc["catalog"]["folders"][0]["id"]
        bulk_doc = self.store.bulk_add_connections(folder_id, [
            {
                "name": "pg_users",
                "connector": POSTGRESQL_CONNECTOR.guid,
                "profile": "analytics_pg",
                "is_source": True,
                "options": {"schema": "public", "table": "users"},
            },
            {
                "name": "pg_orders",
                "connector": POSTGRESQL_CONNECTOR.guid,
                "profile": "analytics_pg",
                "is_source": True,
                "options": {"schema": "public", "table": "orders"},
            },
            {
                "name": "pg_daily_report",
                "connector": POSTGRESQL_CONNECTOR.guid,
                "profile": "analytics_pg",
                "is_source": False,
                "is_destination": True,
                "options": {"schema": "public", "table": "daily_report", "write_mode": "overwrite"},
            },
        ])
        connections = bulk_doc["catalog"]["folders"][0]["connections"]
        self.assertEqual(len(connections), 3)

        # 4. Resolve connection options (merging credentials from profile)
        users_conn = connections[0]
        resolved = resolve_connection_options(users_conn, bulk_doc["catalog"])
        self.assertEqual(resolved["host"], "db.example.com")
        self.assertEqual(resolved["database"], "analytics")
        self.assertEqual(resolved["user"], "analyst")
        self.assertEqual(resolved["password"], "secret_password")
        self.assertEqual(resolved["schema"], "public")
        self.assertEqual(resolved["table"], "users")

        # 5. Delete profile in use should raise ValueError
        with self.assertRaises(ValueError):
            self.store.delete_profile(profile_id)

        # 6. Delete connections, then delete profile should succeed
        for conn in connections:
            self.store.delete_connection(conn["id"])
        del_doc = self.store.delete_profile(profile_id)
        self.assertEqual(len(del_doc["catalog"]["profiles"]), 0)

    def test_connector_metadata_exposes_stable_guids_and_fields(self) -> None:
        metadata = {item["key"]: item for item in connector_metadata()}
        for key in ("csv", "parquet"):
            self.assertIn(key, metadata)
            self.assertEqual(str(uuid.UUID(metadata[key]["id"])), metadata[key]["id"])
            self.assertTrue(metadata[key]["fields"])
        csv_fields = {field["name"] for field in metadata["csv"]["fields"]}
        self.assertIn("has_header", csv_fields)
        self.assertIn("file_pattern", csv_fields)


if __name__ == "__main__":
    unittest.main()
