"""det: Data Engineering Tool (DuckDB 2.0 Edition)."""

from det.config import WorkspaceConfig
from det.runner import PipelineExecutionReport, PipelineRunner
from det.workspace import Workspace

__version__ = "0.3.0"

__all__ = [
    "PipelineExecutionReport",
    "PipelineRunner",
    "Workspace",
    "WorkspaceConfig",
]

