// det Web IDE - Collapsible Model Inspector (SQL Editor & Data Quality Panels)

function renderModelInspector(model) {
    if (!model) return '<div class="pane-subtitle" style="padding:1.5rem; text-align:center;">No model selected.</div>';
    const tests = _getModelTests(model);
    return `
        ${_renderModelSqlCard(model)}
        ${_renderModelTestsCard(model, tests)}
    `;
}

function _renderModelSettings(model) {
    const mats = ["view", "table", "incremental", "ephemeral"];
    const opts = mats.map((m) => `<option value="${m}" ${model.materialized === m ? 'selected' : ''}>${m.toUpperCase()}</option>`).join("");
    return `
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:0.5rem; margin-bottom:0.75rem; background:var(--bg-tertiary); padding:0.5rem 0.75rem; border-radius:6px; border:1px solid var(--border);">
            <div>
                <label style="font-size:0.7rem; color:var(--text-muted); display:block; margin-bottom:2px;">Description</label>
                <input type="text" id="model-config-desc" class="form-input" style="height:26px; padding:2px 6px; font-size:0.78rem;" value="${escapeJs(model.description || '')}" placeholder="Model purpose...">
            </div>
            <div>
                <label style="font-size:0.7rem; color:var(--text-muted); display:block; margin-bottom:2px;">Materialization</label>
                <select id="model-config-mat" class="form-input" style="height:26px; padding:2px 4px; font-size:0.78rem;">${opts}</select>
            </div>
            <div>
                <label style="font-size:0.7rem; color:var(--text-muted); display:block; margin-bottom:2px;">Unique Key</label>
                <input type="text" id="model-config-key" class="form-input" style="height:26px; padding:2px 6px; font-size:0.78rem;" value="${escapeJs(model.unique_key || '')}" placeholder="Primary key column...">
            </div>
        </div>
    `;
}

function _renderModelSqlCard(model) {
    const isCol = state.modelSqlCollapsed;
    const isCompiled = state.sqlViewMode === "compiled";
    const chevronIcon = isCol ? icons.chevronDown : icons.chevronUp;
    const tip = isCol ? "Click to expand SQL editor" : "Click to collapse SQL editor";
    const sqlContent = isCompiled ? (model.compiled_sql || model.clean_sql || model.raw_sql || "") : (model.clean_sql || model.raw_sql || "");

    return `
        <div class="panel-card ${isCol ? 'collapsed' : ''}" id="model-sql-card" style="margin-top: 1rem;">
            <div class="panel-card-header" onclick="toggleModelSqlCollapse()" title="${tip}">
                <div class="panel-card-title-group">
                    <strong style="font-size:1.02rem;">${icons.model} SQL Editor: ${model.name}</strong>
                    <span class="badge badge-entity">${model.materialized}</span>
                    ${model.folder ? `<span class="badge badge-folder">${icons.folder} ${model.folder}</span>` : ""}
                </div>
                <div class="panel-card-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-sm ${!isCompiled ? 'btn-primary' : 'btn-secondary'}" onclick="switchSqlViewMode('raw')" title="Edit clean model SQL">Clean SQL</button>
                    <button class="btn btn-sm ${isCompiled ? 'btn-primary' : 'btn-secondary'}" onclick="switchSqlViewMode('compiled')" title="View compiled executable SQL">Compiled SQL</button>
                    ${!isCompiled ? `<button class="btn btn-secondary btn-sm" onclick="saveCurrentModelCode('${escapeJs(model.name)}')">${icons.save} Save</button>` : `<button class="btn btn-secondary btn-sm" onclick="copyCompiledSql()">${icons.docs} Copy</button>`}
                    <button class="btn btn-primary btn-sm" onclick="onRunSingleModel(null, '${escapeJs(model.name)}')">${icons.play} Run Model</button>
                    <button class="icon-btn icon-btn-sm" title="${tip}" onclick="toggleModelSqlCollapse(event)">${chevronIcon}</button>
                </div>
            </div>
            ${!isCol ? `
                <div class="panel-card-body" style="padding:1rem;">
                    ${!isCompiled ? _renderModelSettings(model) : `<div class="pane-subtitle" style="margin-bottom:0.6rem;">⚡ Compiled executable SQL (refs and configs resolved)</div>`}
                    <textarea id="model-inspector-sql" class="sql-textarea" ${isCompiled ? 'readonly style="min-height: 200px; width: 100%; box-sizing: border-box; background: var(--bg-tertiary); color: var(--text-muted); cursor: text;"' : 'style="min-height: 200px; width: 100%; box-sizing: border-box;"'}>${sqlContent}</textarea>
                    <div id="model-run-result" style="display:none; margin-top:0.5rem; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.8rem;"></div>
                </div>
            ` : ""}
        </div>
    `;
}

function switchSqlViewMode(mode) {
    state.sqlViewMode = mode;
    const card = document.getElementById("model-sql-card");
    if (card && state.selectedModel) {
        const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
        const model = pipeline?.models?.find((m) => m.name === state.selectedModel);
        if (model) card.outerHTML = _renderModelSqlCard(model);
    }
}

function copyCompiledSql() {
    const el = document.getElementById("model-inspector-sql");
    if (el) {
        navigator.clipboard?.writeText(el.value);
        alert("Compiled SQL copied to clipboard!");
    }
}

function _renderModelTestsCard(model, tests) {
    const isCol = state.modelTestsCollapsed;
    const chevronIcon = isCol ? icons.chevronDown : icons.chevronUp;
    const tip = isCol ? "Click to expand assertions panel" : "Click to collapse assertions panel";
    const statusSummary = _computeTestsSummary(model.name, tests);

    return `
        <div class="panel-card ${isCol ? 'collapsed' : ''}" id="model-tests-card" style="margin-top: 1rem;">
            <div class="panel-card-header" onclick="toggleModelTestsCollapse()" title="${tip}">
                <div class="panel-card-title-group">
                    <strong style="font-size:1.02rem;">${icons.test} Data Quality & Tests</strong>
                    <span class="item-badge">${tests.length} assertions</span>
                    ${statusSummary}
                </div>
                <div class="panel-card-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-secondary btn-sm" onclick="promptAddAssertion('${escapeJs(model.name)}')">+ Add Assertion</button>
                    <button class="icon-btn icon-btn-sm" title="${tip}" onclick="toggleModelTestsCollapse(event)">${chevronIcon}</button>
                </div>
            </div>
            ${!isCol ? `
                <div class="panel-card-body" style="padding:1rem;">
                    ${_renderTestsTableContent(model, tests)}
                </div>
            ` : ""}
        </div>
    `;
}

function toggleModelSqlCollapse(event) {
    if (event) event.stopPropagation();
    state.modelSqlCollapsed = !state.modelSqlCollapsed;
    _refreshModelInspector();
}

function toggleModelTestsCollapse(event) {
    if (event) event.stopPropagation();
    state.modelTestsCollapsed = !state.modelTestsCollapsed;
    _refreshModelInspector();
}

function _refreshModelInspector() {
    const inspector = document.getElementById("model-inspector-container");
    const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
    const modelDef = pipeline?.models?.find((m) => m.name === state.selectedModel);
    if (inspector && modelDef) {
        inspector.innerHTML = renderModelInspector(modelDef);
    }
}

function _computeTestsSummary(modelName, tests) {
    if (!tests.length) return '<span class="status-badge badge-untested">NO TESTS</span>';
    const nodeResults = (state.testResults || []).filter((r) => r.model_name === modelName);
    if (!nodeResults.length) return `<span class="status-badge badge-untested">${tests.length} UNTESTED</span>`;
    const failed = nodeResults.filter((r) => !r.passed).length;
    if (failed > 0) return `<span class="status-badge badge-fail">✗ ${failed} FAILED</span>`;
    return `<span class="status-badge badge-pass">✓ ${nodeResults.length}/${nodeResults.length} PASSED</span>`;
}

function _getModelTests(model) {
    const list = [];
    if (model.tests && Array.isArray(model.tests)) {
        list.push(...model.tests);
    } else if (model.raw_sql && model.raw_sql.includes("unique_key")) {
        const match = model.raw_sql.match(/unique_key\s*=\s*['"]([^'"]+)['"]/);
        if (match) {
            const key = match[1];
            list.push({ name: `${model.name}_${key}_not_null`, column: key, type: "not_null", severity: "error", origin: "inferred" });
            list.push({ name: `${model.name}_${key}_unique`, column: key, type: "unique", severity: "error", origin: "inferred" });
        }
    }
    return list;
}

function _renderTestsTableContent(model, tests) {
    if (!tests.length) {
        return `
            <div style="padding:1.5rem; text-align:center; background-color:var(--surface-card); border-radius:6px; border:1px solid var(--border);">
                <div class="pane-subtitle">No quality assertions defined or inferred for this model.</div>
                <button class="btn btn-secondary btn-sm" style="margin-top:0.75rem;" onclick="promptAddAssertion('${escapeJs(model.name)}')">+ Add Assertion</button>
            </div>
        `;
    }
    const rowsHtml = tests.map((t) => _renderTestRow(model.name, t)).join("");
    return `
        <div style="width:100%; overflow-x:auto;">
            <table class="test-assertions-table">
                <thead>
                    <tr>
                        <th style="width:105px;">STATUS</th>
                        <th>ASSERTION NAME</th>
                        <th>COLUMN</th>
                        <th>TYPE</th>
                        <th>SEVERITY</th>
                        <th>PASSED</th>
                        <th>FAILING</th>
                        <th>LATENCY</th>
                        <th>ORIGIN</th>
                    </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>
    `;
}

function _renderTestRow(modelName, t) {
    const ex = state.testResults.find((r) => r.test_name === t.name || (r.model_name === modelName && r.column_name === t.column && r.test_type === t.type));
    const passRows = ex ? (ex.passed_rows !== undefined ? ex.passed_rows : (ex.passed ? "all" : 0)) : null;
    const pill = !ex ? '<span class="status-badge badge-untested">UNTESTED</span>' : (ex.passed ? `<span class="status-badge badge-pass">✓ PASS (${passRows})</span>` : `<span class="status-badge badge-fail">✗ FAIL (${ex.failing_rows})</span>`);
    const passTxt = ex ? `${passRows} rows` : "—";
    const failTxt = ex ? (ex.passed ? "0 rows" : `${ex.failing_rows} rows`) : "—";
    const latTxt = ex ? `${ex.execution_time_ms} ms` : "—";
    const origin = t.origin === "inferred" || t.name.includes("_not_null") || t.name.includes("_unique") ? "Inferred (unique_key)" : "Custom";

    return `
        <tr>
            <td>${pill}</td>
            <td><strong style="font-family:monospace; font-size:0.8rem;">${t.name}</strong></td>
            <td><span class="badge badge-column">${t.column || '—'}</span></td>
            <td><span class="badge badge-type">${t.type || 'expression'}</span></td>
            <td><span class="badge badge-severity-${t.severity || 'error'}">${t.severity || 'error'}</span></td>
            <td><span style="font-family:monospace; font-size:0.8rem; color:#22c55e;">${passTxt}</span></td>
            <td><span style="font-family:monospace; font-size:0.8rem; color:${ex && !ex.passed ? '#ef4444' : 'inherit'};">${failTxt}</span></td>
            <td><span style="font-family:monospace; font-size:0.8rem; color:var(--muted);">${latTxt}</span></td>
            <td><span style="font-size:0.75rem; color:var(--muted);">${origin}</span></td>
        </tr>
    `;
}

async function saveCurrentModelCode(name) {
    const textarea = document.getElementById("model-inspector-sql");
    if (!textarea) return;
    const cleanSql = textarea.value;
    const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
    const model = pipeline?.models?.find((m) => m.name === name);
    const desc = document.getElementById("model-config-desc")?.value ?? (model?.description || "");
    const mat = document.getElementById("model-config-mat")?.value || model?.materialized || "table";
    const key = document.getElementById("model-config-key")?.value ?? (model?.unique_key || "");

    try {
        const res = await fetch("/api/pipelines/model/save", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project: state.selectedPipeline, name, folder: model?.folder || "",
                clean_sql: cleanSql, description: desc, materialized: mat, unique_key: key, destinations: model?.destinations || []
            }),
        });
        const rep = await res.json();
        if (rep.status === "ok") {
            if (model) { model.clean_sql = cleanSql; model.description = desc; model.materialized = mat; model.unique_key = key; }
            await reloadPipelinesData();
            await loadAndRenderDAG(state.selectedPipeline);
            alert(`Model '${name}' saved successfully!`);
        } else { alert(`Save failed: ${rep.error}`); }
    } catch (err) { alert(`Save failed: ${err.message}`); }
}

function promptAddAssertion(modelName) {
    showPromptModal({
        title: `Add Assertion for ${modelName}`, label: "Assertion Expression or Type:", defaultValue: "metric_id > 0",
        onSubmit: async (val) => alert(`Configured assertion '${val}' for model ${modelName}. Ready for pipeline validation.`),
    });
}
