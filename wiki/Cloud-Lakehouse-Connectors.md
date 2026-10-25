# Cloud & Lakehouse Connectors Guide

`det` provides built-in, first-class connectivity to all major modern cloud object stores and open table lakehouse formats.

---

## 🌊 Delta Lake (Read & Write)

`det` supports both high-throughput vectorized reads and ACID transaction writes for Delta Lake.

### Reading Delta Tables
Reads leverage DuckDB's vectorized `delta_scan` extension:
```yaml
connections:
  customer_delta:
    type: delta_lake
    tier: entity
    options:
      path: "s3://my-bucket/delta/customers"
```

### Writing to Delta Tables
Pipelines can publish model results directly to Delta Lake directories in either `replace` (overwrite) or `append` mode using PyArrow streaming:
```yaml
{{ config(
    materialized='table',
    destinations=[
        {'target': 's3://my-bucket/delta/customers', 'format': 'delta', 'mode': 'append'}
    ]
) }}
```

---

## ☁️ Amazon S3 & S3-Compatible Storage

Connects to AWS S3, Cloudflare R2, Ceph, and MinIO.

```yaml
connections:
  s3_landing:
    type: s3
    tier: entity
    options:
      path: "s3://analytics-bucket/raw/events.parquet"
      region: "us-east-1"
      endpoint: "minio.internal:9000"  # Optional for S3-compatible endpoints
    credentials:
      key_id: "${AWS_ACCESS_KEY_ID}"
      secret_key: "${AWS_SECRET_ACCESS_KEY}"
      session_token: "${AWS_SESSION_TOKEN}" # Optional for temporary IAM roles
```

---

## 🔷 Azure Blob Storage & ADLS Gen2

Connects to Azure Storage containers and Azure Data Lake Storage Gen2 (`abfss://`).

```yaml
connections:
  adls_gold:
    type: azure
    tier: entity
    options:
      path: "abfss://gold@analytics.dfs.core.windows.net/marts/sales.parquet"
    credentials:
      # Option 1: Connection String
      connection_string: "${AZURE_STORAGE_CONNECTION_STRING}"
      # Option 2: Service Principal / Client Credentials
      tenant_id: "${AZURE_TENANT_ID}"
      client_id: "${AZURE_CLIENT_ID}"
      client_secret: "${AZURE_CLIENT_SECRET}"
      account_name: "analytics"
```

---

## 🌈 Google Cloud Storage (GCS)

Connects to Google Cloud Storage buckets (`gs://`).

```yaml
connections:
  gcs_lake:
    type: gcs
    tier: entity
    options:
      path: "gs://company-analytics/orders.parquet"
    credentials:
      # HMAC Key Authentication
      key_id: "${GCS_HMAC_KEY_ID}"
      secret_key: "${GCS_HMAC_SECRET}"
      # Or Bearer Token
      bearer_token: "${GCP_BEARER_TOKEN}"
```

---

## 🏢 Microsoft Fabric OneLake

Connects directly to Microsoft Fabric OneLake lakehouse tables and delta folders.

```yaml
connections:
  fabric_sales:
    type: onelake
    tier: entity
    options:
      workspace: "AnalyticsWorkspace"
      lakehouse: "BronzeLakehouse"
      table: "sales_orders"
    credentials:
      tenant_id: "${AZURE_TENANT_ID}"
      client_id: "${AZURE_CLIENT_ID}"
      client_secret: "${AZURE_CLIENT_SECRET}"
```
