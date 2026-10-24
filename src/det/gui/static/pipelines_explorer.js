// det Web IDE - Pipelines Explorer & Collapsible Models Sub-Sidebar

function toggleSubExplorer() {
    state.subExplorerCollapsed = !state.subExplorerCollapsed;
    const subExplorer = document.getElementById("sub-explorer-bar");
    const subStrip = document.getElementById("sub-explorer-expand-tab");
    if (state.subExplorerCollapsed) {
        if (subExplorer) subExplorer.style.display = "none";
        if (subStrip) subStrip.style.display = "flex";
    } else {
        if (subExplorer) subExplorer.style.display = "flex";
        if (subStrip) subStrip.style.display = "none";
    }
}

function onSubExplorerSearch(val) {
    state.subExplorerSearchQuery = (val || "").trim().toLowerCase();
    if (state.activeModule === "docs" && typeof renderDocsSubExplorer === "function") {
        renderDocsSubExplorer();
    } else {
        renderSubExplorerModels();
    }
}

function selectPipeline(name) {
    state.selectedPipeline = name;
    const pipeline = state.pipelines.find((p) => p.name === name);
    state.selectedModel = pipeline?.models?.[0]?.name || null;
    state.highlightedNode = null;
    renderPipelinesExplorer(document.getElementById("explorer-body"));
    renderSubExplorerModels();
    loadAndRenderDAG(name);
}

function promptCreatePipeline(folderName = "Core Pipelines") {
    showPromptModal({
        title: folderName ? `Create Pipeline in '${folderName}'` : "Create New Pipeline",
        label: "Pipeline / Project Identifier *",
        placeholder: "e.g. analytics, marketing, finance",
        submitText: "Create Pipeline",
        onConfirm: async (cleanName) => {
            try {
                const res = await fetch("/api/pipelines/create", {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name: cleanName, folder: folderName }),
                });
                const rep = await res.json();
                if (rep.status === "ok") {
                    await reloadPipelinesData();
                    selectPipeline(cleanName);
                } else {
                    alert(rep.error || "Failed to create pipeline.");
                }
            } catch (err) { alert("Pipeline creation error: " + err.message); }
        }
    });
}

function promptCreatePipelineFolder() {
    showPromptModal({
        title: "Create Pipeline Folder",
        label: "Folder Name *",
        placeholder: "e.g. Ingestion, Analytics, Nightly",
        submitText: "Create Folder",
        onConfirm: (cleanName) => {
            if (!state.pipelineFolders) state.pipelineFolders = new Set(["Core Pipelines"]);
            state.pipelineFolders.add(cleanName);
            renderPipelinesExplorer(document.getElementById("explorer-body"));
        }
    });
}

function onFolderAddPipeline(event, folderName) {
    if (event) event.stopPropagation();
    promptCreatePipeline(folderName);
}

function promptCreateModelFolder() {
    showPromptModal({
        title: `Create Schema / Folder in '${state.selectedPipeline}'`,
        label: "Schema / Directory Name *",
        placeholder: "e.g. staging, intermediate, marts, analytics",
        submitText: "Create Schema",
        onConfirm: (cleanName) => {
            if (!state.modelFolders) state.modelFolders = {};
            if (!state.modelFolders[state.selectedPipeline]) state.modelFolders[state.selectedPipeline] = new Set(["staging", "marts"]);
            state.modelFolders[state.selectedPipeline].add(cleanName);
            renderSubExplorerModels();
        }
    });
}

function onFolderAddModel(event, folderName) {
    if (event) event.stopPropagation();
    openAddModelModal(folderName);
}

function groupPipelinesByFolder(pipelines, query) {
    const allFolders = new Set(state.pipelineFolders || ["Core Pipelines"]);
    pipelines.forEach((p) => { if (p.folder) allFolders.add(p.folder); });
    const groups = {};
    allFolders.forEach((f) => { groups[f] = []; });
    groups["Ungrouped"] = [];

    pipelines.forEach((p) => {
        const folder = p.folder || "Core Pipelines";
        if (!groups[folder]) groups[folder] = [];
        groups[folder].push(p);
    });
    return groups;
}

function createPipelineItem(p) {
    const item = document.createElement("div");
    const isSelected = p.name === state.selectedPipeline;
    item.className = `explorer-item sub-item ${isSelected ? "active" : ""}`;
    item.innerHTML = `
        <span class="item-icon">${icons.pipelines}</span>
        <span class="truncate" title="${p.name}">${p.name}</span>
        <span class="item-badge item-badge-hide-on-hover">${p.models_count || p.models?.length || 0}</span>
        <div class="explorer-item-actions">
            <button class="icon-btn icon-btn-sm" title="Run Pipeline" onclick="onRunPipeline(event, '${escapeJs(p.name)}')">${icons.play}</button>
        </div>
    `;
    item.onclick = () => selectPipeline(p.name);
    return item;
}

function renderPipelinesExplorer(container) {
    if (!container) return;
    container.innerHTML = "";
    const query = state.searchQuery;
    const groups = groupPipelinesByFolder(state.pipelines, query);

    Object.keys(groups).sort().forEach((folderName) => {
        let items = groups[folderName];
        if (query) items = items.filter((p) => p.name.toLowerCase().includes(query));
        if (folderName === "Ungrouped" && items.length === 0) return;

        const header = document.createElement("div");
        header.className = "explorer-folder-header";
        header.innerHTML = `
            <span class="explorer-folder-title" title="${folderName}">${icons.folder} <span>${folderName}</span></span>
            <div class="explorer-folder-actions">
                <button class="icon-btn icon-btn-sm" title="Add pipeline to ${folderName}" onclick="onFolderAddPipeline(event, '${escapeJs(folderName)}')">${icons.plus}</button>
                <span class="item-badge">${items.length}</span>
            </div>
        `;
        container.appendChild(header);
        items.forEach((p) => container.appendChild(createPipelineItem(p)));
    });
}

function groupModelsByFolder(models, query) {
    let filtered = query ? models.filter((m) => m.name.toLowerCase().includes(query) || (m.folder && m.folder.toLowerCase().includes(query))) : models;
    const groups = {};
    const pipelineFolders = state.modelFolders?.[state.selectedPipeline] || new Set(["staging", "marts"]);
    pipelineFolders.forEach((f) => { groups[f] = []; });

    filtered.forEach((m) => {
        const folder = m.folder || "models";
        if (!groups[folder]) groups[folder] = [];
        groups[folder].push(m);
    });
    return { filtered, groups };
}

function createModelItem(m) {
    const item = document.createElement("div");
    const isSelected = m.name === state.selectedModel;
    item.className = `explorer-item sub-item ${isSelected ? "active" : ""}`;
    item.innerHTML = `
        <span class="item-icon">${icons.model}</span>
        <span class="truncate" title="${m.name}">${m.name}</span>
        <span class="item-badge item-badge-hide-on-hover">${m.materialized}</span>
        <div class="explorer-item-actions">
            <button class="icon-btn icon-btn-sm" title="Run Model" onclick="onRunSingleModel(event, '${escapeJs(m.name)}')">${icons.play}</button>
            <button class="icon-btn icon-btn-sm text-danger" title="Delete Model" onclick="onDeleteModel(event, '${escapeJs(m.name)}')">${icons.trash}</button>
        </div>
    `;
    item.onclick = () => {
        state.selectedModel = m.name;
        state.highlightedNode = m.name;
        renderSubExplorerModels();
        renderDAGCanvas();
        const insp = document.getElementById("model-inspector-container");
        if (insp) insp.innerHTML = renderModelInspector(m);
    };
    return item;
}

function renderSubExplorerModels() {
    const container = document.getElementById("sub-explorer-body");
    const titleEl = document.getElementById("sub-explorer-title");
    const countEl = document.getElementById("sub-explorer-count");
    if (!container) return;

    const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline) || state.pipelines[0];
    const models = pipeline?.models || [];
    if (titleEl) { titleEl.textContent = "Models"; titleEl.title = pipeline?.name ? `Pipeline: ${pipeline.name}` : "Models"; }
    if (countEl) countEl.textContent = models.length;

    container.innerHTML = "";
    const { filtered, groups } = groupModelsByFolder(models, state.subExplorerSearchQuery);

    Object.keys(groups).sort().forEach((folderName) => {
        const folderModels = groups[folderName];
        const header = document.createElement("div");
        header.className = "explorer-folder-header";
        header.innerHTML = `
            <span class="explorer-folder-title" title="${folderName}">${icons.folder} <span>${folderName}</span></span>
            <div class="explorer-folder-actions">
                <button class="icon-btn icon-btn-sm" title="Add model to ${folderName}" onclick="onFolderAddModel(event, '${escapeJs(folderName)}')">${icons.plus}</button>
                <span class="item-badge">${folderModels.length}</span>
            </div>
        `;
        container.appendChild(header);
        if (!folderModels.length) {
            const empty = document.createElement("div");
            empty.className = "explorer-item sub-item muted";
            empty.style.fontSize = "0.75rem";
            empty.textContent = "(Empty schema)";
            container.appendChild(empty);
        } else {
            folderModels.forEach((m) => container.appendChild(createModelItem(m)));
        }
    });
}
