// det Web IDE - Pipelines Stage, Command Ribbon & DAG Execution

function toggleDAGCanvasCollapse(event) {
    if (event) event.stopPropagation();
    state.dagCanvasCollapsed = !state.dagCanvasCollapsed;
    const card = document.getElementById("dag-canvas-card");
    const btn = document.getElementById("btn-dag-collapse");
    const header = document.querySelector(".dag-card-header");
    const tip = state.dagCanvasCollapsed ? "Click to expand diagram" : "Click to collapse diagram";
    if (card) {
        if (state.dagCanvasCollapsed) card.classList.add("collapsed");
        else card.classList.remove("collapsed");
    }
    if (btn) {
        btn.innerHTML = state.dagCanvasCollapsed ? icons.chevronDown : icons.chevronUp;
        btn.title = tip;
    }
    if (header) header.title = tip;
}

async function loadAndRenderDAG(projectName) {
    try {
        const res = await fetch(`/api/pipelines/dag?project=${encodeURIComponent(projectName)}`);
        state.activeDag = await res.json();
        renderDAGCanvas();
        renderPipelinesDAGStage();
    } catch (err) {
        console.error("Failed to load pipeline DAG:", err);
    }
}

function _renderCommandRibbon(pipeline) {
    return `
        <div class="dag-toolbar">
            <div class="dag-toolbar-title-group">
                <span style="font-size: 1.05rem; font-weight: 700; display:flex; align-items:center; gap:0.35rem;">
                    ${icons.pipelines} ${pipeline?.name || "Pipeline"}
                </span>
                <span class="badge badge-entity">${state.activeDag?.nodes?.length || 0} Models</span>
                <span id="pipeline-run-status" class="status-pill">● Ready</span>
            </div>
            <div class="dag-toolbar-actions">
                <button class="btn btn-secondary btn-sm" onclick="openAddModelModal()">${icons.plus} Model</button>
                <button class="btn btn-secondary btn-sm" onclick="compileActivePipeline()">${icons.compile} Compile</button>
                <button class="btn btn-secondary btn-sm" onclick="testActivePipeline()">${icons.test} Test</button>
                <button class="btn btn-secondary btn-sm" onclick="generateDocsForPipeline()">${icons.docs} Docs</button>
                <button class="btn btn-primary btn-sm" title="Run Pipeline" onclick="runActivePipeline()">${icons.play} Run</button>
                <div style="width:1px; height:18px; background:var(--border); margin:0 0.15rem;"></div>
                <button class="icon-btn icon-btn-sm" title="Fit to Canvas" onclick="fitDAGToCanvas()">${icons.fit}</button>
                <button class="icon-btn icon-btn-sm" title="Refresh Lineage" onclick="refreshPipelineLineage()">${icons.refresh}</button>
            </div>
        </div>
    `;
}

function _renderDAGCard() {
    const tip = state.dagCanvasCollapsed ? "Click to expand diagram" : "Click to collapse diagram";
    return `
        <div class="dag-canvas-card ${state.dagCanvasCollapsed ? 'collapsed' : ''}" id="dag-canvas-card">
            <div class="dag-card-header" onclick="toggleDAGCanvasCollapse()" title="${tip}">
                <div class="dag-card-title-group">
                    <span class="dag-card-title">${icons.pipelines} Dependency Graph & Lineage</span>
                    <span class="item-badge" id="dag-node-count-badge">${state.activeDag?.nodes?.length || 0} nodes</span>
                </div>
                <div style="display:flex; align-items:center;">
                    <button class="icon-btn icon-btn-sm" id="btn-dag-collapse" title="${tip}" onclick="toggleDAGCanvasCollapse(event)">
                        ${state.dagCanvasCollapsed ? icons.chevronDown : icons.chevronUp}
                    </button>
                </div>
            </div>
            <div class="dag-canvas-svg-container" id="dag-svg-container"></div>
        </div>
    `;
}

function renderPipelinesDAGStage(stage) {
    if (!stage) stage = document.getElementById("main-stage");
    if (!stage) return;
    const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline) || state.pipelines[0];
    const toolbarContainer = document.getElementById("pipeline-toolbar-container");
    if (toolbarContainer) {
        toolbarContainer.style.display = "block";
        toolbarContainer.innerHTML = _renderCommandRibbon(pipeline);
    }
    const selectedModelDef = pipeline?.models?.find((m) => m.name === state.selectedModel) || pipeline?.models?.[0];

    stage.innerHTML = `
        ${_renderDAGCard()}
        <div id="model-inspector-container">
            ${selectedModelDef ? renderModelInspector(selectedModelDef) : ""}
        </div>
    `;
    renderDAGCanvas();
}

async function runActivePipeline() {
    const statusEl = document.getElementById("pipeline-run-status");
    if (statusEl) { statusEl.textContent = "Running DAG..."; statusEl.style.color = "var(--accent)"; }
    try {
        const res = await fetch("/api/pipelines/run", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline }),
        });
        const rep = await res.json();
        if (statusEl) {
            statusEl.textContent = rep.status === "ok" ? `● Finished (${rep.duration_ms}ms, ${rep.succeeded} models)` : "✗ Run Failed";
            statusEl.style.color = rep.status === "ok" ? "var(--success)" : "#ef4444";
        }
    } catch (err) {
        if (statusEl) { statusEl.textContent = `✗ Error: ${err.message}`; statusEl.style.color = "#ef4444"; }
    }
}

async function testActivePipeline() {
    const statusEl = document.getElementById("pipeline-run-status");
    if (statusEl) { statusEl.textContent = "Running Tests..."; statusEl.style.color = "var(--accent)"; }
    try {
        const res = await fetch("/api/pipelines/test", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline }),
        });
        const rep = await res.json();
        state.testResults = rep.results || [];
        state.testsMap = {};
        state.testResults.forEach((r) => {
            if (!state.testsMap[r.model_name]) state.testsMap[r.model_name] = [];
            state.testsMap[r.model_name].push(r);
        });
        if (statusEl) {
            const ok = rep.status === "ok";
            statusEl.textContent = ok ? `✓ Tests Passed (${rep.passed}/${rep.total_tests})` : `✗ Tests Failed (${rep.failed} failed)`;
            statusEl.style.color = ok ? "var(--success)" : "#ef4444";
        }
        renderDAGCanvas();
        const inspector = document.getElementById("model-inspector-container");
        const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
        const modelDef = pipeline?.models?.find((m) => m.name === state.selectedModel);
        if (inspector && modelDef) {
            inspector.innerHTML = renderModelInspector(modelDef);
        }
    } catch (err) {
        if (statusEl) { statusEl.textContent = `✗ Error: ${err.message}`; statusEl.style.color = "#ef4444"; }
    }
}

async function generateDocsForPipeline() {
    const statusEl = document.getElementById("pipeline-run-status");
    if (statusEl) { statusEl.textContent = "Generating Docs..."; statusEl.style.color = "var(--accent)"; }
    try {
        const res = await fetch("/api/pipelines/docs", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline }),
        });
        const rep = await res.json();
        if (statusEl) {
            statusEl.textContent = rep.status === "ok" ? "✓ Docs Generated" : "✗ Docs Failed";
            statusEl.style.color = rep.status === "ok" ? "var(--success)" : "#ef4444";
        }
    } catch (err) {
        if (statusEl) { statusEl.textContent = `✗ Error: ${err.message}`; statusEl.style.color = "#ef4444"; }
    }
}

async function compileActivePipeline() {
    const statusEl = document.getElementById("pipeline-run-status");
    if (statusEl) { statusEl.textContent = "Compiling DAG..."; statusEl.style.color = "var(--accent)"; }
    try {
        const res = await fetch("/api/pipelines/compile", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline }),
        });
        const rep = await res.json();
        if (statusEl) {
            statusEl.textContent = rep.status === "ok" ? `✓ Compiled (${rep.models_count} models)` : "✗ Compile Failed";
            statusEl.style.color = rep.status === "ok" ? "var(--success)" : "#ef4444";
        }
    } catch (err) {
        if (statusEl) { statusEl.textContent = `✗ Error: ${err.message}`; statusEl.style.color = "#ef4444"; }
    }
}

function fitDAGToCanvas() {
    const container = document.getElementById("dag-svg-container");
    if (container) container.scrollTo({ top: 0, left: 0, behavior: "smooth" });
}

async function refreshPipelineLineage() {
    const statusEl = document.getElementById("pipeline-run-status");
    if (statusEl) { statusEl.textContent = "Refreshing Lineage..."; statusEl.style.color = "var(--accent)"; }
    await reloadPipelinesData();
    await loadAndRenderDAG(state.selectedPipeline);
}

async function onRunSingleModel(event, name) {
    if (event) event.stopPropagation();
    const resultBox = document.getElementById("model-run-result");
    if (resultBox) { resultBox.style.display = "block"; resultBox.className = "test-result-box"; resultBox.textContent = "Executing model..."; }
    try {
        const res = await fetch("/api/pipelines/run", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline, select: name }),
        });
        const rep = await res.json();
        if (resultBox) {
            resultBox.className = rep.status === "ok" ? "test-result-box test-result-success" : "test-result-box test-result-fail";
            const rowCount = rep.row_count ?? (rep.results && rep.results[0] ? rep.results[0].row_count : null);
            const countStr = rowCount !== null && rowCount !== undefined ? ` (${rowCount} rows)` : "";
            resultBox.textContent = rep.status === "ok" ? `✓ Model '${name}'${countStr} materialized in ${rep.duration_ms}ms` : `✗ Failed: ${rep.error || "Error"}`;
        }
    } catch (err) {
        if (resultBox) { resultBox.className = "test-result-box test-result-fail"; resultBox.textContent = `✗ Error: ${err.message}`; }
    }
}

function onRunPipeline(event, name) {
    if (event) event.stopPropagation();
    selectPipeline(name);
    runActivePipeline();
}

async function reloadPipelinesData() {
    const pipelinesRes = await fetch("/api/pipelines").then((r) => r.json()).catch(() => []);
    state.pipelines = pipelinesRes || [];
}
