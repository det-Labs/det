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
    modelSchemaCollapsed: false,
    modelTestsCollapsed: false,
    schemaViewMode: "table",
    modelSchemaCache: {},
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
    runningPipelines: new Set(),
};

async function loadInitialData() {
    try {
        const initRes = await fetch("/api/init").then((r) => r.json());
        if (initRes && initRes.modules) {
            state.workspaceRoot = initRes.workspace_root || "";
            state.modules = initRes.modules || [];
            state.themes = initRes.themes || [];
            state.explorer = initRes.explorer || { projects: [], connections: [] };
            state.connectors = initRes.connectors || [];
            state.connections = initRes.connections || [];
            state.pipelines = initRes.pipelines || [];
        } else {
            throw new Error("Invalid /api/init payload");
        }
    } catch (err) {
        console.warn("Fast /api/init unavailable, falling back to resilient loading:", err);
        try {
            const manifestRes = await fetch("/api/ui/manifest").then((r) => r.json()).catch(() => ({}));
            state.modules = manifestRes.modules || [];
            state.themes = manifestRes.themes || [];
            state.explorer = await fetch("/api/explorer").then((r) => r.json()).catch(() => ({ projects: [], connections: [] }));
            state.connectors = await fetch("/api/catalog/connectors").then((r) => r.json()).catch(() => []);
            state.connections = await fetch("/api/catalog/connections").then((r) => r.json()).catch(() => []);
            state.pipelines = await fetch("/api/pipelines").then((r) => r.json()).catch(() => []);
        } catch (fallbackErr) {
            console.error("Fallback load also failed:", fallbackErr);
        }
    }

    state.customFolders = new Set((state.connections || []).map((c) => c.folder).filter(Boolean));
    state.pipelineFolders = new Set((state.pipelines || []).map((p) => p.folder || "Core Pipelines"));

    if (state.connections && state.connections.length > 0) {
        if (!state.selectedConnection || !state.connections.some((c) => c.name === state.selectedConnection)) {
            state.selectedConnection = state.connections[0].name;
        }
    } else {
        state.selectedConnection = null;
    }

    if (state.pipelines && state.pipelines.length > 0) {
        const savedPipeline = sessionStorage.getItem("det_selected_pipeline");
        const pipeMatch = state.pipelines.find((p) => p.name === savedPipeline);
        state.selectedPipeline = pipeMatch ? savedPipeline : state.pipelines[0].name;
        const currPipe = state.pipelines.find((p) => p.name === state.selectedPipeline);
        const savedModel = sessionStorage.getItem("det_selected_model");
        const modelMatch = currPipe?.models?.find((m) => m.name === savedModel);
        state.selectedModel = modelMatch ? savedModel : (currPipe?.models?.[0]?.name || null);
    } else {
        state.selectedPipeline = null;
        state.selectedModel = null;
    }
}
