// det Web IDE - Interactive Documentation Portal & Data Dictionary Stage

async function renderDocsStage(stage) {
    if (!stage) return;
    stage.innerHTML = `<div class="docs-loading-box">Loading Data Dictionary for <strong>${state.selectedPipeline}</strong>...</div>`;
    try {
        const res = await fetch(`/api/docs/content?project=${encodeURIComponent(state.selectedPipeline)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        state.docsData = data;
        _renderDocsContent(stage, data);
    } catch (err) {
        stage.innerHTML = `<div class="explorer-empty-hint" style="color:var(--danger)">Failed to load documentation: ${err.message}</div>`;
    }
}

function _renderDocsContent(stage, data) {
    stage.innerHTML = "";
    const container = document.createElement("div");
    container.className = "docs-main-container";
    container.appendChild(_createDocsHeaderBar(data));
    container.appendChild(_createDocsKpiGrid(data));
    container.appendChild(_createDocsDagCard(data));
    container.appendChild(_createDocsModelsContainer(data));
    stage.appendChild(container);

    const canvas = document.getElementById("docs-dag-canvas");
    if (canvas && data.dag) {
        try {
            if (typeof renderDAGToContainer === "function") {
                renderDAGToContainer(canvas, data.dag, "scrollToDocModel");
            }
        } catch (dagErr) {
            console.warn("DAG render notice:", dagErr);
        }
    }
}

function _createDocsHeaderBar(data) {
    const header = document.createElement("div");
    header.className = "docs-header-bar";
    header.innerHTML = `
        <div class="docs-header-titles">
            <h2 class="docs-main-title">Data Dictionary & Pipeline Schema</h2>
            <div class="pane-subtitle">Project: <strong>${data.project_name || state.selectedPipeline}</strong> &middot; v${data.version || "0.1.0"}</div>
        </div>
        <div class="docs-header-actions">
            <button class="btn btn-secondary" onclick="exportStaticDocs()">
                ${icons.save || ""} <span>Export Static HTML Docs</span>
            </button>
        </div>
    `;
    return header;
}

function _createDocsDagCard(data) {
    const card = document.createElement("div");
    card.className = "docs-dag-card";
    const nodeCount = data.dag ? (data.dag.nodes ? data.dag.nodes.length : 0) : 0;
    card.innerHTML = `
        <div class="docs-dag-header">
            <div class="docs-dag-title">${icons.pipelines || ""} Pipeline Lineage & DAG Architecture (${nodeCount} Nodes)</div>
            <span class="pane-subtitle" style="font-size:0.75rem;">Click any model in DAG to scroll directly to its documentation</span>
        </div>
        <div class="docs-dag-canvas-wrap" id="docs-dag-canvas"></div>
    `;
    return card;
}

async function exportStaticDocs() {
    try {
        const res = await fetch("/api/docs/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline })
        });
        const out = await res.json();
        alert(out.status === "ok" ? `Docs generated successfully!\nArtifact: ${out.path}` : `Error: ${out.error || "Unknown"}`);
    } catch (e) {
        alert(`Export failed: ${e.message}`);
    }
}

function _createDocsKpiGrid(data) {
    const grid = document.createElement("div");
    grid.className = "docs-kpi-grid";
    let totalCols = 0;
    (data.models || []).forEach((m) => { totalCols += (m.columns ? m.columns.length : 0); });
    const kpis = [
        { label: "Pipeline Models", val: data.total_models || 0, icon: icons.model },
        { label: "Catalog Sources", val: data.total_sources || 0, icon: icons.database },
        { label: "Active Test Rules", val: data.total_tests || 0, icon: icons.test },
        { label: "Introspected Columns", val: totalCols, icon: icons.compile }
    ];
    grid.innerHTML = kpis.map((k) => `
        <div class="docs-kpi-card">
            <div class="docs-kpi-header"><span class="docs-kpi-icon">${k.icon || ""}</span><span class="docs-kpi-label">${k.label}</span></div>
            <div class="docs-kpi-value">${k.val}</div>
        </div>
    `).join("");
    return grid;
}

function _createDocsModelsContainer(data) {
    const list = document.createElement("div");
    list.className = "docs-models-container";
    const q = (state.docsSearchQuery || "").toLowerCase();
    const models = (data.models || []).filter((m) => {
        if (!q) return true;
        const colMatch = (m.columns || []).some((c) => c.name.toLowerCase().includes(q) || c.data_type.toLowerCase().includes(q));
        return m.name.toLowerCase().includes(q) || (m.description || "").toLowerCase().includes(q) || colMatch;
    });
    if (models.length === 0) {
        list.innerHTML = `<div class="explorer-empty-hint">No documentation records match filter "${q}"</div>`;
        return list;
    }
    models.forEach((m) => list.appendChild(renderDocModelCard(m)));
    return list;
}

function toggleDocSqlTab(modelName, tab) {
    state.docsSqlTab[modelName] = tab;
    const model = (state.docsData?.models || []).find((m) => m.name === modelName);
    if (!model) return;
    const pre = document.getElementById(`docs-sql-${modelName}`);
    if (pre) pre.innerHTML = `<code>${escapeHtml(tab === "compiled" ? model.compiled_sql : model.raw_sql)}</code>`;
    const card = document.getElementById(`doc-model-${modelName}`);
    if (card) {
        const btns = card.querySelectorAll(".tab-btn");
        if (btns.length === 2) {
            btns[0].classList.toggle("active", tab === "raw");
            btns[1].classList.toggle("active", tab === "compiled");
        }
    }
}

function copyDocSql(modelName) {
    const model = (state.docsData?.models || []).find((m) => m.name === modelName);
    if (!model) return;
    const isCompiled = state.docsSqlTab[modelName] === "compiled";
    navigator.clipboard.writeText(isCompiled ? model.compiled_sql : model.raw_sql);
}

function navToModelInEditor(project, modelName) {
    state.selectedPipeline = project;
    state.selectedModel = modelName;
    switchModule("pipelines");
}

function escapeHtml(str) {
    return (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
