// det Web IDE - Documentation Model Card Renderer

function renderDocModelCard(model) {
    const card = document.createElement("div");
    card.className = "docs-model-card";
    card.id = `doc-model-${model.name}`;

    card.appendChild(_renderModelHeader(model));
    card.appendChild(_renderModelSourcesTable(model.sources_detail || []));
    card.appendChild(_renderModelDestinationsTable(model.destinations_detail || []));
    card.appendChild(_renderModelColumnsTable(model.columns || [], model));
    card.appendChild(_renderModelTestsTable(model.tests_detail || [], model));
    card.appendChild(_renderModelSqlViewer(model));

    return card;
}

function _renderModelHeader(model) {
    const hdr = document.createElement("div");
    hdr.className = "docs-model-header";
    const matClass = model.materialization === "view" ? "badge-view" : "badge-table";
    const desc = model.description ? `<p class="docs-model-desc">${escapeHtml(model.description)}</p>` : `<p class="docs-model-desc docs-muted">No description provided for this model.</p>`;

    hdr.innerHTML = `
        <div style="width:100%;">
            <div class="docs-model-title-row" style="justify-content:space-between; margin-bottom:0.5rem;">
                <div style="display:flex; align-items:center; gap:0.6rem;">
                    <span class="docs-model-name">${model.name}</span>
                    <span class="badge ${matClass}">${(model.materialization || "table").toUpperCase()}</span>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="navToModelInEditor('${escapeJs(model.project)}', '${escapeJs(model.name)}')">
                    ${icons.edit || ""} Edit in Pipelines
                </button>
            </div>
            ${desc}
        </div>
    `;
    return hdr;
}

function _renderModelSourcesTable(sources) {
    const wrap = document.createElement("div");
    wrap.className = "docs-sources-table-wrap";
    if (!sources || sources.length === 0) return wrap;

    const rows = sources.map((s) => `
        <tr>
            <td class="font-mono"><strong>${escapeHtml(s.name)}</strong></td>
            <td><span class="badge badge-folder">${escapeHtml((s.tier || "entity").toUpperCase())}</span></td>
            <td><span class="badge-type-mono">${escapeHtml((s.connector_type || "csv").toUpperCase())}</span></td>
            <td class="font-mono" style="color:var(--accent); font-size:0.78rem;">${escapeHtml(s.path || "(direct view)")}</td>
            <td class="docs-muted" style="font-size:0.78rem;">${escapeHtml(s.description || "—")}</td>
        </tr>
    `).join("");

    wrap.innerHTML = `
        <div class="docs-section-h4">Ingestion Sources (${sources.length})</div>
        <div class="docs-columns-table-wrap">
            <table class="docs-table" style="min-width:720px;">
                <thead><tr><th style="min-width:140px;">SOURCE</th><th style="min-width:90px;">TIER</th><th style="min-width:100px;">CONNECTOR</th><th style="min-width:210px;">LOCATION / FILE PATH</th><th style="min-width:180px;">DESCRIPTION</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
    return wrap;
}

function _renderModelDestinationsTable(dests) {
    const wrap = document.createElement("div");
    wrap.className = "docs-dests-table-wrap";
    if (!dests || dests.length === 0) return wrap;

    const rows = dests.map((d) => `
        <tr>
            <td><span class="badge badge-dest">${escapeHtml((d.target || "csv").toUpperCase())}</span></td>
            <td class="font-mono" style="font-size:0.78rem;"><strong>${escapeHtml(d.path)}</strong></td>
            <td class="font-mono docs-muted" style="font-size:0.78rem;">${escapeHtml(JSON.stringify(d.options || {}))}</td>
        </tr>
    `).join("");

    wrap.innerHTML = `
        <div class="docs-section-h4">Export Destinations (${dests.length})</div>
        <div class="docs-columns-table-wrap">
            <table class="docs-table" style="min-width:560px;">
                <thead><tr><th style="min-width:120px;">TARGET FORMAT</th><th style="min-width:260px;">PHYSICAL DESTINATION</th><th style="min-width:180px;">OPTIONS</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
    return wrap;
}

function _renderModelColumnsTable(columns, model) {
    const wrap = document.createElement("div");
    wrap.className = "docs-columns-table-wrap";
    if (!columns || columns.length === 0) return wrap;

    const rows = columns.map((c) => {
        const badges = (c.test_badges || []).map((b) => `<span class="badge badge-test">${escapeHtml(b)}</span>`).join(" ");
        const descClass = c.description ? "" : "docs-muted";
        return `
            <tr>
                <td class="col-name font-mono"><strong>${escapeHtml(c.name)}</strong></td>
                <td class="col-type"><span class="badge-type-mono">${escapeHtml(c.data_type || "VARCHAR")}</span></td>
                <td class="col-tests">${badges || '<span class="docs-muted">—</span>'}</td>
                <td class="col-desc">
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
                        <span class="${descClass}" id="desc-val-${model?.name}-${c.name}">${escapeHtml(c.description || "Undocumented")}</span>
                        <button class="icon-btn icon-btn-sm" title="Edit column description" onclick="promptEditColumnDesc('${escapeJs(model?.project || state.selectedPipeline)}', '${escapeJs(model?.name)}', '${escapeJs(c.name)}')">
                            ${icons.edit || ""}
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");

    wrap.innerHTML = `
        <div class="docs-section-h4" style="margin-top:0;">Column Schema (${columns.length})</div>
        <div class="docs-columns-table-wrap">
            <table class="docs-table" style="min-width:650px;">
                <thead><tr><th style="min-width:160px;">COLUMN</th><th style="min-width:120px;">DATA TYPE</th><th style="min-width:180px;">ASSERTIONS</th><th style="min-width:190px;">DESCRIPTION</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
    return wrap;
}

function promptEditColumnDesc(project, model, column) {
    const curEl = document.getElementById(`desc-val-${model}-${column}`);
    const curVal = curEl && !curEl.classList.contains("docs-muted") ? curEl.textContent : "";
    showPromptModal({
        title: `Edit Description: ${model}.${column}`,
        label: `Description for column '${column}' *`,
        placeholder: "e.g. Unique identifier for customer account",
        defaultValue: curVal,
        submitText: "Save Description",
        onConfirm: async (newDesc) => {
            try {
                const res = await fetch("/api/docs/column/description", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ project, model, column, description: newDesc }),
                });
                const data = await res.json();
                if (data.status === "ok") {
                    if (curEl) {
                        curEl.textContent = newDesc || "Undocumented";
                        curEl.classList.toggle("docs-muted", !newDesc);
                    }
                    const mObj = (state.docsData?.models || []).find((m) => m.name === model);
                    const cObj = mObj?.columns?.find((c) => c.name === column);
                    if (cObj) cObj.description = newDesc;
                } else {
                    alert(`Failed to save description: ${data.error || "Unknown"}`);
                }
            } catch (err) {
                alert(`Error saving description: ${err.message}`);
            }
        }
    });
}

function _renderModelTestsTable(tests, model = null) {
    const wrap = document.createElement("div");
    wrap.className = "docs-tests-table-wrap";
    if (model && model.name) {
        wrap.id = `docs-tests-${model.name}`;
    }
    if (!tests || tests.length === 0) return wrap;

    const rows = tests.map((t) => {
        const sevClass = `badge-severity-${(t.severity || "error").toLowerCase()}`;
        return `
            <tr>
                <td class="font-mono" style="font-size:0.78rem; min-width:250px;"><strong>${escapeHtml(t.name)}</strong></td>
                <td class="font-mono" style="font-size:0.78rem; min-width:120px;">${escapeHtml(t.column || "model")}</td>
                <td style="font-size:0.78rem; min-width:170px;">${escapeHtml(t.details || t.test_type)}</td>
                <td style="min-width:90px;"><span class="status-badge ${sevClass}">${escapeHtml(t.severity)}</span></td>
                <td class="docs-action-failure" style="min-width:240px;">${escapeHtml(t.action_on_failure)}</td>
            </tr>
        `;
    }).join("");

    wrap.innerHTML = `
        <div class="docs-section-h4">Quality Contracts & Failure Behavior (${tests.length})</div>
        <div class="docs-columns-table-wrap">
            <table class="docs-table" style="min-width:870px;">
                <thead><tr><th style="min-width:250px;">ASSERTION NAME</th><th style="min-width:120px;">COLUMN</th><th style="min-width:170px;">RULE / CONDITION</th><th style="min-width:90px;">SEVERITY</th><th style="min-width:240px;">ACTION ON FAILURE</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
    return wrap;
}

function _renderModelSqlViewer(model) {
    const wrap = document.createElement("div");
    wrap.className = "docs-sql-preview-wrap";
    const isCompiled = state.docsSqlTab[model.name] === "compiled";
    const sqlText = isCompiled ? (model.compiled_sql || "") : (model.raw_sql || "");

    wrap.innerHTML = `
        <div class="docs-sql-header">
            <div class="tab-group">
                <button class="tab-btn ${!isCompiled ? "active" : ""}" onclick="toggleDocSqlTab('${escapeJs(model.name)}', 'raw')">Raw SQL</button>
                <button class="tab-btn ${isCompiled ? "active" : ""}" onclick="toggleDocSqlTab('${escapeJs(model.name)}', 'compiled')">Compiled SQL</button>
            </div>
            <button class="icon-btn" title="Copy SQL" onclick="copyDocSql('${escapeJs(model.name)}')">${icons.save || ""} Copy</button>
        </div>
        <pre class="docs-sql-code font-mono" id="docs-sql-${model.name}"><code>${escapeHtml(sqlText)}</code></pre>
    `;
    return wrap;
}
