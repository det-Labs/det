// det Web IDE - Main Master Coordinator

document.addEventListener("DOMContentLoaded", async () => {
    const rawHash = window.location.hash.replace("#", "");
    const [hashMod, hashQuery] = rawHash.split("?");
    const savedMod = sessionStorage.getItem("det_active_module");
    if (hashMod && ["catalog", "pipelines", "monitoring", "docs"].includes(hashMod)) {
        state.activeModule = hashMod;
    } else if (savedMod && ["catalog", "pipelines", "monitoring", "docs"].includes(savedMod)) {
        state.activeModule = savedMod;
    }
    await loadInitialData();
    if (hashQuery) {
        const params = new URLSearchParams(hashQuery);
        if (params.get("project")) {
            state.selectedPipeline = params.get("project");
            state.monitoringPipelineFilter = params.get("project");
        }
        if (params.get("model")) state.selectedModel = params.get("model");
        if (params.get("connection")) state.selectedConnection = params.get("connection");
        if (params.get("view")) state.activeMonitoringView = params.get("view");
        if (params.get("autorun") === "1" && state.selectedModel) {
            setTimeout(async () => {
                await onRunSingleModel(null, state.selectedModel);
                await testActivePipeline();
            }, 400);
        } else if (params.get("autorun") === "model" && state.selectedModel) {
            setTimeout(async () => {
                await onRunSingleModel(null, state.selectedModel);
            }, 400);
        }
    }
    renderNavigation();
    renderThemeSelector();
    if (hashQuery) {
        const params = new URLSearchParams(hashQuery);
        if (params.get("theme")) {
            applyTheme(params.get("theme"));
            const selector = document.getElementById("theme-select");
            if (selector) selector.value = params.get("theme");
        }
    }
    renderExplorer();
    renderMainStage();
    if (hashQuery) {
        const params = new URLSearchParams(hashQuery);
        if (params.get("doc_model")) {
            setTimeout(() => scrollToDocModel(params.get("doc_model"), params.get("target_sub")), 400);
        }
        if (params.get("collapse_primary") === "1") { state.explorerCollapsed = true; _updatePrimaryExplorerVisibility(); }
        if (params.get("collapse_sub") === "1") { state.subExplorerCollapsed = true; _updateSubExplorerVisibility(); }
    }
});

function isValidIdentifier(name) {
    return typeof name === "string" && /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name) && name.length <= 64;
}

function renderNavigation() {
    const navContainer = document.getElementById("nav-bar");
    if (!navContainer) return;
    navContainer.innerHTML = "";

    state.modules.forEach((mod) => {
        const btn = document.createElement("button");
        btn.className = `nav-pill ${mod.id === state.activeModule ? "active" : ""}`;
        const iconSvg = icons[mod.id] || icons.plug;
        btn.innerHTML = `${iconSvg} <span>${mod.title}</span>`;
        btn.onclick = () => switchModule(mod.id);
        navContainer.appendChild(btn);
    });

    // Demo Mode Trigger Pill beside module navigation
    const demoBtn = document.createElement("button");
    demoBtn.className = "nav-pill nav-pill-demo";
    demoBtn.id = "btn-demo-mode";
    demoBtn.title = "Explore sample datasets & interactive guided tour";
    demoBtn.innerHTML = `<span>✨</span> <span>Demo Mode</span>`;
    demoBtn.onclick = () => {
        if (typeof triggerDemoMode === "function") triggerDemoMode();
    };
    navContainer.appendChild(demoBtn);
}

function switchModule(moduleId) {
    state.activeModule = moduleId;
    sessionStorage.setItem("det_active_module", moduleId);
    window.location.hash = moduleId;
    state.searchQuery = "";
    const searchInput = document.getElementById("explorer-search");
    if (searchInput) searchInput.value = "";
    renderNavigation(); renderExplorer(); renderMainStage();
}

function renderThemeSelector() {
    const selector = document.getElementById("theme-select");
    if (!selector) return;
    selector.innerHTML = "";

    state.themes.forEach((th) => {
        const opt = document.createElement("option");
        opt.value = th.id;
        opt.textContent = th.name;
        selector.appendChild(opt);
    });
    selector.onchange = (e) => applyTheme(e.target.value);
}

function applyTheme(themeId) {
    const theme = state.themes.find((t) => t.id === themeId);
    if (!theme) return;
    const root = document.documentElement;
    Object.entries(theme.variables).forEach(([key, val]) => {
        root.style.setProperty(key, val);
    });
}

function onExplorerSearch(val) {
    state.searchQuery = (val || "").trim().toLowerCase();
    if (state.activeModule === "docs") {
        renderDocsExplorer(document.getElementById("explorer-body"));
        return;
    }
    renderExplorer();
}

function onExplorerCreateFolder() {
    if (state.activeModule === "catalog") promptCreateFolder();
    else if (state.activeModule === "pipelines") promptCreatePipelineFolder();
}

function onExplorerAdd() {
    if (state.activeModule === "catalog") openAddConnModal();
    else if (state.activeModule === "pipelines") promptCreatePipeline();
}

function togglePrimaryExplorer() {
    state.explorerCollapsed = !state.explorerCollapsed;
    _updatePrimaryExplorerVisibility();
}

function _updatePrimaryExplorerVisibility() {
    const explorerBar = document.getElementById("explorer-bar");
    const expandTab = document.getElementById("explorer-expand-tab");
    const label = document.getElementById("explorer-collapsed-label");
    if (label) {
        const mod = state.activeModule;
        label.textContent = mod === "pipelines" ? "PIPELINES" : (mod === "docs" ? "DOCS" : (mod === "monitoring" ? "MONITORING" : "CATALOG"));
    }
    if (state.explorerCollapsed) {
        if (explorerBar) explorerBar.style.display = "none";
        if (expandTab) expandTab.style.display = "flex";
    } else {
        if (explorerBar) explorerBar.style.display = "flex";
        if (expandTab) expandTab.style.display = "none";
    }
}

function _updateSubExplorerVisibility() {
    const subBar = document.getElementById("sub-explorer-bar");
    const subTab = document.getElementById("sub-explorer-expand-tab");
    const toolbar = document.getElementById("pipeline-toolbar-container");
    const btnFolder = document.getElementById("btn-sub-create-folder");
    const btnAdd = document.getElementById("btn-sub-add-model");
    const label = document.getElementById("sub-explorer-collapsed-label");
    const subTitle = document.getElementById("sub-explorer-title");
    const sBox = document.getElementById("sub-explorer-search")?.parentElement;
    const isPipelines = state.activeModule === "pipelines";
    const isDocs = state.activeModule === "docs";
    const isMonitoring = state.activeModule === "monitoring";

    if (toolbar) toolbar.style.display = isPipelines ? "block" : "none";
    if (btnFolder) btnFolder.style.display = isPipelines ? "" : "none";
    if (btnAdd) btnAdd.style.display = isPipelines ? "" : "none";
    if (sBox) sBox.style.display = isMonitoring ? "none" : "";
    if (label) label.textContent = isDocs ? "TABLES & VIEWS" : (isMonitoring ? "MONITORING" : "MODELS");
    if (subTitle) subTitle.textContent = isDocs ? "Tables & Views" : (isMonitoring ? "Monitoring Views" : "Models");

    if (isPipelines || isDocs || isMonitoring) {
        if (state.subExplorerCollapsed) {
            if (subBar) subBar.style.display = "none";
            if (subTab) subTab.style.display = "flex";
        } else {
            if (subBar) subBar.style.display = "flex";
            if (subTab) subTab.style.display = "none";
        }
        if (isDocs && typeof renderDocsSubExplorer === "function") renderDocsSubExplorer();
        else if (isPipelines && typeof renderSubExplorerModels === "function") renderSubExplorerModels();
        else if (isMonitoring && typeof renderMonitoringSubExplorer === "function") renderMonitoringSubExplorer();
    } else {
        if (subBar) subBar.style.display = "none";
        if (subTab) subTab.style.display = "none";
    }
}

function renderExplorer() {
    const titleEl = document.getElementById("explorer-title");
    const bodyEl = document.getElementById("explorer-body");
    const searchInput = document.getElementById("explorer-search");
    const btnAdd = document.getElementById("btn-explorer-add");
    const btnFolder = document.getElementById("btn-explorer-create-folder");
    const btnDocsRegen = document.getElementById("btn-explorer-docs-regenerate");
    const btnDocsDel = document.getElementById("btn-explorer-docs-delete");
    const footerEl = document.getElementById("explorer-footer");
    const isDocs = state.activeModule === "docs";
    const isMonitoring = state.activeModule === "monitoring";

    if (btnAdd) btnAdd.style.display = isDocs || isMonitoring ? "none" : "";
    if (btnFolder) btnFolder.style.display = isDocs || isMonitoring ? "none" : "";
    if (btnDocsRegen) btnDocsRegen.style.display = isDocs ? "inline-flex" : "none";
    if (btnDocsDel) btnDocsDel.style.display = isDocs ? "inline-flex" : "none";
    if (footerEl) {
        footerEl.style.display = isMonitoring ? "flex" : "none";
        if (isMonitoring && typeof renderMonitoringFooter === "function") renderMonitoringFooter(footerEl);
    }

    if (state.activeModule === "catalog") {
        if (titleEl) titleEl.textContent = "Connections";
        if (searchInput) searchInput.placeholder = "Search connections...";
        if (btnAdd) btnAdd.title = "Add Connection";
        if (btnFolder) btnFolder.title = "Create Connection Folder";
        renderCatalogConnectionsExplorer(bodyEl);
    } else if (state.activeModule === "pipelines") {
        if (titleEl) titleEl.textContent = "Pipelines / Projects";
        if (searchInput) searchInput.placeholder = "Search pipelines...";
        if (btnAdd) btnAdd.title = "Create New Pipeline";
        if (btnFolder) btnFolder.title = "Create Pipeline Folder";
        renderPipelinesExplorer(bodyEl);
    } else if (isDocs) {
        if (titleEl) titleEl.textContent = "Pipelines";
        if (searchInput) searchInput.placeholder = "Search pipelines...";
        renderDocsExplorer(bodyEl);
    } else if (isMonitoring) {
        if (titleEl) titleEl.textContent = "Pipelines";
        if (searchInput) searchInput.placeholder = "Search pipelines...";
        if (typeof renderMonitoringExplorer === "function") renderMonitoringExplorer(bodyEl);
    }
    _updatePrimaryExplorerVisibility();
    _updateSubExplorerVisibility();
}

function renderMainStage() {
    const stage = document.getElementById("main-stage");
    if (!stage) return;
    if (state.activeModule === "catalog") renderCatalogStage(stage);
    else if (state.activeModule === "pipelines") {
        renderPipelinesDAGStage(stage);
        if (state.selectedPipeline && (!state.activeDag?.nodes || !state.activeDag.nodes.length)) loadAndRenderDAG(state.selectedPipeline);
    } else if (state.activeModule === "docs") renderDocsStage(stage);
    else if (state.activeModule === "monitoring") renderMonitoringStage(stage);
}

function escapeJs(str) {
    return (str || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}
