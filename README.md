# det
det stands for Data Engineering Tool

A modular, Python-first data engineering framework that lets teams extract from multiple sources, transform with SQL or Polars, and publish to multiple destinations using explicit dependencies, tests, contracts, and optional portable catalog and documentation modules.

## Modules

### Catalog

The project includes an optional, Python-based YAML catalog. It allows users to register, discover, and resolve dataset names, namespaces, and schema metadata. Built with `pyyaml` and cross-platform concurrency locks via `filelock`, it avoids storing credentials and guarantees atomic updates for safe usage in batch pipelines. The catalog is designed to be accessible programmatically or eventually via a CLI and GUI interface.
