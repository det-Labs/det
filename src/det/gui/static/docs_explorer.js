// det Web IDE - Docs Explorer (Pipelines & Tables/Views Sub-Explorer)

function renderDocsExplorer(container) {
    if (!container) return;
    container.innerHTML = "";
    const query = (state.searchQuery || "").toLowerCase();
    const pipelines = state.pipelines || [];
    const groups = typeof groupPipelinesByFolder === "function"
        ? groupPipelinesByFolder(pipelines, query)
        : { "Pipelines": pipelines };

    Object.keys(groups).sort().forEach((folderName) => {
        let items = groups[folderName] || [];
        if (query) items = items.filter((p) => p.name.toLowerCase().includes(query));
        if (folderName === "Ungrouped" && items.length === 0) return;

        const header = document.createElement("div");
        header.className = "explorer-folder-header";
        header.innerHTML = `
            <span class="explorer-folder-title" title="${escapeHtml(folderName)}">${icons.folder || ""} <span>${escapeHtml(folderName)}</span></span>
            <span class="item-badge">${items.length}</span>
        `;
        container.appendChild(header);
        items.forEach((p) => container.appendChild(_createDocsPipelineItem(p)));
    });
}

function _createDocsPipelineItem(p) {
    const item = document.createElement("div");
    const isSelected = p.name === state.selectedPipeline;
    item.className = `explorer-item sub-item ${isSelected ? "active" : ""}`;
    item.innerHTML = `
        <span class="item-icon">${icons.pipelines || ""}</span>
        <span class="truncate" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</span>
        <span class="item-badge item-badge-hide-on-hover">${p.models_count || (p.models ? p.models.length : 0)}</span>
        <div class="explorer-item-actions">
            <button class="icon-btn icon-btn-sm text-danger" title="Delete Pipeline" onclick="onDeletePipelineInDocs(event, '${escapeJs(p.name)}')">${icons.trash}</button>
        </div>
    `;
    item.onclick = () => selectDocsPipeline(p.name);
    return item;
}

async function onDeletePipelineInDocs(event, pipelineName) {
    if (event) event.stopPropagation();
    if (!confirm(`Are you sure you want to delete pipeline '${pipelineName}' and all its models? This action cannot be undone.`)) {
        return;
    }
    try {
        const res = await fetch("/api/pipelines/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: pipelineName }),
        });
        const rep = await res.json();
        if (rep.status === "ok") {
            if (typeof reloadPipelinesData === "function") {
                await reloadPipelinesData();
            }
            const nextPipeline = state.pipelines[0]?.name || "default";
            selectDocsPipeline(nextPipeline);
        } else {
            alert(rep.error || "Failed to delete pipeline.");
        }
    } catch (err) {
        alert("Pipeline deletion error: " + err.message);
    }
}

function selectDocsPipeline(name) {
    state.selectedPipeline = name;
    renderDocsExplorer(document.getElementById("explorer-body"));
    renderDocsSubExplorer();
    renderDocsStage(document.getElementById("main-stage"));
}

function renderDocsSubExplorer() {
    const container = document.getElementById("sub-explorer-body");
    const titleEl = document.getElementById("sub-explorer-title");
    const countEl = document.getElementById("sub-explorer-count");
    if (!container) return;

    const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline) || state.pipelines[0];
    const models = pipeline?.models || [];
    if (titleEl) {
        titleEl.textContent = "Tables & Views";
        titleEl.title = pipeline?.name ? `Pipeline: ${pipeline.name}` : "Tables & Views";
    }
    if (countEl) countEl.textContent = models.length;

    container.innerHTML = "";
    const query = (state.subExplorerSearchQuery || "").toLowerCase();
    const { groups } = typeof groupModelsByFolder === "function"
        ? groupModelsByFolder(models, query)
        : { groups: { "models": models } };

    Object.keys(groups).sort().forEach((folderName) => {
        const folderModels = groups[folderName] || [];
        if (!folderModels.length && query) return;
        const header = document.createElement("div");
        header.className = "explorer-folder-header";
        header.innerHTML = `
            <span class="explorer-folder-title" title="${escapeHtml(folderName)}">${icons.folder || ""} <span>${escapeHtml(folderName)}</span></span>
            <span class="item-badge">${folderModels.length}</span>
        `;
        container.appendChild(header);
        folderModels.forEach((m) => container.appendChild(_createDocsSubModelItem(m)));
    });
}

function _createDocsSubModelItem(m) {
    const item = document.createElement("div");
    const matClass = m.materialized === "view" ? "badge-view" : "badge-table";
    const isSelected = m.name === state.selectedModel;
    item.className = `explorer-item sub-item ${isSelected ? "active" : ""}`;
    item.id = `docs-sub-item-${m.name}`;
    item.innerHTML = `
        <span class="item-icon">${icons.model || ""}</span>
        <span class="truncate" title="${escapeHtml(m.name)}">${escapeHtml(m.name)}</span>
        <span class="badge ${matClass}" style="font-size:0.65rem; padding:1px 4px;">${(m.materialized || "table").toUpperCase()}</span>
    `;
    item.onclick = () => {
        state.selectedModel = m.name;
        const container = document.getElementById("sub-explorer-body");
        if (container) container.querySelectorAll(".explorer-item").forEach((el) => el.classList.remove("active"));
        item.classList.add("active");
        scrollToDocModel(m.name);
    };
    return item;
}

function scrollToDocModel(modelName, targetSub = null) {
    const container = document.querySelector(".docs-main-container");
    if (targetSub === "sql") {
        const sqlEl = document.getElementById(`docs-sql-${modelName}`);
        if (sqlEl && container) {
            container.scrollTop = sqlEl.parentElement.offsetTop - 60;
            return;
        }
    }
    if (targetSub === "tests") {
        const testsEl = document.getElementById(`docs-tests-${modelName}`);
        if (testsEl && container) {
            container.scrollTop = testsEl.offsetTop - 60;
            return;
        }
    }
    const target = document.getElementById(`doc-model-${modelName}`);
    if (target && container) {
        container.scrollTop = target.offsetTop - 60;
        target.classList.add("docs-card-highlight");
        setTimeout(() => target.classList.remove("docs-card-highlight"), 1600);
    }
    const subItem = document.getElementById(`docs-sub-item-${modelName}`);
    if (subItem) {
        const subContainer = document.getElementById("sub-explorer-body");
        if (subContainer) subContainer.querySelectorAll(".explorer-item").forEach((el) => el.classList.remove("active"));
        subItem.classList.add("active");
    }
}

async function onDocsRegenerate() {
    const proj = state.selectedPipeline;
    if (!proj) return;
    try {
        const res = await fetch("/api/docs/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: proj }),
        });
        const data = await res.json();
        if (data.status === "ok") {
            await renderDocsStage(document.getElementById("main-stage"));
            renderDocsSubExplorer();
            alert(`Documentation for '${proj}' regenerated successfully!\nPath: ${data.path}`);
        } else {
            alert(`Regeneration failed: ${data.error || "Unknown error"}`);
        }
    } catch (err) {
        alert(`Regeneration error: ${err.message}`);
    }
}

async function onDocsDelete() {
    const proj = state.selectedPipeline;
    if (!proj) return;
    if (!confirm(`Are you sure you want to delete generated static documentation for project '${proj}'?`)) {
        return;
    }
    try {
        const res = await fetch("/api/docs/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: proj }),
        });
        const data = await res.json();
        if (data.status === "ok") {
            alert(data.deleted ? `Generated documentation for '${proj}' was deleted.` : `No static documentation was on disk for '${proj}'.`);
            await renderDocsStage(document.getElementById("main-stage"));
        } else {
            alert(`Delete failed: ${data.error || "Unknown error"}`);
        }
    } catch (err) {
        alert(`Delete error: ${err.message}`);
    }
}

function escapeHtml(str) {
    return (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
