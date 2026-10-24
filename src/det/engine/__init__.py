"""Engine package exposing the public interface for the DuckDB analytical subsystem."""

from det.engine.base import (
    BaseDispatcher,
    BaseMounter,
    BaseSecretResolver,
    BaseSessionManager,
    EngineConfig,
    MountReport,
    Mountable,
    QueryResult,
)
from det.engine.dispatcher import QueryDispatcher
from det.engine.facade import EngineFacade
from det.engine.mounter import CatalogMounter
from det.engine.secrets import SecretResolver
from det.engine.session import DuckDBSessionManager

__all__ = [
    "BaseDispatcher",
    "BaseMounter",
    "BaseSecretResolver",
    "BaseSessionManager",
    "CatalogMounter",
    "DuckDBSessionManager",
    "EngineConfig",
    "EngineFacade",
    "MountReport",
    "Mountable",
    "QueryDispatcher",
    "QueryResult",
    "SecretResolver",
]

