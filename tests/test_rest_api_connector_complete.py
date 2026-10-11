"""Complete automated test suite for HTTP REST API JSON connector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from det.catalog import CatalogService
from det.catalog import config as catalog_config
from det.catalog.store import read_catalog_yaml
from det.connectors import get_connector
from det.connectors.apis.rest_api_connector import (
    RestApiConnector,
    extract_json_path,
    infer_json_type,
)
from det.connectors.errors import ConnectorValidationError
from det.gui import server


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


def test_rest_api_connector_registration():
    connector = get_connector("rest_api")
    assert isinstance(connector, RestApiConnector)
    assert connector.id == "rest_api"
    assert connector.name == "REST API"
    assert connector.group == "APIs"


def test_json_path_extraction():
    # 1. Root list
    assert extract_json_path([{"id": 1}, {"id": 2}], "") == [{"id": 1}, {"id": 2}]

    # 2. Nested dot path
    nested = {"response": {"status": "ok", "data": {"items": [{"sku": "A1"}, {"sku": "B2"}]}}}
    assert extract_json_path(nested, "response.data.items") == [{"sku": "A1"}, {"sku": "B2"}]

    # 3. Single list in dict auto-extracted
    dict_with_list = {"status": "success", "results": [{"val": 10}, {"val": 20}]}
    assert extract_json_path(dict_with_list, "") == [{"val": 10}, {"val": 20}]


def test_json_type_inference():
    assert infer_json_type([1, 2, 3]) == "Int64"
    assert infer_json_type([1, 2.5, 3]) == "Float64"
    assert infer_json_type([True, False, True]) == "Boolean"
    assert infer_json_type(["2024-05-01T10:30:00Z", "2024-05-02T11:00:00Z"]) == "DateTime"
    assert infer_json_type(["Alice", "Bob"]) == "String"
    assert infer_json_type([{"geo": "US"}, {"geo": "EU"}]) == "JSON"
    assert infer_json_type([None, None]) == "String"


def test_request_config_auth_and_headers():
    connector = RestApiConnector()

    # Bearer auth
    bearer_cfg = connector._build_request_config(
        source_config={"base_url": "https://api.github.com", "auth_type": "bearer"},
        credentials={"auth_token": "ghp_SecretGithubToken123"},
        table_options={"endpoint": "/user/repos"},
    )
    assert bearer_cfg["full_url"] == "https://api.github.com/user/repos"
    assert bearer_cfg["headers"]["Authorization"] == "Bearer ghp_SecretGithubToken123"

    # API Key auth
    api_key_cfg = connector._build_request_config(
        source_config={
            "base_url": "https://api.weather.com",
            "auth_type": "api_key",
            "api_key_header": "X-API-KEY",
            "custom_headers": '{"X-Env": "prod"}',
        },
        credentials={"auth_token": "WeatherKey999"},
        table_options={"endpoint": "forecast", "query_params": '{"city": "London"}'},
    )
    assert api_key_cfg["full_url"] == "https://api.weather.com/forecast"
    assert api_key_cfg["headers"]["X-API-KEY"] == "WeatherKey999"
    assert api_key_cfg["headers"]["X-Env"] == "prod"
    assert api_key_cfg["params"]["city"] == "London"


@patch("httpx.Client.get")
def test_rest_api_connection_testing(mock_get):
    connector = RestApiConnector()

    # Success 200 OK
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    res = connector.test_connection(source_config={"base_url": "https://api.example.com"})
    assert res.success is True
    assert "200 OK" in res.message

    # Unauthorized 401
    mock_resp.status_code = 401
    fail_res = connector.test_connection(source_config={"base_url": "https://api.example.com"})
    assert fail_res.success is False
    assert "Unauthorized" in fail_res.message


@patch("httpx.Client.get")
def test_rest_api_discovery_openapi(mock_get):
    connector = RestApiConnector()

    # Mock openapi.json response
    mock_doc_resp = MagicMock()
    mock_doc_resp.status_code = 200
    mock_doc_resp.json.return_value = {
        "paths": {
            "/api/v1/users": {"get": {}},
            "/api/v1/orders": {"get": {}},
            "/api/v1/inventory": {"get": {}},
        }
    }
    mock_get.return_value = mock_doc_resp

    discovered = connector.discover_objects(source_config={"base_url": "https://api.service.io"})
    assert len(discovered) == 3
    paths = [d.path for d in discovered]
    assert "/api/v1/users" in paths
    assert "/api/v1/orders" in paths


@patch("httpx.Client.get")
def test_rest_api_schema_inference(mock_get):
    connector = RestApiConnector()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "items": [
                {
                    "user_id": 101,
                    "username": "alice",
                    "rating": 4.85,
                    "is_active": True,
                    "last_login": "2024-06-01T14:22:00Z",
                    "profile": {"tier": "gold"},
                },
                {
                    "user_id": 102,
                    "username": "bob",
                    "rating": 3.90,
                    "is_active": False,
                    "last_login": "2024-05-20T09:15:00Z",
                    "profile": {"tier": "bronze"},
                },
            ]
        }
    }
    mock_get.return_value = mock_resp

    schema = connector.infer_schema(
        source_config={"base_url": "https://api.corp.com"},
        table_options={"endpoint": "/users", "data_path": "data.items"},
    )

    assert schema.row_count_estimate == 2
    cols = {c.name: c for c in schema.columns}

    assert cols["user_id"].type == "Int64"
    assert cols["username"].type == "String"
    assert cols["rating"].type == "Float64"
    assert cols["is_active"].type == "Boolean"
    assert cols["last_login"].type == "DateTime"
    assert cols["profile"].type == "JSON"


@patch("httpx.Client.get")
def test_rest_api_preview_and_pagination(mock_get):
    connector = RestApiConnector()

    # Test page-based pagination
    def mock_pagination_get(url, params=None):
        page = (params or {}).get("page", 1)
        resp = MagicMock()
        resp.status_code = 200
        if page == 1:
            resp.json.return_value = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        elif page == 2:
            resp.json.return_value = [{"id": 3, "name": "Item 3"}]
        else:
            resp.json.return_value = []
        return resp

    mock_get.side_effect = mock_pagination_get

    preview = connector.preview(
        source_config={"base_url": "https://api.store.com"},
        table_options={"endpoint": "/products", "pagination_type": "page", "page_size": 2},
        limit=10,
    )

    assert len(preview.rows) == 3
    assert preview.columns == ["id", "name"]
    assert preview.rows[0]["name"] == "Item 1"
    assert preview.rows[2]["name"] == "Item 3"


@patch("httpx.Client.get")
def test_rest_api_polars_scan(mock_get):
    connector = RestApiConnector()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"metric": "cpu", "value": 78.5},
        {"metric": "ram", "value": 62.1},
    ]
    mock_get.return_value = mock_resp

    df = connector.read_polars(
        source_config={"base_url": "https://metrics.cloud.net"},
        table_options={"endpoint": "/sys"},
    )

    assert df.shape == (2, 2)
    assert "metric" in df.columns
    assert df["value"].mean() == pytest.approx(70.3)


def test_rest_api_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "api_catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "API Data Catalog")

    # 1. Create a reusable REST connection with bearer token credentials
    service.create_connection(
        name="GitHub REST API",
        connector="rest_api",
        config={"base_url": "https://api.github.com", "auth_type": "bearer"},
        credentials={"auth_token": "ghp_HighlyConfidentialToken999"},
        description="GitHub developer REST API v3",
    )
    conn_list = service.list_connections()
    assert any(c["id"] == "github_rest_api" for c in conn_list)

    # Verify secret is NOT leaked into catalog YAML
    yaml_text = read_catalog_yaml(cat_yaml)
    assert "ghp_HighlyConfidentialToken999" not in yaml_text

    # 2. Add table referencing that connection
    service.create_table(
        name="github_repo_issues",
        namespace="default",
        connector="rest_api",
        connection_id="github_rest_api",
        options={"endpoint": "/repos/det-labs/det-core/issues", "data_path": ""},
        description="Active bug reports and features from GitHub API",
    )

    state = service.state()
    default_cat = next(c for c in state.categories if c["name"] == "default")
    assert any(t["name"] == "github_repo_issues" for t in default_cat["tables"])

    # Verify YAML saved table metadata
    saved_yaml = read_catalog_yaml(cat_yaml)
    assert "github_repo_issues" in saved_yaml
    assert "github_rest_api" in saved_yaml


def test_rest_api_validation_errors():
    connector = RestApiConnector()

    # Missing base_url
    with pytest.raises(ConnectorValidationError, match="Base URL is required"):
        connector._build_request_config(source_config={})

