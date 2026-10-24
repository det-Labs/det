// det Web IDE - Monitoring Run History, Stage Breakdown & Run Export

let _currentRunsCache = [];

function createRunsTableCard(runs, totalCount, limit) {
    _currentRunsCache = runs || [];
    if (!state.monitoringHasInitialized) {
        state.monitoringHasInitialized = true;
        if (runs && runs.length > 0) state.monitoringExpandedRuns.add(runs[0].run_id);
    }
    const card = document.createElement("div");
    card.className = "docs-model-card";

    const filterWrap = document.createElement("div");
    filterWrap.style.cssText = "display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:0.5rem; margin-bottom:0.85rem; padding-bottom:0.75rem; border-bottom:1px solid var(--border);";
    filterWrap.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
            <span style="font-weight:700; font-size:0.8rem; color:var(--text);">${icons.pipelines || ""} Filters:</span>
            <input type="date" id="mon-filter-date" class="form-input" style="padding:0.25rem 0.5rem; font-size:0.78rem;" value="${state.monitoringFilters?.date || ''}" onchange="onMonFilterChange('date', this.value)" title="Filter by execution date">
            <select id="mon-filter-status" class="form-input" style="padding:0.25rem 0.5rem; font-size:0.78rem;" onchange="onMonFilterChange('status', this.value)">
                <option value="">All Statuses</option>
                <option value="SUCCESS" ${state.monitoringFilters?.status === 'SUCCESS' ? 'selected' : ''}>SUCCESS</option>
                <option value="FAILED" ${state.monitoringFilters?.status === 'FAILED' ? 'selected' : ''}>FAILED</option>
            </select>
            <input type="text" id="mon-filter-model" class="form-input" placeholder="Filter by model..." style="padding:0.25rem 0.5rem; font-size:0.78rem; width:150px;" value="${state.monitoringFilters?.model || ''}" oninput="onMonFilterChange('model', this.value)">
            <button class="btn btn-secondary btn-sm" onclick="onMonClearFilters()" title="Reset search filters">Reset</button>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem;">
            <span class="docs-muted" style="font-size:0.75rem;">Limit:</span>
            <select class="form-input" style="padding:0.25rem 0.5rem; font-size:0.78rem;" onchange="onMonLimitChange(this.value)">
                <option value="50" ${limit == 50 ? 'selected' : ''}>50 runs</option>
                <option value="100" ${limit == 100 ? 'selected' : ''}>100 runs</option>
                <option value="250" ${limit == 250 ? 'selected' : ''}>250 runs</option>
                <option value="500" ${limit == 500 ? 'selected' : ''}>500 runs</option>
                <option value="1000" ${limit == 1000 ? 'selected' : ''}>1,000 runs</option>
                <option value="5000" ${limit == 5000 ? 'selected' : ''}>5,000 (Max)</option>
            </select>
        </div>
    `;
    card.appendChild(filterWrap);

    const perfNotice = document.createElement("div");
    perfNotice.className = "docs-muted";
    perfNotice.style.cssText = "font-size:0.75rem; margin-bottom:0.75rem; display:flex; align-items:center; justify-content:space-between; gap:0.5rem;";
    perfNotice.innerHTML = `
        <span>⚡ <strong>Performance Guard:</strong> UI reads up to <strong>${limit || 100}</strong> runs (backend query capped at 5,000 max to keep UI responsive).</span>
        <span>Showing <strong>${runs.length}</strong> matching runs</span>
    `;
    card.appendChild(perfNotice);

    const filtered = _applyRunFilters(runs);
    if (filtered.length === 0) {
        const empty = document.createElement("div");
        empty.className = "explorer-empty-hint";
        empty.textContent = runs.length === 0 ? "No executions logged yet for this pipeline." : "No runs match the selected filters.";
        card.appendChild(empty);
        return card;
    }

    const tableWrap = document.createElement("div");
    tableWrap.className = "docs-columns-table-wrap";
    tableWrap.innerHTML = `
        <table class="docs-table" style="min-width:780px;">
            <thead><tr><th style="width:30px;"></th><th>RUN ID</th><th>STATUS</th><th>STARTED AT</th><th>DURATION</th><th>STAGES</th><th>ACTIONS</th></tr></thead>
            <tbody>${filtered.map((r) => _renderRunRowWithStages(r)).join("")}</tbody>
        </table>
    `;
    card.appendChild(tableWrap);
    return card;
}

function _applyRunFilters(runs) {
    const f = state.monitoringFilters || {};
    return runs.filter((r) => {
        if (f.date && !r.started_at?.startsWith(f.date)) return false;
        if (f.status && r.status !== f.status) return false;
        if (f.model) {
            const mQ = f.model.toLowerCase();
            const stages = r.models_detail || [];
            if (!stages.some((s) => s.model_name?.toLowerCase().includes(mQ))) return false;
        }
        return true;
    });
}

function _renderRunRowWithStages(r) {
    const isExpanded = state.monitoringExpandedRuns.has(r.run_id);
    const stages = r.models_detail || [];
    const stagesBadge = `<span class="badge badge-folder" style="cursor:pointer;" onclick="toggleRunStages('${escapeJs(r.run_id)}', event)">${stages.length || r.models_executed || 0} models</span>`;
    
    return `
        <tr style="cursor:pointer;" onclick="toggleRunStages('${escapeJs(r.run_id)}', event)">
            <td id="chevron-${escapeHtml(r.run_id)}" style="text-align:center; color:var(--muted); font-size:0.75rem;">${isExpanded ? '▼' : '▶'}</td>
            <td class="font-mono" style="font-size:0.78rem;"><strong>${escapeHtml(r.run_id)}</strong></td>
            <td><span class="status-badge ${r.status === 'SUCCESS' ? 'badge-severity-warn' : 'badge-severity-error'}">${escapeHtml(r.status)}</span></td>
            <td style="font-size:0.78rem;">${escapeHtml(r.started_at?.replace('T', ' ').slice(0, 19) || '—')}</td>
            <td class="font-mono" style="font-size:0.78rem;">${r.duration_ms.toFixed(1)}ms</td>
            <td>${stagesBadge}</td>
            <td onclick="event.stopPropagation();">
                <button class="btn btn-secondary btn-sm" onclick="exportRunTelemetry('${escapeJs(r.run_id)}')" title="Export run telemetry JSON">
                    ${icons.save || ""} Export
                </button>
            </td>
        </tr>
        <tr id="stages-row-${escapeHtml(r.run_id)}" style="background:var(--bg-card); ${isExpanded ? '' : 'display:none;'}">
            <td colspan="7" style="padding:0.75rem 1rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <div style="font-weight:700; font-size:0.78rem; color:var(--text);">${icons.pipelines || ""} Model Execution Stages Breakdown (${stages.length})</div>
                    <button class="btn btn-secondary btn-sm" style="padding:0.15rem 0.5rem; font-size:0.72rem;" onclick="toggleRunStages('${escapeJs(r.run_id)}', event)" title="Collapse model stages breakdown">▲ Collapse Stages</button>
                </div>
                ${stages.length === 0 ? '<div class="docs-muted" style="font-size:0.75rem; padding:0.5rem;">No stage breakdown recorded for this run.</div>' : `
                <table class="docs-table" style="width:100%; font-size:0.75rem; background:var(--bg-app); border:1px solid var(--border); border-radius:4px;">
                    <thead><tr style="background:var(--bg-card);"><th>#</th><th>MODEL / STAGE</th><th>STATUS</th><th>STARTED</th><th>DURATION</th><th>ROWS PROCESSED</th><th>FAILURE / DETAILS</th></tr></thead>
                    <tbody>${stages.map((s, idx) => `
                        <tr>
                            <td style="color:var(--muted); font-size:0.7rem;">${idx + 1}</td>
                            <td class="font-mono" style="font-weight:700;">${escapeHtml(s.model_name)}</td>
                            <td><span class="status-badge ${s.status === 'SUCCESS' ? 'badge-severity-warn' : 'badge-severity-error'}" style="font-size:0.68rem; padding:0.15rem 0.4rem;">${escapeHtml(s.status)}</span></td>
                            <td style="font-size:0.7rem; color:var(--muted);">${escapeHtml(s.started_at ? s.started_at.replace('T', ' ').slice(11, 19) : '—')}</td>
                            <td class="font-mono">${s.duration_ms ? s.duration_ms.toFixed(1) + 'ms' : '0.0ms'}</td>
                            <td class="font-mono" style="font-weight:600;">${(s.rows_affected || 0).toLocaleString()} rows</td>
                            <td>${s.error_message ? `<span style="color:var(--danger); font-family:monospace; font-size:0.7rem;">${escapeHtml(s.error_message)}</span>` : '<span class="docs-muted" style="font-size:0.7rem;">Success</span>'}</td>
                        </tr>
                    `).join("")}</tbody>
                </table>
                `}
            </td>
        </tr>
    `;
}

function toggleRunStages(runId, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    const row = document.getElementById(`stages-row-${runId}`);
    const chevron = document.getElementById(`chevron-${runId}`);
    if (!row) return;
    const isOpening = row.style.display === "none";
    row.style.display = isOpening ? "" : "none";
    if (chevron) chevron.textContent = isOpening ? "▼" : "▶";
    if (isOpening) state.monitoringExpandedRuns.add(runId);
    else state.monitoringExpandedRuns.delete(runId);
}

function onMonFilterChange(key, val) {
    state.monitoringFilters = state.monitoringFilters || {};
    state.monitoringFilters[key] = val;
    renderMonitoringStage(document.getElementById("main-stage"));
}

function onMonClearFilters() {
    state.monitoringFilters = { date: "", status: "", model: "" };
    renderMonitoringStage(document.getElementById("main-stage"));
}

function onMonLimitChange(val) {
    state.monitoringLimit = parseInt(val, 10) || 100;
    renderMonitoringStage(document.getElementById("main-stage"));
}

function exportRunTelemetry(runId) {
    const run = _currentRunsCache.find((r) => r.run_id === runId);
    if (!run) {
        alert(`Run ${runId} not found in current view.`);
        return;
    }
    const cleanPayload = JSON.stringify(run, null, 2);
    const blob = new Blob([cleanPayload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `det_run_${run.run_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
