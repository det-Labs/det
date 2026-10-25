// det Web IDE - Monitoring Dual Explorer & Fixed Sinks Settings Footer

function renderMonitoringExplorer(container) {
    if (!container) return;
    container.innerHTML = "";

    const wrap = document.createElement("div");
    wrap.className = "monitoring-explorer-wrap";

    if (!state.monitoringPipelineFilter && state.pipelines && state.pipelines.length > 0) {
        state.monitoringPipelineFilter = state.selectedPipeline || state.pipelines[0].name;
    }

    const query = (state.searchQuery || "").trim().toLowerCase();
    const pipelines = state.pipelines || [];
    const groups = typeof groupPipelinesByFolder === "function"
        ? groupPipelinesByFolder(pipelines, query)
        : { "Pipelines": pipelines };

    let totalItems = 0;
    Object.keys(groups).sort().forEach((folderName) => {
        let items = groups[folderName] || [];
        if (query) items = items.filter((p) => p.name.toLowerCase().includes(query));
        if (folderName === "Ungrouped" && items.length === 0) return;
        totalItems += items.length;

        const header = document.createElement("div");
        header.className = "explorer-folder-header";
        header.innerHTML = `
            <span class="explorer-folder-title" title="${escapeHtml(folderName)}">${icons.folder || ""} <span>${escapeHtml(folderName)}</span></span>
            <span class="item-badge">${items.length}</span>
        `;
        wrap.appendChild(header);

        items.forEach((p) => {
            const item = document.createElement("div");
            const isSel = p.name === state.monitoringPipelineFilter && state.activeMonitoringView !== "sinks";
            item.className = `explorer-item sub-item ${isSel ? "active" : ""}`;
            item.innerHTML = `
                <span class="item-icon">${icons.pipelines || ""}</span>
                <span class="truncate" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</span>
                <span class="item-badge item-badge-hide-on-hover">${p.models_count || (p.models ? p.models.length : 0)}</span>
                <div class="explorer-item-actions">
                    <button class="icon-btn icon-btn-sm" title="Run Pipeline '${escapeJs(p.name)}'" onclick="onRunPipelineInMonitoring(event, '${escapeJs(p.name)}')">${icons.play}</button>
                </div>
            `;
            item.onclick = () => {
                state.monitoringPipelineFilter = p.name;
                state.selectedPipeline = p.name;
                if (state.activeMonitoringView === "sinks") state.activeMonitoringView = "telemetry";
                renderMonitoringExplorer(container);
                renderMonitoringFooter(document.getElementById("explorer-footer"));
                renderMonitoringSubExplorer();
                renderMonitoringStage(document.getElementById("main-stage"));
            };
            wrap.appendChild(item);
        });
    });

    if (totalItems === 0) {
        const empty = document.createElement("div");
        empty.className = "explorer-empty-hint";
        empty.style.cssText = "padding:0.75rem 1rem; font-size:0.78rem;";
        empty.textContent = "No matching pipelines";
        wrap.appendChild(empty);
    }
    container.appendChild(wrap);
}

function onRunPipelineInMonitoring(event, pipelineName) {
    if (event) event.stopPropagation();
    state.monitoringPipelineFilter = pipelineName;
    state.selectedPipeline = pipelineName;
    if (typeof runPipelineFromMonitoring === "function") {
        runPipelineFromMonitoring(pipelineName);
    }
}

function renderMonitoringFooter(container) {
    if (!container) return;
    container.innerHTML = "";
    const isSinks = state.activeMonitoringView === "sinks";

    const item = document.createElement("div");
    item.className = `explorer-item sub-item ${isSinks ? "active" : ""}`;
    item.style.cssText = "margin:0; border-radius:4px; cursor:pointer;";
    item.innerHTML = `
        <span class="item-icon">${icons.database || ""}</span>
        <span class="truncate"><strong>Storage Sinks Config</strong></span>
    `;
    item.title = "Workspace Storage & Pluggable Logging Sinks Configuration";
    item.onclick = () => selectMonitoringSinks();
    container.appendChild(item);
}

function selectMonitoringSinks() {
    state.activeMonitoringView = "sinks";
    renderMonitoringExplorer(document.getElementById("explorer-body"));
    renderMonitoringFooter(document.getElementById("explorer-footer"));
    renderMonitoringSubExplorer();
    renderMonitoringStage(document.getElementById("main-stage"));
}

function renderMonitoringSubExplorer() {
    const body = document.getElementById("sub-explorer-body");
    const countBadge = document.getElementById("sub-explorer-count");
    if (!body) return;
    body.innerHTML = "";

    const views = [
        { id: "telemetry", label: "Execution Telemetry", icon: icons.monitoring || "" },
        { id: "quarantine", label: "Quarantine Explorer", icon: icons.trash || "" },
        { id: "audits", label: "Data Quality Audits", icon: icons.test || "" },
    ];

    if (countBadge) countBadge.textContent = views.length;
    const curView = state.activeMonitoringView || "telemetry";

    const wrap = document.createElement("div");
    wrap.style.cssText = "padding:0.35rem 0;";

    views.forEach((v) => {
        const item = document.createElement("div");
        const isSel = v.id === curView;
        item.className = `explorer-item sub-item ${isSel ? "active" : ""}`;
        item.innerHTML = `
            <span class="item-icon">${v.icon}</span>
            <span class="truncate"><strong>${escapeHtml(v.label)}</strong></span>
        `;
        item.onclick = () => {
            state.activeMonitoringView = v.id;
            renderMonitoringExplorer(document.getElementById("explorer-body"));
            renderMonitoringFooter(document.getElementById("explorer-footer"));
            renderMonitoringSubExplorer();
            renderMonitoringStage(document.getElementById("main-stage"));
        };
        wrap.appendChild(item);
    });

    body.appendChild(wrap);
}
