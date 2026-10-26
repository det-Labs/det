// det Web IDE - Interactive Documentation Portal & Data Dictionary Stage

async function renderDocsStage(stage) {
    if (!stage) stage = document.getElementById("main-stage");
    if (!stage) return;

    if (!state.pipelines || state.pipelines.length === 0) {
        stage.innerHTML = `
            <div class="docs-main-container">
                <div class="docs-model-card" style="text-align:center; padding:3rem 1.5rem;">
                    <div style="font-size:2.5rem; margin-bottom:0.75rem; opacity:0.4;">📖</div>
                    <h2>No Pipelines to Document</h2>
                    <p class="pane-subtitle">Documentation will be automatically generated once you create a pipeline.</p>
                </div>
            </div>
        `;
        return;
    }

    const targetPipeline = state.selectedPipeline || state.pipelines[0]?.name || "default";
    stage.innerHTML = `<div class="docs-loading-box">Loading Data Dictionary for <strong>${escapeHtml(targetPipeline)}</strong>...</div>`;

    try {
        const res = await fetch(`/api/docs/content?project=${encodeURIComponent(targetPipeline)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        state.docsData = data;
        _renderDocsContent(stage, data);
    } catch (err) {
        stage.innerHTML = `
            <div class="docs-main-container">
                <div class="docs-header-bar">
                    <div class="docs-header-titles">
                        <h2 class="docs-main-title">Data Dictionary & Pipeline Schema</h2>
                        <div class="pane-subtitle">Pipeline: <strong>${escapeHtml(targetPipeline)}</strong></div>
                    </div>
                    <div class="docs-header-actions">
                        <button class="btn btn-primary btn-sm" onclick="regenerateStaticDocs('${escapeJs(targetPipeline)}')">${icons.refresh || ""} Generate Docs</button>
                    </div>
                </div>
                <div class="docs-model-card" style="text-align:center; padding:2.5rem 1.5rem;">
                    <h3>Documentation Not Yet Available</h3>
                    <p class="pane-subtitle" style="margin-bottom:1rem;">Documentation has not yet been compiled for this pipeline.</p>
                    <button class="btn btn-primary" onclick="regenerateStaticDocs('${escapeJs(targetPipeline)}')">${icons.refresh || ""} Compile Documentation</button>
                </div>
            </div>
        `;
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
    const projName = data.project_name || state.selectedPipeline;
    const hasGenerated = !!data.has_generated_docs;
    header.innerHTML = `
        <div class="docs-header-titles">
            <h2 class="docs-main-title">Data Dictionary & Pipeline Schema</h2>
            <div class="pane-subtitle" style="display:flex; align-items:center; gap:0.5rem; margin-top:0.25rem;">
                <span>Project: <strong>${escapeHtml(projName)}</strong> &middot; v${data.version || "0.1.0"}</span>
                ${hasGenerated
                    ? '<span class="badge badge-success" style="font-size:0.72rem; padding:2px 8px; font-weight:600;">● HTML Docs Generated</span>'
                    : '<span class="badge badge-muted" style="font-size:0.72rem; padding:2px 8px;">No HTML Docs Generated</span>'}
            </div>
        </div>
        <div class="docs-header-actions" style="display:flex; align-items:center; gap:0.4rem;">
            ${hasGenerated ? `
                <button class="btn btn-secondary btn-sm" title="Open static HTML documentation in new tab" onclick="viewGeneratedDocs('${escapeJs(projName)}')">
                    ${icons.docs || ""} <span>View Docs</span>
                </button>
            ` : ""}
            <button class="btn btn-secondary btn-sm" id="btn-regenerate-docs" title="${hasGenerated ? 'Regenerate static HTML documentation' : 'Generate static HTML documentation'}" onclick="regenerateStaticDocs('${escapeJs(projName)}')">
                ${icons.refresh || ""} <span>${hasGenerated ? "Regenerate Docs" : "Generate Docs"}</span>
            </button>
            ${hasGenerated ? `
                <button class="btn btn-secondary btn-sm btn-danger" id="btn-delete-docs" title="Delete generated HTML documentation" onclick="deleteGeneratedDocs('${escapeJs(projName)}')">
                    ${icons.trash || ""} <span>Delete Docs</span>
                </button>
            ` : ""}
        </div>
    `;
    return header;
}

function viewGeneratedDocs(projName) {
    const project = projName || state.selectedPipeline;
    window.open(`/api/docs/view?project=${encodeURIComponent(project)}`, "_blank");
}

async function regenerateStaticDocs(projName) {
    const project = projName || state.selectedPipeline;
    const btn = document.getElementById("btn-regenerate-docs");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `${icons.refresh || ""} <span>Generating...</span>`;
    }
    try {
        const res = await fetch("/api/docs/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project })
        });
        const out = await res.json();
        if (out.status === "ok") {
            await renderDocsStage(document.getElementById("main-stage"));
        } else {
            alert(`Docs generation failed: ${out.error || "Unknown error"}`);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `${icons.refresh || ""} <span>Regenerate Docs</span>`;
            }
        }
    } catch (e) {
        alert(`Docs generation failed: ${e.message}`);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `${icons.refresh || ""} <span>Regenerate Docs</span>`;
        }
    }
}

async function deleteGeneratedDocs(projName) {
    const project = projName || state.selectedPipeline;
    if (!confirm(`Are you sure you want to delete the generated HTML documentation for project '${project}'?`)) {
        return;
    }
    const btn = document.getElementById("btn-delete-docs");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `${icons.trash || ""} <span>Deleting...</span>`;
    }
    try {
        const res = await fetch("/api/docs/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project })
        });
        const out = await res.json();
        if (out.status === "ok") {
            await renderDocsStage(document.getElementById("main-stage"));
        } else {
            alert(`Failed to delete docs: ${out.error || "Unknown error"}`);
            if (btn) btn.disabled = false;
        }
    } catch (e) {
        alert(`Delete docs error: ${e.message}`);
        if (btn) btn.disabled = false;
    }
}

async function exportStaticDocs() {
    await regenerateStaticDocs();
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
