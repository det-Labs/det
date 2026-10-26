// det Web IDE - Interactive Monitoring & Quarantine Telemetry Dashboard

async function renderMonitoringStage(stage) {
    if (!stage) stage = document.getElementById("main-stage");
    if (!stage) return;
    stage.innerHTML = `<div class="docs-loading-box">Loading Monitoring Telemetry...</div>`;
    const view = state.activeMonitoringView || "telemetry";
    const proj = state.monitoringPipelineFilter;
    const limit = state.monitoringLimit || 100;

    const isSinks = view === "sinks";
    try {
        const [runsRes, quarRes, cfgRes] = await Promise.all([
            isSinks ? Promise.resolve({ runs: [], total: 0 }) : fetch(`/api/monitoring/runs?limit=${limit}${proj ? `&project=${encodeURIComponent(proj)}` : ""}`).then((r) => r.json()).catch(() => ({ runs: [], total: 0 })),
            isSinks ? Promise.resolve({ records: [], total: 0 }) : fetch(`/api/monitoring/quarantine?limit=100${proj ? `&project=${encodeURIComponent(proj)}` : ""}`).then((r) => r.json()).catch(() => ({ records: [], total: 0 })),
            fetch("/api/monitoring/config").then((r) => r.json()).catch(() => ({ active_sink: "duckdb", config: {} })),
        ]);

        stage.innerHTML = "";
        const container = document.createElement("div");
        container.className = "docs-main-container";
        container.appendChild(_createMonitoringHeader(cfgRes || {}, view, proj));
        if (!isSinks) {
            container.appendChild(_createMonitoringKpis(runsRes?.runs || [], quarRes?.records || []));
        }

        if (view === "telemetry") {
            container.appendChild(createRunsTableCard(runsRes?.runs || [], runsRes?.total || 0, limit));
        } else if (view === "quarantine") {
            container.appendChild(_createQuarantineCard(quarRes?.records || []));
        } else if (view === "sinks") {
            container.appendChild(_createSinkSettingsCard(cfgRes || {}));
        } else {
            container.appendChild(await _createAuditsCard(proj));
        }

        stage.appendChild(container);
    } catch (err) {
        stage.innerHTML = `
            <div class="docs-main-container">
                <div class="docs-header-bar">
                    <div class="docs-header-titles">
                        <h2 class="docs-main-title">Monitoring & Telemetry</h2>
                    </div>
                </div>
                <div class="docs-model-card" style="text-align:center; padding:2.5rem 1.5rem;">
                    <h3>Telemetry Service Ready</h3>
                    <p class="pane-subtitle">No historical runs recorded yet. Execute a pipeline or model to record telemetry.</p>
                </div>
            </div>
        `;
    }
}

function _createMonitoringHeader(cfg, view, proj) {
    const header = document.createElement("div");
    header.className = "docs-header-bar";
    const titles = {
        telemetry: "Execution Telemetry & Run History",
        quarantine: "Data Quality Quarantine Explorer",
        audits: "Assertion Evaluation Audits",
        sinks: "Extensible Telemetry Sinks Configuration",
    };
    const activeProj = proj || state.monitoringPipelineFilter || state.selectedPipeline || (state.pipelines && state.pipelines[0]?.name) || "default";
    const subtitle = view === "sinks"
        ? `Active Storage Provider: <strong style="color:var(--text); text-transform:uppercase;">${escapeHtml(cfg.active_sink || "duckdb")}</strong> &middot; Target: ${escapeHtml(cfg.config?.path || cfg.config?.url || ".det/telemetry.duckdb")}`
        : `Pipeline: <strong style="color:var(--accent);">${escapeHtml(proj || "All")}</strong> &middot; Sink: <strong style="color:var(--text); text-transform:uppercase;">${escapeHtml(cfg.active_sink || "duckdb")}</strong> &middot; Target: ${escapeHtml(cfg.config?.path || cfg.config?.url || ".det/telemetry.duckdb")}`;

    const isRunning = state.runningPipelines && state.runningPipelines.has(activeProj);
    header.innerHTML = `
        <div class="docs-header-titles">
            <h2 class="docs-main-title">${titles[view] || "Monitoring Dashboard"}</h2>
            <div class="pane-subtitle">${subtitle}</div>
        </div>
        <div class="docs-header-actions" style="display:flex; align-items:center; gap:0.4rem;">
            ${view !== "sinks" ? `
                <button class="btn btn-primary btn-sm" id="btn-mon-run-pipeline" title="Run pipeline '${escapeHtml(activeProj)}'" onclick="runPipelineFromMonitoring('${escapeJs(activeProj)}')" ${isRunning ? "disabled" : ""}>
                    ${isRunning ? icons.refresh || "" : icons.play || ""} <span>${isRunning ? "Running..." : `Run '${escapeHtml(activeProj)}'`}</span>
                </button>
            ` : ""}
            <button class="btn btn-secondary btn-sm" onclick="renderMonitoringStage(document.getElementById('main-stage'))">
                ${icons.refresh || ""} Refresh
            </button>
        </div>
    `;
    return header;
}

async function runPipelineFromMonitoring(projectName) {
    const project = projectName || state.monitoringPipelineFilter || state.selectedPipeline || "default";
    if (state.runningPipelines && state.runningPipelines.has(project)) {
        alert(`Pipeline '${project}' is already running. Please wait for the current run to finish.`);
        return;
    }
    if (!state.runningPipelines) state.runningPipelines = new Set();
    state.runningPipelines.add(project);

    const runBtn = document.getElementById("btn-mon-run-pipeline");
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = `${icons.refresh || ""} <span>Running '${escapeHtml(project)}'...</span>`;
    }

    try {
        const res = await fetch("/api/pipelines/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project }),
        });
        const rep = await res.json();
        if (rep.status === "ok") {
            await renderMonitoringStage(document.getElementById("main-stage"));
        } else {
            alert(`Pipeline run error: ${rep.error || "Execution failed"}`);
        }
    } catch (err) {
        alert(`Pipeline run request failed: ${err.message}`);
    } finally {
        if (state.runningPipelines) state.runningPipelines.delete(project);
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = `${icons.play || ""} <span>Run '${escapeHtml(project)}'</span>`;
        }
    }
}

function _createMonitoringKpis(runs, quarantine) {
    const grid = document.createElement("div");
    grid.className = "docs-kpi-grid";
    const totalRuns = runs.length;
    const rate = totalRuns > 0 ? Math.round((runs.filter((r) => r.status === "SUCCESS").length / totalRuns) * 100) : 100;
    const lastRunDur = runs.length > 0 && runs[0].duration_ms != null ? `${runs[0].duration_ms.toFixed(1)} ms` : "—";
    const pendingQuar = quarantine.filter((q) => q.status === "QUARANTINED").length;

    const kpis = [
        { label: "Total Runs", val: totalRuns, icon: icons.play },
        { label: "Success Rate", val: `${rate}%`, icon: icons.test },
        { label: "Last Run Duration", val: lastRunDur, icon: icons.compile },
        { label: "Pending Quarantine", val: pendingQuar, icon: icons.trash },
    ];
    grid.innerHTML = kpis.map((k) => `
        <div class="docs-kpi-card">
            <div class="docs-kpi-header"><span class="docs-kpi-icon">${k.icon || ""}</span><span class="docs-kpi-label">${k.label}</span></div>
            <div class="docs-kpi-value">${k.val}</div>
        </div>
    `).join("");
    return grid;
}

function _createQuarantineCard(records) {
    const card = document.createElement("div");
    card.className = "docs-model-card";
    if (records.length === 0) {
        card.innerHTML = `<div class="explorer-empty-hint">Quarantine sink is currently clean. Zero violating records found!</div>`;
        return card;
    }
    const rows = records.map((q) => `
        <tr>
            <td class="font-mono" style="font-size:0.78rem;"><strong>${escapeHtml(q.record_id)}</strong></td>
            <td><span class="badge badge-folder">${escapeHtml(q.project)}</span></td>
            <td class="font-mono" style="font-size:0.78rem;">${escapeHtml(q.model_name)}</td>
            <td class="font-mono" style="font-size:0.78rem; color:var(--danger);">${escapeHtml(q.test_name)}</td>
            <td><pre class="font-mono" style="margin:0; font-size:0.72rem; max-width:260px; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(JSON.stringify(q.raw_payload))}</pre></td>
            <td><span class="status-badge ${q.status === 'RESOLVED' ? 'badge-severity-warn' : 'badge-severity-error'}">${escapeHtml(q.status)}</span></td>
            <td>
                ${q.status !== 'RESOLVED' ? `<button class="btn btn-secondary btn-sm" onclick="resolveQuarantineRecord('${escapeJs(q.record_id)}')">Resolve</button>` : '<span class="docs-muted">Resolved</span>'}
                <button class="icon-btn icon-btn-sm text-danger" title="Purge record" onclick="purgeQuarantineRecord('${escapeJs(q.record_id)}')">${icons.trash || ""}</button>
            </td>
        </tr>
    `).join("");
    card.innerHTML = `
        <div class="docs-section-h4" style="margin-top:0;">Quarantined Records (${records.length})</div>
        <div class="docs-columns-table-wrap">
            <table class="docs-table" style="min-width:850px;">
                <thead><tr><th>RECORD ID</th><th>PROJECT</th><th>MODEL</th><th>VIOLATED ASSERTION</th><th>PAYLOAD</th><th>STATUS</th><th>ACTIONS</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
    return card;
}

function _createSinkSettingsCard(cfg) {
    const card = document.createElement("div");
    card.className = "docs-model-card";
    const cur = cfg.active_sink || "duckdb";
    card.innerHTML = `
        <div class="docs-section-h4" style="margin-top:0;">Pluggable Telemetry & Logging Storage Sink</div>
        <p class="pane-subtitle" style="margin-bottom:1rem;">Select where execution logs and quarantine records are persisted (local DuckDB, JSONL files, or external DB tables).</p>
        <div style="display:flex; flex-direction:column; gap:0.85rem; max-width:650px;">
            <label style="display:flex; align-items:flex-start; gap:0.6rem; cursor:pointer;">
                <input type="radio" name="sink-type" value="duckdb" ${cur === "duckdb" ? "checked" : ""}>
                <div><strong>DuckDB File (.det/telemetry.duckdb)</strong><div class="docs-muted" style="font-size:0.78rem;">High-performance embedded analytics database with zero external server dependencies.</div></div>
            </label>
            <label style="display:flex; align-items:flex-start; gap:0.6rem; cursor:pointer;">
                <input type="radio" name="sink-type" value="file" ${cur === "file" ? "checked" : ""}>
                <div><strong>Flat File JSONL (.det/telemetry/)</strong><div class="docs-muted" style="font-size:0.78rem;">Append-only newline-delimited JSON logs suitable for shipping to log aggregators.</div></div>
            </label>
            <label style="display:flex; align-items:flex-start; gap:0.6rem; cursor:pointer;">
                <input type="radio" name="sink-type" value="database" ${cur === "database" ? "checked" : ""}>
                <div><strong>External Database Table (SQLite / PostgreSQL / Catalog)</strong><div class="docs-muted" style="font-size:0.78rem;">Persist all run and quarantine records directly into external database audit tables.</div></div>
            </label>
            <div id="db-config-wrap" style="${cur === 'database' ? '' : 'display:none;'} margin-top:0.35rem;">
                <label style="font-size:0.75rem; font-weight:700;">Target Connection URL / Path:</label>
                <input type="text" id="target-sink-url" class="form-input" style="width:100%; margin-top:0.25rem;" value="${escapeHtml(cfg.config?.url || 'sqlite:///.det/external_audit.db')}">
            </div>
            <button class="btn btn-primary" style="align-self:flex-start; margin-top:0.35rem;" onclick="onApplySinkSwitch()">${icons.save || ""} Apply Storage Sink</button>
        </div>
    `;
    card.querySelectorAll("input[name='sink-type']").forEach((r) => r.onchange = () => {
        const wrap = document.getElementById("db-config-wrap");
        if (wrap) wrap.style.display = r.value === "database" ? "block" : "none";
    });
    return card;
}

async function _createAuditsCard(project) {
    const card = document.createElement("div");
    card.className = "docs-model-card";
    const res = await fetch(`/api/monitoring/audits?limit=100${project ? `&project=${encodeURIComponent(project)}` : ""}`).then((r) => r.json());
    const audits = res.audits || [];
    if (audits.length === 0) {
        card.innerHTML = `<div class="explorer-empty-hint">No test audits found. Run quality assertions to record audit ledger.</div>`;
        return card;
    }
    const rows = audits.map((a) => `
        <tr>
            <td class="font-mono" style="font-size:0.78rem;"><strong>${escapeHtml(a.test_name)}</strong></td>
            <td class="font-mono" style="font-size:0.78rem;">${escapeHtml(a.model_name)}</td>
            <td><span class="badge ${a.passed ? 'badge-view' : 'badge-table'}">${a.passed ? 'PASSED' : 'FAILED'}</span></td>
            <td><span class="status-badge badge-severity-${a.severity.toLowerCase()}">${escapeHtml(a.severity)}</span></td>
            <td class="font-mono">${a.failures_count}</td>
            <td style="font-size:0.78rem;">${escapeHtml(a.action_taken)}</td>
        </tr>
    `).join("");
    card.innerHTML = `
        <div class="docs-section-h4" style="margin-top:0;">Assertion Execution Audits (${audits.length})</div>
        <div class="docs-columns-table-wrap">
            <table class="docs-table" style="min-width:750px;">
                <thead><tr><th>ASSERTION</th><th>MODEL</th><th>RESULT</th><th>SEVERITY</th><th>FAILURES</th><th>ACTION TAKEN</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
    return card;
}

async function resolveQuarantineRecord(recId) {
    const notes = prompt("Enter remediation / resolution notes:", "Reviewed and verified");
    if (notes === null) return;
    try {
        const res = await fetch("/api/monitoring/quarantine/resolve", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ record_id: recId, notes }),
        });
        const data = await res.json();
        if (data.status === "ok") renderMonitoringStage(document.getElementById("main-stage"));
        else alert("Resolution failed: " + data.error);
    } catch (e) { alert("Error: " + e.message); }
}

async function purgeQuarantineRecord(recId) {
    if (!confirm(`Purge quarantine record '${recId}' permanently?`)) return;
    try {
        const res = await fetch("/api/monitoring/quarantine/purge", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ record_ids: [recId] }),
        });
        const data = await res.json();
        if (data.status === "ok") renderMonitoringStage(document.getElementById("main-stage"));
        else alert("Purge failed: " + data.error);
    } catch (e) { alert("Error: " + e.message); }
}

async function onApplySinkSwitch() {
    const selected = document.querySelector("input[name='sink-type']:checked")?.value || "duckdb";
    const cfg = {};
    if (selected === "database") {
        const urlInput = document.getElementById("target-sink-url");
        cfg.url = urlInput?.value || "sqlite:///.det/external_audit.db";
    }
    try {
        const res = await fetch("/api/monitoring/config", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sink: selected, config: cfg }),
        });
        const data = await res.json();
        if (data.status === "ok") {
            alert(`Switched monitoring storage sink to '${data.active_sink.toUpperCase()}' successfully!`);
            renderMonitoringStage(document.getElementById("main-stage"));
        } else {
            alert("Sink switch failed: " + data.error);
        }
    } catch (e) { alert("Error switching sink: " + e.message); }
}
