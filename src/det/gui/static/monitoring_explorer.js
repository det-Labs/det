// det Web IDE - Monitoring Dual Explorer & Fixed Sinks Settings Footer

function renderMonitoringExplorer(container) {
    if (!container) return;
    container.innerHTML = "";

    const wrap = document.createElement("div");
    wrap.className = "monitoring-explorer-wrap";

    if (!state.monitoringPipelineFilter && state.pipelines && state.pipelines.length > 0) {
        state.monitoringPipelineFilter = state.selectedPipeline || state.pipelines[0].name;
    }

    const q = (state.searchQuery || "").trim().toLowerCase();
    const filtered = (state.pipelines || []).filter((p) => !q || p.name.toLowerCase().includes(q));

    if (filtered.length === 0) {
        const empty = document.createElement("div");
        empty.className = "explorer-empty-hint";
        empty.style.cssText = "padding:0.75rem 1rem; font-size:0.78rem;";
        empty.textContent = "No matching pipelines";
        wrap.appendChild(empty);
    } else {
        filtered.forEach((p) => {
            const item = document.createElement("div");
            const isSel = p.name === state.monitoringPipelineFilter && state.activeMonitoringView !== "sinks";
            item.className = `explorer-item sub-item ${isSel ? "active" : ""}`;
            item.innerHTML = `<span class="item-icon">${icons.pipelines || ""}</span><span class="truncate">${escapeHtml(p.name)}</span>`;
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
    }
    container.appendChild(wrap);
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
