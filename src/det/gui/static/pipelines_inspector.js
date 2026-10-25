// det Web IDE - Collapsible Model Inspector (SQL Editor & Data Quality Panels)

function renderModelInspector(model) {
    if (!model) return '<div class="pane-subtitle" style="padding:1.5rem; text-align:center;">No model selected.</div>';
    const tests = _getModelTests(model);
    _ensureModelSchemaLoaded(state.selectedPipeline, model.name);
    return `
        ${_renderModelSqlCard(model)}
        ${_renderModelSchemaCard(model)}
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

function toggleModelSchemaCollapse(event) {
    if (event) event.stopPropagation();
    state.modelSchemaCollapsed = !state.modelSchemaCollapsed;
    const card = document.getElementById("model-schema-card");
    if (card && state.selectedModel) {
        const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
        const model = pipeline?.models?.find((m) => m.name === state.selectedModel);
        if (model) card.outerHTML = _renderModelSchemaCard(model);
    }
}

function switchSchemaViewMode(mode) {
    state.schemaViewMode = mode;
    const card = document.getElementById("model-schema-card");
    if (card && state.selectedModel) {
        const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
        const model = pipeline?.models?.find((m) => m.name === state.selectedModel);
        if (model) card.outerHTML = _renderModelSchemaCard(model);
    }
}

async function _ensureModelSchemaLoaded(projectName, modelName) {
    if (!state.modelSchemaCache) state.modelSchemaCache = {};
    if (state.modelSchemaCache[modelName]) return;
    try {
        const res = await fetch(`/api/pipelines/model/schema?project=${encodeURIComponent(projectName)}&model=${encodeURIComponent(modelName)}`);
        const data = await res.json();
        if (data.status === "ok") {
            state.modelSchemaCache[modelName] = data;
            const card = document.getElementById("model-schema-card");
            if (card && state.selectedModel === modelName) {
                const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
                const model = pipeline?.models?.find((m) => m.name === modelName);
                if (model) card.outerHTML = _renderModelSchemaCard(model);
            }
        }
    } catch (err) {
        console.error("Failed to load model schema:", err);
    }
}

async function refreshModelSchema(modelName) {
    if (!modelName) modelName = state.selectedModel;
    if (state.modelSchemaCache) delete state.modelSchemaCache[modelName];
    await _ensureModelSchemaLoaded(state.selectedPipeline, modelName);
}

async function saveCurrentModelSchema(modelName) {
    if (!modelName) modelName = state.selectedModel;
    const resultBox = document.getElementById("model-schema-result");
    const isYaml = state.schemaViewMode === "yaml";
    let payload = { project: state.selectedPipeline, model: modelName };

    if (isYaml) {
        const yamlArea = document.getElementById("model-inspector-yaml");
        payload.raw_yaml = yamlArea?.value || "";
    } else {
        const descEl = document.getElementById("model-config-desc");
        payload.description = descEl ? descEl.value : (state.modelSchemaCache?.[modelName]?.description || "");
        const inputs = document.querySelectorAll(".model-schema-col-input");
        payload.columns = Array.from(inputs).map((inp) => ({
            name: inp.dataset.colName,
            description: inp.value,
        }));
    }

    try {
        const res = await fetch("/api/pipelines/model/schema", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok && data.status === "ok") {
            if (!state.modelSchemaCache) state.modelSchemaCache = {};
            state.modelSchemaCache[modelName] = data;
            if (resultBox) {
                resultBox.style.display = "block";
                resultBox.style.background = "rgba(46, 160, 67, 0.15)";
                resultBox.style.border = "1px solid rgba(46, 160, 67, 0.4)";
                resultBox.style.color = "#3fb950";
                resultBox.textContent = `✓ Schema saved to ${data.schema_file || 'schema.yml'}`;
                setTimeout(() => { if (resultBox) resultBox.style.display = "none"; }, 3500);
            }
            const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
            const model = pipeline?.models?.find((m) => m.name === modelName);
            if (model && data.description) model.description = data.description;
            const card = document.getElementById("model-schema-card");
            if (card && model) card.outerHTML = _renderModelSchemaCard(model);
        } else {
            if (resultBox) {
                resultBox.style.display = "block";
                resultBox.style.background = "rgba(248, 81, 73, 0.15)";
                resultBox.style.border = "1px solid rgba(248, 81, 73, 0.4)";
                resultBox.style.color = "#f85149";
                resultBox.textContent = `✕ Error: ${data.error || 'Failed to save schema'}`;
            }
        }
    } catch (err) {
        if (resultBox) {
            resultBox.style.display = "block";
            resultBox.style.background = "rgba(248, 81, 73, 0.15)";
            resultBox.style.border = "1px solid rgba(248, 81, 73, 0.4)";
            resultBox.style.color = "#f85149";
            resultBox.textContent = `✕ Network error: ${err.message}`;
        }
    }
}

function _renderModelSchemaCard(model) {
    const isCol = state.modelSchemaCollapsed;
    const isYaml = state.schemaViewMode === "yaml";
    const chevronIcon = isCol ? icons.chevronDown : icons.chevronUp;
    const tip = isCol ? "Click to expand schema & columns panel" : "Click to collapse schema & columns panel";
    const cached = state.modelSchemaCache?.[model.name];
    const columns = cached?.columns || [];
    const rawYaml = cached?.raw_yaml || `version: 2\nmodels:\n  - name: ${model.name}\n    description: "${model.description || ''}"\n    columns: []`;
    const colCount = columns.length;

    return `
        <div class="panel-card ${isCol ? 'collapsed' : ''}" id="model-schema-card" style="margin-top: 1rem;">
            <div class="panel-card-header" onclick="toggleModelSchemaCollapse()" title="${tip}">
                <div class="panel-card-title-group">
                    <strong style="font-size:1.02rem;">${icons.docs} Schema & Columns: ${model.name}</strong>
                    <span class="item-badge" id="model-schema-count-badge">${colCount} columns</span>
                    ${cached?.schema_file ? `<span class="badge badge-folder">${icons.folder} ${cached.schema_file}</span>` : ""}
                </div>
                <div class="panel-card-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-sm ${!isYaml ? 'btn-primary' : 'btn-secondary'}" onclick="switchSchemaViewMode('table')" title="View and edit columns in table">Table View</button>
                    <button class="btn btn-sm ${isYaml ? 'btn-primary' : 'btn-secondary'}" onclick="switchSchemaViewMode('yaml')" title="View and edit raw schema.yml">Raw YAML</button>
                    <button class="btn btn-secondary btn-sm" onclick="saveCurrentModelSchema('${escapeJs(model.name)}')">${icons.save} Save Schema</button>
                    <button class="icon-btn icon-btn-sm" title="${tip}" onclick="toggleModelSchemaCollapse(event)">${chevronIcon}</button>
                </div>
            </div>
            ${!isCol ? `
                <div class="panel-card-body" style="padding:1rem;" id="model-schema-body">
                    ${!isYaml ? _renderSchemaTableView(model, columns, cached) : _renderSchemaYamlView(model, rawYaml)}
                    <div id="model-schema-result" style="display:none; margin-top:0.6rem; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.8rem;"></div>
                </div>
            ` : ""}
        </div>
    `;
}

function _renderSchemaTableView(model, columns, cached) {
    if (!cached) {
        return `<div class="pane-subtitle" style="padding:1rem; text-align:center;">Loading column schema...</div>`;
    }
    if (!columns || columns.length === 0) {
        return `
            <div style="padding: 1.5rem; text-align:center; background: var(--bg-tertiary); border-radius:6px; border:1px solid var(--border);">
                <div style="font-size: 0.9rem; font-weight:600; margin-bottom:0.4rem;">No introspected columns found</div>
                <div class="pane-subtitle" style="margin-bottom:0.8rem;">Run or compile this model to introspect output columns, or switch to <strong>Raw YAML</strong> to add them manually.</div>
                <button class="btn btn-secondary btn-sm" onclick="refreshModelSchema('${escapeJs(model.name)}')">${icons.refresh} Refresh Schema</button>
            </div>
        `;
    }
    const rows = columns.map((col) => {
        const badgesHtml = (col.test_badges || []).map((b) => `<span class="badge badge-entity" style="font-size:0.68rem; margin-right:4px;">${b}</span>`).join("");
        return `
            <tr>
                <td style="font-family:monospace; font-weight:600; color:var(--text);">${escapeJs(col.name)}</td>
                <td><span class="badge badge-type-mono">${escapeJs(col.data_type || 'ANY')}</span></td>
                <td>
                    <input type="text" class="form-input model-schema-col-input" 
                        data-col-name="${escapeJs(col.name)}" 
                        value="${escapeJs(col.description || '')}" 
                        placeholder="Add description for ${escapeJs(col.name)}..."
                        style="height:28px; font-size:0.8rem; width:100%; box-sizing:border-box;">
                </td>
                <td>${badgesHtml || '<span style="color:var(--text-muted); font-size:0.75rem;">None</span>'}</td>
            </tr>
        `;
    }).join("");

    return `
        <div style="margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
            <span class="pane-subtitle">Inline descriptions automatically sync with <code>schema.yml</code>.</span>
            <button class="btn btn-secondary btn-sm" onclick="refreshModelSchema('${escapeJs(model.name)}')">${icons.refresh} Refresh</button>
        </div>
        <div class="docs-columns-table-wrap" style="border: 1px solid var(--border); border-radius: 6px; overflow: hidden;">
            <table class="docs-table" style="margin: 0;">
                <thead>
                    <tr>
                        <th style="width: 22%;">Column</th>
                        <th style="width: 14%;">Type</th>
                        <th style="width: 44%;">Description</th>
                        <th style="width: 20%;">Tests</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    `;
}

function _renderSchemaYamlView(model, rawYaml) {
    return `
        <div style="margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
            <span class="pane-subtitle">Direct <code>schema.yml</code> configuration for <strong>${escapeJs(model.name)}</strong>.</span>
            <span class="item-badge">YAML 2.0</span>
        </div>
        <textarea id="model-inspector-yaml" class="sql-textarea yaml-textarea" 
            style="min-height: 220px; width: 100%; box-sizing: border-box; font-family: monospace; font-size: 0.82rem; line-height: 1.45; background: var(--bg-tertiary); color: var(--text);"
            placeholder="version: 2&#10;models:&#10;  - name: ${escapeJs(model.name)}&#10;    description: ...&#10;    columns: []">${rawYaml}</textarea>
    `;
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
                        <th style="width:75px; text-align:center;">ACTIONS</th>
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
    const isInferred = t.origin === "inferred" || (!t.origin && (t.name.includes("_not_null") || t.name.includes("_unique")));
    const origin = isInferred ? "Inferred (unique_key)" : "schema.yml";

    let actionsHtml = "";
    if (isInferred) {
        actionsHtml = `<span style="font-size:0.72rem; color:var(--muted); font-style:italic;" title="Derived from unique_key in model config">Locked</span>`;
    } else {
        const tName = escapeJs(t.name);
        const colName = escapeJs(t.column || "");
        const tType = escapeJs(t.type || "expression");
        const tSev = escapeJs(t.severity || "error");
        const tExpr = escapeJs(t.expression || "");
        const tVals = escapeJs(t.accepted_values || "");
        actionsHtml = `
            <div style="display:flex; justify-content:center; gap:4px;">
                <button class="icon-btn icon-btn-sm" title="Edit Assertion" onclick="openEditAssertionModal('${escapeJs(modelName)}', '${tName}', '${colName}', '${tType}', '${tSev}', '${tExpr}', '${tVals}')">${icons.edit || '✎'}</button>
                <button class="icon-btn icon-btn-sm text-danger" title="Delete Assertion" onclick="onDeleteAssertion('${escapeJs(modelName)}', '${tName}', '${colName}', '${tType}')">${icons.trash || '🗑'}</button>
            </div>
        `;
    }

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
            <td style="text-align:center;">${actionsHtml}</td>
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
    openAddAssertionModal(modelName);
}

function openAddAssertionModal(modelName) {
    _renderAssertionModal({
        modelName,
        isEdit: false,
        oldTestName: null,
        defaultColumn: "",
        defaultType: "expression",
        defaultExpression: "",
        defaultSeverity: "error",
    });
}

function openEditAssertionModal(modelName, testName, columnName, testType, severity, expression = "", acceptedValues = "") {
    _renderAssertionModal({
        modelName,
        isEdit: true,
        oldTestName: testName,
        defaultColumn: columnName,
        defaultType: testType,
        defaultExpression: expression || acceptedValues || "",
        defaultSeverity: severity,
    });
}

function _renderAssertionModal(cfg) {
    const existing = document.getElementById("assertion-form-modal");
    if (existing) existing.remove();

    const cachedCols = state.modelSchemaCache?.[cfg.modelName]?.columns || [];
    const colOptions = cachedCols.length > 0 
        ? cachedCols.map((c) => `<option value="${escapeJs(c.name)}" ${c.name === cfg.defaultColumn ? 'selected' : ''}>${escapeHtml(c.name)} (${c.data_type || 'ANY'})</option>`).join("")
        : `<option value="${escapeJs(cfg.defaultColumn || 'id')}">${escapeHtml(cfg.defaultColumn || 'id')}</option>`;

    const modal = document.createElement("div");
    modal.id = "assertion-form-modal";
    modal.className = "modal-overlay";
    modal.style.display = "flex";
    modal.innerHTML = `
        <div class="modal-card" style="max-width: 520px; width: 90%;">
            <div class="modal-header">
                <h3>${cfg.isEdit ? 'Edit Quality Assertion' : 'Add Quality Assertion'}</h3>
                <button class="icon-btn" onclick="document.getElementById('assertion-form-modal').remove()">${icons.close || '✕'}</button>
            </div>
            <div class="modal-body" style="display:flex; flex-direction:column; gap:0.9rem;">
                <div class="form-group">
                    <label class="form-label">Target Column *</label>
                    <select id="assertion-col-select" class="form-input">
                        ${colOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Assertion Type *</label>
                    <select id="assertion-type-select" class="form-input" onchange="_onAssertionTypeChange(this.value)">
                        <option value="expression" ${cfg.defaultType === 'expression' ? 'selected' : ''}>Custom Expression (SQL boolean)</option>
                        <option value="not_null" ${cfg.defaultType === 'not_null' ? 'selected' : ''}>Not Null (Column cannot be NULL)</option>
                        <option value="unique" ${cfg.defaultType === 'unique' ? 'selected' : ''}>Unique (Values must be distinct)</option>
                        <option value="accepted_values" ${cfg.defaultType === 'accepted_values' ? 'selected' : ''}>Accepted Values (Allowed list)</option>
                    </select>
                </div>
                <div class="form-group" id="assertion-val-group">
                    <label class="form-label" id="assertion-val-label">SQL Expression Condition *</label>
                    <input type="text" id="assertion-val-input" class="form-input" placeholder="e.g. quantity > 0 AND unit_price >= 0" value="${escapeJs(cfg.defaultExpression)}">
                    <span class="pane-subtitle" id="assertion-val-hint" style="margin-top:0.25rem;">Boolean SQL predicate that must evaluate to TRUE for every row.</span>
                </div>
                <div class="form-group">
                    <label class="form-label">Severity Level</label>
                    <select id="assertion-severity-select" class="form-input">
                        <option value="error" ${cfg.defaultSeverity === 'error' ? 'selected' : ''}>Error (Halts pipeline execution / Quarantines rows)</option>
                        <option value="warn" ${cfg.defaultSeverity === 'warn' ? 'selected' : ''}>Warning (Logs audit entry without halting)</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer" style="display:flex; justify-content:flex-end; gap:0.5rem; margin-top:1rem;">
                <button class="btn btn-secondary" onclick="document.getElementById('assertion-form-modal').remove()">Cancel</button>
                <button class="btn btn-primary" id="btn-save-assertion-confirm" onclick="_submitAssertionForm('${escapeJs(cfg.modelName)}', ${cfg.isEdit ? `'${escapeJs(cfg.oldTestName || '')}'` : 'null'})">${cfg.isEdit ? 'Update Assertion' : 'Add Assertion'}</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    _onAssertionTypeChange(cfg.defaultType);
}

function _onAssertionTypeChange(type) {
    const valGroup = document.getElementById("assertion-val-group");
    const valLabel = document.getElementById("assertion-val-label");
    const valInput = document.getElementById("assertion-val-input");
    const valHint = document.getElementById("assertion-val-hint");
    if (!valGroup) return;

    if (type === "not_null" || type === "unique") {
        valGroup.style.display = "none";
    } else if (type === "accepted_values") {
        valGroup.style.display = "flex";
        if (valLabel) valLabel.textContent = "Accepted Values (Comma-separated) *";
        if (valInput) valInput.placeholder = "e.g. 'VIP', 'GOLD', 'SILVER'";
        if (valHint) valHint.textContent = "List of allowed categorical string or numeric values.";
    } else {
        valGroup.style.display = "flex";
        if (valLabel) valLabel.textContent = "SQL Expression Condition *";
        if (valInput) valInput.placeholder = "e.g. quantity > 0";
        if (valHint) valHint.textContent = "Boolean SQL predicate that must evaluate to TRUE for every row.";
    }
}

async function _submitAssertionForm(modelName, oldTestName) {
    const col = document.getElementById("assertion-col-select")?.value;
    const type = document.getElementById("assertion-type-select")?.value || "expression";
    const val = document.getElementById("assertion-val-input")?.value || "";
    const sev = document.getElementById("assertion-severity-select")?.value || "error";

    if (!col) { alert("Please select a target column."); return; }
    if (type === "expression" && !val.trim()) { alert("Please provide a SQL expression condition."); return; }
    if (type === "accepted_values" && !val.trim()) { alert("Please provide comma-separated accepted values."); return; }

    const payload = {
        project: state.selectedPipeline,
        model: modelName,
        column: col,
        type: type,
        expression: type === "expression" ? val.trim() : "",
        accepted_values: type === "accepted_values" ? val.trim() : "",
        severity: sev,
        old_test_name: oldTestName || null,
    };

    try {
        const res = await fetch("/api/pipelines/model/assertion/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const rep = await res.json();
        if (rep.status === "ok") {
            document.getElementById("assertion-form-modal")?.remove();
            await reloadPipelinesData();
            if (typeof refreshModelSchema === "function") {
                await refreshModelSchema(modelName);
            }
            _refreshModelInspector();
        } else {
            alert(rep.error || "Failed to save assertion.");
        }
    } catch (err) {
        alert("Error saving assertion: " + err.message);
    }
}

async function onDeleteAssertion(modelName, testName, columnName, testType) {
    if (!confirm(`Are you sure you want to delete assertion '${testName}' from schema.yml?`)) {
        return;
    }
    try {
        const res = await fetch("/api/pipelines/model/assertion/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project: state.selectedPipeline,
                model: modelName,
                column: columnName,
                test_name: testName,
                type: testType,
            }),
        });
        const rep = await res.json();
        if (rep.status === "ok") {
            await reloadPipelinesData();
            if (typeof refreshModelSchema === "function") {
                await refreshModelSchema(modelName);
            }
            _refreshModelInspector();
        } else {
            alert(rep.error || "Failed to delete assertion.");
        }
    } catch (err) {
        alert("Error deleting assertion: " + err.message);
    }
}
