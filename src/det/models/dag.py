"""Topological dependency graph, cycle detection, and staged execution resolution."""

from collections import deque
from typing import Any

from det.models.base import BaseDAG, DAGStage
from det.models.definition import ModelDefinition


class ModelDAG(BaseDAG):
    """Dependency graph for models with cycle validation and staged parallel scheduling."""

    def __init__(self) -> None:
        self._models: dict[str, ModelDefinition] = {}
        self._dependencies: dict[str, set[str]] = {}  # node -> upstream providers
        self._dependents: dict[str, set[str]] = {}    # node -> downstream consumers

    def add_model(self, model: ModelDefinition) -> None:
        """Register a model and wire its dependencies into the graph."""
        self._models[model.name] = model
        if model.name not in self._dependencies:
            self._dependencies[model.name] = set()
        if model.name not in self._dependents:
            self._dependents[model.name] = set()

        for provider in model.all_dependencies:
            self.add_edge(consumer=model.name, provider=provider)

    def add_edge(self, consumer: str, provider: str) -> None:
        """Add a directed dependency edge: consumer requires provider."""
        self._dependencies.setdefault(consumer, set()).add(provider)
        self._dependents.setdefault(provider, set()).add(consumer)

    def get_model(self, name: str) -> ModelDefinition | None:
        """Retrieve a registered model definition by name."""
        return self._models.get(name)

    def detect_cycles(self) -> list[str] | None:
        """Detect circular dependencies via Depth First Search (DFS)."""
        visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        parent_path: list[str] = []

        def _dfs(node: str) -> list[str] | None:
            visited[node] = 1
            parent_path.append(node)
            for upstream in self._dependencies.get(node, set()):
                if upstream not in self._models:
                    continue  # External source, cannot form intra-model cycle
                state = visited.get(upstream, 0)
                if state == 1:
                    cycle_start = parent_path.index(upstream)
                    return parent_path[cycle_start:] + [upstream]
                if state == 0:
                    cycle = _dfs(upstream)
                    if cycle:
                        return cycle
            parent_path.pop()
            visited[node] = 2
            return None

        for node in self._models:
            if visited.get(node, 0) == 0:
                cycle = _dfs(node)
                if cycle:
                    return cycle
        return None

    def get_execution_order(self) -> list[str]:
        """Compute flat topological execution order via Kahn's algorithm."""
        cycle = self.detect_cycles()
        if cycle:
            raise RuntimeError(f"Circular dependency detected: {' -> '.join(cycle)}")

        in_degree: dict[str, int] = {
            m: sum(1 for dep in self._dependencies.get(m, set()) if dep in self._models)
            for m in self._models
        }
        queue = deque(sorted([m for m, deg in in_degree.items() if deg == 0]))
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for consumer in sorted(self._dependents.get(node, set())):
                if consumer in in_degree:
                    in_degree[consumer] -= 1
                    if in_degree[consumer] == 0:
                        queue.append(consumer)

        return order

    def get_execution_stages(self) -> list[DAGStage]:
        """Group models into sequential parallelizable execution stages."""
        order = self.get_execution_order()
        model_stage: dict[str, int] = {}

        for node in order:
            upstream_models = [
                dep for dep in self._dependencies.get(node, set()) if dep in self._models
            ]
            if not upstream_models:
                model_stage[node] = 0
            else:
                model_stage[node] = max(model_stage[dep] for dep in upstream_models) + 1

        stage_count = max(model_stage.values(), default=-1) + 1
        stages: list[DAGStage] = []
        for stage_idx in range(stage_count):
            stage_models = sorted(
                [m for m, stg in model_stage.items() if stg == stage_idx]
            )
            stages.append(DAGStage(stage_index=stage_idx, models=stage_models))

        return stages

    def select_models(self, selector: str) -> set[str]:
        """Filter models using dbt-style selectors (+model, model+, +model+)."""
        sel = selector.strip()
        include_upstream = sel.startswith("+")
        include_downstream = sel.endswith("+")
        target_name = sel.strip("+")

        if target_name not in self._models:
            raise KeyError(f"Selected model '{target_name}' not found in DAG.")

        selected: set[str] = {target_name}
        if include_upstream:
            selected.update(self._traverse_upstream(target_name))
        if include_downstream:
            selected.update(self._traverse_downstream(target_name))
        return selected

    def _traverse_upstream(self, node: str) -> set[str]:
        """Collect all recursive upstream model dependencies."""
        ancestors: set[str] = set()
        queue = deque([node])
        while queue:
            curr = queue.popleft()
            for dep in self._dependencies.get(curr, set()):
                if dep in self._models and dep not in ancestors:
                    ancestors.add(dep)
                    queue.append(dep)
        return ancestors

    def _traverse_downstream(self, node: str) -> set[str]:
        """Collect all recursive downstream dependent models."""
        descendants: set[str] = set()
        queue = deque([node])
        while queue:
            curr = queue.popleft()
            for consumer in self._dependents.get(curr, set()):
                if consumer in self._models and consumer not in descendants:
                    descendants.add(consumer)
                    queue.append(consumer)
        return descendants

