// det Web IDE - Global Reactive State & Manifest Initialization
const state = {
    activeModule: "catalog",
    searchQuery: "",
    subExplorerSearchQuery: "",
    selectedConnection: null,
    selectedPipeline: "default",
    selectedModel: null,
    selectedModelTab: "sql",
    sqlViewMode: "raw",
    highlightedNode: null,
    explorerCollapsed: false,
    subExplorerCollapsed: false,
    modelSqlCollapsed: false,
    modelTestsCollapsed: false,
    isEditing: false,
    customFolders: new Set(),
    pipelineFolders: new Set(["Core Pipelines"]),
    docsData: null,
    docsSearchQuery: "",
    docsSqlTab: {},
    docsLineageExpanded: false,
    themes: [],
    modules: [],
    explorer: { projects: [], connections: [] },
    connectors: [],
    connections: [],
    pipelines: [],
    testResults: [],
    testsMap: {},
    activeDag: { nodes: [], edges: [] },
    activeMonitoringView: "telemetry",
    monitoringPipelineFilter: null,
    monitoringLimit: 100,
    monitoringExpandedRuns: new Set(),
    monitoringFilters: { date: "", status: "", model: "" },
};

async function loadInitialData() {
    try {
        const [manifestRes, explorerRes, statusRes, connectorsRes, connectionsRes, pipelinesRes] = await Promise.all([
            fetch("/api/ui/manifest").then((r) => r.json()),
            fetch("/api/explorer").then((r) => r.json()),
            fetch("/api/status").then((r) => r.json()),
            fetch("/api/catalog/connectors").then((r) => r.json()),
            fetch("/api/catalog/connections").then((r) => r.json()),
            fetch("/api/pipelines").then((r) => r.json()).catch(() => []),
        ]);

        state.modules = manifestRes.modules || [];
        state.themes = manifestRes.themes || [];
        state.explorer = explorerRes || { projects: [], connections: [] };
        state.connectors = connectorsRes || [];
        state.connections = connectionsRes || [];
        state.pipelines = pipelinesRes || [];

        state.customFolders = new Set(state.connections.map((c) => c.folder).filter(Boolean));
        state.pipelineFolders = new Set(state.pipelines.map((p) => p.folder || "Core Pipelines"));

        if (state.connections.length > 0 && !state.selectedConnection) {
            state.selectedConnection = state.connections[0].name;
        }
        if (state.pipelines.length > 0) {
            state.selectedPipeline = state.pipelines[0].name;
            state.selectedModel = state.pipelines[0].models?.[0]?.name || null;
        }
    } catch (err) {
        console.error("Failed to load initial IDE data:", err);
    }
}
