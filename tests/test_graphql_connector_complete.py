"""Unit and integration test suite for GraphQL API Connector."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import polars as pl
import pytest

from det.catalog import CatalogService
from det.catalog import config as catalog_config
from det.catalog.store import read_catalog_yaml
from det.connectors.apis.graphql_connector import (
    GraphQLConnector,
    extract_graphql_records,
    get_nested_value,
)
from det.connectors.contract import ConnectorGroup
from det.connectors.errors import ConnectorValidationError
from det.connectors.registry import get_connector
from det.gui import server


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure catalog and connections YAML operate in a clean temporary directory."""
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    conn_path = config_dir / "connections.yaml"
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_path)
    from det.connectors import connections
    monkeypatch.setattr(connections, "_custom_connections_path", conn_path)
    server.set_service(None)
    yield
    server.set_service(None)


def test_graphql_connector_registration():
    connector = get_connector("graphql")
    assert connector is not None
    assert isinstance(connector, GraphQLConnector)
    assert connector.id == "graphql"
    assert connector.name == "GraphQL"
    assert connector.group == ConnectorGroup.APIS

    source_names = [f.name for f in connector.source_fields]
    assert "endpoint_url" in source_names
    assert "auth_type" in source_names
    assert "auth_token" in source_names

    table_names = [f.name for f in connector.table_fields]
    assert "query" in table_names
    assert "variables" in table_names
    assert "data_path" in table_names
    assert "pagination_type" in table_names


def test_nested_value_navigation():
    payload = {
        "data": {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cur123"},
                    "nodes": [{"id": 1}, {"id": 2}],
                }
            }
        }
    }
    assert get_nested_value(payload, "data.repository.issues.pageInfo.endCursor") == "cur123"
    assert get_nested_value(payload, "data.repository.issues.pageInfo.hasNextPage") is True
    assert get_nested_value(payload, "non.existent.path") is None


def test_graphql_record_extraction():
    # 1. Direct explicit path
    payload1 = {
        "data": {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
        }
    }
    records1 = extract_graphql_records(payload1, "data.users")
    assert len(records1) == 2
    assert records1[0]["name"] == "Alice"

    # 2. Auto-detection of list
    records2 = extract_graphql_records(payload1, None)
    assert len(records2) == 2
    assert records2[1]["name"] == "Bob"

    # 3. Relay edges/node unpacking
    relay_payload = {
        "data": {
            "search": {
                "edges": [
                    {"cursor": "c1", "node": {"id": "n1", "title": "First"}},
                    {"cursor": "c2", "node": {"id": "n2", "title": "Second"}},
                ]
            }
        }
    }
    relay_records = extract_graphql_records(relay_payload, "data.search.edges")
    assert len(relay_records) == 2
    assert relay_records[0]["id"] == "n1"
    assert relay_records[0]["title"] == "First"
    assert relay_records[0]["_cursor"] == "c1"

    # 4. Auto-detection with Relay structure
    relay_auto = extract_graphql_records(relay_payload, None)
    assert len(relay_auto) == 2
    assert relay_auto[1]["title"] == "Second"

    # 5. Single object record
    single_payload = {"data": {"user": {"id": 10, "username": "admin"}}}
    single_rec = extract_graphql_records(single_payload, None)
    assert len(single_rec) == 1
    assert single_rec[0]["username"] == "admin"


def test_graphql_request_config_auth_and_headers():
    connector = GraphQLConnector()

    # Bearer auth
    cfg_bearer = connector._build_request_config(
        source_config={"endpoint_url": "https://api.example.com/graphql", "auth_type": "bearer"},
        credentials={"auth_token": "secret_token_123"},
        table_options={"query": "query { hello }"},
    )
    assert cfg_bearer["endpoint_url"] == "https://api.example.com/graphql"
    assert cfg_bearer["headers"]["Authorization"] == "Bearer secret_token_123"
    assert cfg_bearer["headers"]["Content-Type"] == "application/json"
    assert cfg_bearer["query"] == "query { hello }"

    # API Key auth
    cfg_apikey = connector._build_request_config(
        source_config={
            "endpoint_url": "https://api.example.com/graphql",
            "auth_type": "api_key",
            "api_key_header": "X-API-KEY",
            "auth_token": "my-api-key",
            "custom_headers": '{"X-Environment": "production"}',
        },
    )
    assert cfg_apikey["headers"]["X-API-KEY"] == "my-api-key"
    assert cfg_apikey["headers"]["X-Environment"] == "production"

    # Basic auth
    cfg_basic = connector._build_request_config(
        source_config={
            "endpoint_url": "https://api.example.com/graphql",
            "auth_type": "basic",
            "username": "admin",
            "password": "pwd",
        },
    )
    assert cfg_basic["basic_auth"] == ("admin", "pwd")

    # Missing endpoint raises validation error
    with pytest.raises(ConnectorValidationError, match="Endpoint URL is required"):
        connector._build_request_config(source_config={})


@patch("httpx.Client.post")
def test_graphql_connection_testing(mock_post):
    connector = GraphQLConnector()
    source_cfg = {"endpoint_url": "https://api.example.com/graphql"}

    # Case 1: Success 200 OK
    resp_ok = MagicMock()
    resp_ok.status_code = 200
    resp_ok.json.return_value = {"data": {"__typename": "Query"}}
    mock_post.return_value = resp_ok

    res_ok = connector.test_connection(source_config=source_cfg)
    assert res_ok.success is True
    assert "Connected successfully" in res_ok.message

    # Case 2: GraphQL error in 200 payload
    resp_err = MagicMock()
    resp_err.status_code = 200
    resp_err.json.return_value = {"errors": [{"message": "Cannot query field"}]}
    mock_post.return_value = resp_err

    res_err = connector.test_connection(source_config=source_cfg)
    assert res_err.success is False
    assert "Cannot query field" in res_err.message

    # Case 3: HTTP 401 Unauthorized
    resp_401 = MagicMock()
    resp_401.status_code = 401
    mock_post.return_value = resp_401

    res_401 = connector.test_connection(source_config=source_cfg)
    assert res_401.success is False
    assert "Authentication failed" in res_401.message

    # Case 4: Network failure
    mock_post.side_effect = httpx.ConnectError("Failed to resolve host")
    res_fail = connector.test_connection(source_config=source_cfg)
    assert res_fail.success is False
    assert "GraphQL connection failed" in res_fail.message


@patch("httpx.Client.post")
def test_graphql_discovery_introspection(mock_post):
    connector = GraphQLConnector()
    source_cfg = {"endpoint_url": "https://api.example.com/graphql"}

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "__schema": {
                "queryType": {
                    "name": "Query",
                    "fields": [
                        {
                            "name": "users",
                            "description": "Fetch all user accounts",
                            "args": [{"name": "limit"}, {"name": "role"}],
                        },
                        {
                            "name": "orders",
                            "description": "Fetch purchase orders",
                            "args": [{"name": "status"}],
                        },
                    ],
                }
            }
        }
    }
    mock_post.return_value = resp

    discovered = connector.discover_objects(source_config=source_cfg)
    assert len(discovered) == 2
    names = [d.name for d in discovered]
    assert "users" in names
    assert "orders" in names
    assert discovered[0].metadata["arguments"] == ["limit", "role"]


@patch("httpx.Client.post")
def test_graphql_schema_inference(mock_post):
    connector = GraphQLConnector()
    source_cfg = {"endpoint_url": "https://api.example.com/graphql"}
    table_opts = {
        "query": "query GetProducts { products { id name price in_stock created_at } }",
        "data_path": "data.products",
    }

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "products": [
                {
                    "id": 101,
                    "name": "Mechanical Keyboard",
                    "price": 89.99,
                    "in_stock": True,
                    "created_at": "2026-10-11T10:00:00Z",
                },
                {
                    "id": 102,
                    "name": "Wireless Mouse",
                    "price": 49.50,
                    "in_stock": False,
                    "created_at": "2026-10-11T11:00:00Z",
                },
            ]
        }
    }
    mock_post.return_value = resp

    schema = connector.infer_schema(source_config=source_cfg, table_options=table_opts)
    assert schema.row_count_estimate == 2
    col_map = {c.name: c.type for c in schema.columns}
    assert col_map["id"] == "Int64"
    assert col_map["name"] == "String"
    assert col_map["price"] == "Float64"
    assert col_map["in_stock"] == "Boolean"
    assert col_map["created_at"] == "DateTime"


@patch("httpx.Client.post")
def test_graphql_preview_and_polars_scan(mock_post):
    connector = GraphQLConnector()
    source_cfg = {"endpoint_url": "https://api.example.com/graphql"}
    table_opts = {
        "query": "query GetUsers { users { id name details } }",
    }

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "users": [
                {"id": 1, "name": "Alice", "details": {"dept": "Eng", "level": 3}},
                {"id": 2, "name": "Bob", "details": {"dept": "Sales", "level": 2}},
            ]
        }
    }
    mock_post.return_value = resp

    # Preview test
    prev = connector.preview(source_config=source_cfg, table_options=table_opts, limit=10)
    assert prev.columns == ["id", "name", "details"]
    assert len(prev.rows) == 2
    assert prev.rows[0]["name"] == "Alice"
    assert json.loads(prev.rows[0]["details"]) == {"dept": "Eng", "level": 3}

    # Polars scan test
    df = connector.read_polars(source_config=source_cfg, table_options=table_opts)
    assert isinstance(df, pl.DataFrame)
    assert df.shape == (2, 3)
    assert df["id"].to_list() == [1, 2]
    assert df["name"].to_list() == ["Alice", "Bob"]


@patch("httpx.Client.post")
def test_graphql_cursor_relay_pagination(mock_post):
    connector = GraphQLConnector()
    source_cfg = {"endpoint_url": "https://api.example.com/graphql"}
    table_opts = {
        "query": "query ($after: String, $first: Int) { items(after: $after, first: $first) { pageInfo { hasNextPage endCursor } nodes { id name } } }",
        "data_path": "data.items.nodes",
        "pagination_type": "cursor",
        "cursor_variable": "after",
        "cursor_path": "data.items.pageInfo.endCursor",
        "has_next_page_path": "data.items.pageInfo.hasNextPage",
        "limit_variable": "first",
        "page_size": 2,
    }

    def mock_post_pages(url, json=None, **kwargs):
        variables = (json or {}).get("variables", {})
        cursor = variables.get("after")

        resp = MagicMock()
        resp.status_code = 200
        if cursor is None:
            # Page 1
            resp.json.return_value = {
                "data": {
                    "items": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                        "nodes": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}],
                    }
                }
            }
        elif cursor == "c1":
            # Page 2 (last page)
            resp.json.return_value = {
                "data": {
                    "items": {
                        "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                        "nodes": [{"id": 3, "name": "Item 3"}],
                    }
                }
            }
        else:
            resp.json.return_value = {
                "data": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []}}
            }
        return resp

    mock_post.side_effect = mock_post_pages

    df = connector.read_polars(source_config=source_cfg, table_options=table_opts)
    assert len(df) == 3
    assert df["id"].to_list() == [1, 2, 3]


def test_graphql_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "graphql_catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "GraphQL Catalog")

    # 1. Create connection with bearer token
    service.create_connection(
        name="GitHub GraphQL API",
        connector="graphql",
        config={"endpoint_url": "https://api.github.com/graphql", "auth_type": "bearer"},
        credentials={"auth_token": "ghp_MockSecretToken777"},
        description="GitHub official GraphQL API endpoint",
    )
    conn_list = service.list_connections()
    assert any(c["id"] == "github_graphql_api" for c in conn_list)

    # Verify secret token is NOT leaked into catalog YAML
    yaml_text = read_catalog_yaml(cat_yaml)
    assert "ghp_MockSecretToken777" not in yaml_text

    # 2. Add table referencing that connection
    service.create_table(
        name="github_issues_gql",
        namespace="default",
        connector="graphql",
        connection_id="github_graphql_api",
        options={
            "query": "query { repository(owner: \"det\", name: \"core\") { issues { nodes { id title } } } }",
            "data_path": "data.repository.issues.nodes",
        },
        description="GitHub issues extracted via GraphQL",
    )

    state = service.state()
    default_cat = next(c for c in state.categories if c["name"] == "default")
    assert any(t["name"] == "github_issues_gql" for t in default_cat["tables"])

    # Verify saved YAML contains table and connection reference
    saved_yaml = read_catalog_yaml(cat_yaml)
    assert "github_issues_gql" in saved_yaml
    assert "github_graphql_api" in saved_yaml


def test_graphql_validation_errors():
    connector = GraphQLConnector()
    # Missing query raises ConnectorValidationError
    with pytest.raises(ConnectorValidationError, match="GraphQL query document is required"):
        connector._fetch_records({
            "endpoint_url": "https://api.example.com/graphql",
            "headers": {},
            "timeout": 10,
            "basic_auth": None,
            "variables": {},
        })
