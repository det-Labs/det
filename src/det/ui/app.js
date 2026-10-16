const moduleContent = {
  Catalog: {
    explorer: "Catalog items and connections will appear here.",
    description: "Browse YAML catalogs and manage source and destination connections.",
  },
  ETL: {
    explorer: "Pipeline folders and SQL stages will appear here.",
    description: "Build multi-stage SQL pipelines powered by Apache DataFusion.",
  },
  Monitoring: {
    explorer: "Pipeline runs and health views will appear here.",
    description: "Follow pipeline activity, execution status, and workspace health.",
  },
  Documentation: {
    explorer: "Workspace guides and notes will appear here.",
    description: "Keep data definitions and project documentation close to your work.",
  },
  Help: {
    explorer: "Guides and support resources will appear here.",
    description: "Find help for your workspace, extensions, and SQL pipelines.",
  },
};

const moduleTabs = [...document.querySelectorAll(".module-tab")];
const themeToggle = document.querySelector("#theme-toggle");
const explorerTitle = document.querySelector("#explorer-title");
const explorerMessage = document.querySelector("#explorer-message");
const breadcrumbModule = document.querySelector("#breadcrumb-module");
const moduleTitle = document.querySelector("#module-title");
const moduleDescription = document.querySelector("#module-description");
const themeRoot = document.documentElement;
const catalogExplorer = document.querySelector("#catalog-explorer");
const genericExplorer = document.querySelector("#generic-explorer");
const genericModuleContent = document.querySelector("#generic-module-content");
const catalogModule = document.querySelector("#catalog-module");
const catalogTree = document.querySelector("#catalog-tree");
const catalogSearch = document.querySelector("#catalog-search");
const catalogSummary = document.querySelector("#catalog-summary");
const catalogDetail = document.querySelector("#catalog-detail");
const catalogHeading = document.querySelector("#catalog-heading");
const catalogSubtitle = document.querySelector("#catalog-subtitle");
const addConnectionButton = document.querySelector("#add-connection-button");
const codePanel = document.querySelector("#catalog-code-panel");
const dialog = document.querySelector("#editor-dialog");
const dialogForm = document.querySelector("#editor-form");
const dialogFields = document.querySelector("#dialog-fields");
const dialogStatus = document.querySelector("#dialog-status");
const dialogPreviewBtn = document.querySelector("#dialog-preview-btn");
const svg = {
  folder: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5h7l2 2h9v8.7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7.5Z"/><path d="M3 10h18"/></svg>',
  connection: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="12" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="m8.6 10.5 6.8-3m-6.8 6 6.8 3"/></svg>',
  edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6 4 4M4 20l4-.8L19 8a2.8 2.8 0 0 0-4-4L4 15l-.8 5Z"/></svg>',
  delete: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16m-10 4v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  add: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14m-7-7h14"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>',
  pipeline: '<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  sync: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>',
  htmlDoc: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="m10 13-2 2 2 2m4-4 2 2-2 2"/></svg>',
  mdDoc: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
};

let currentState;
let activeCatalog;
const pipelineCatalogCache = new Map();
let etlActiveCatalog = null;
let connectors = [];
let selectedConnectionId = null;
let selectedFolderId = null;
let activeDetailTab = "Overview";
let editorHandler = null;
let connectionEditorRenderer = null;
const collapsedFolders = new Set();

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function apiErrorMessage(payload, fallback) {
  return payload && typeof payload.error === "string" ? payload.error : fallback;
}

let demoState = null;

function isStaticDemoMode() {
  return (
    window.location.hostname.includes("github.io") ||
    window.location.protocol === "file:" ||
    window.location.pathname.endsWith("demo.html") ||
    window.location.pathname.includes("/demo") ||
    Boolean(window.__DET_STATIC_DEMO__) ||
    (!window.location.port && Boolean(window.DET_DEMO_DATA))
  );
}

function handleStaticMockApi(path, options = {}) {
  const data = window.DET_DEMO_DATA;
  if (!data) return null;
  if (!demoState) {
    demoState = { ...data.state };
  }

  const url = new URL(path, window.location.origin);
  const pathname = url.pathname;
  const method = (options.method || "GET").toUpperCase();

  // 1. State
  if (pathname === "/api/state") {
    if (method === "POST" && options.body) {
      try {
        const body = JSON.parse(options.body);
        demoState = { ...demoState, ...body };
      } catch (e) {}
    }
    return demoState;
  }

  // 2. Connectors
  if (pathname === "/api/connectors") {
    return { items: data.connectors };
  }

  // 3. Catalogs
  if (pathname === "/api/catalogs") {
    return { items: data.catalogs, active: data.active_catalog_name };
  }
  if (pathname === "/api/catalogs/active") {
    return { success: true };
  }

  // 4. Catalog connection preview & detail
  if (pathname.startsWith("/api/catalog/connections/")) {
    const parts = pathname.replace(/^\/+|\/+$/g, "").split("/");
    const connId = decodeURIComponent(parts[3] || "");
    const subAction = parts[4];

    // Find connection in catalog data
    let foundConn = null;
    let foundFolder = "Sample_Warehouse_Connections";
    for (const c of (data.catalog?.catalog?.connections || [])) {
      if (c.id === connId || c.name === connId) { foundConn = c; break; }
    }
    if (!foundConn) {
      for (const folder of (data.catalog?.catalog?.folders || [])) {
        for (const c of (folder.connections || [])) {
          if (c.id === connId || c.name === connId) {
            foundConn = c;
            foundFolder = folder.name;
            break;
          }
        }
        if (foundConn) break;
      }
    }

    if (subAction === "preview") {
      const connName = foundConn ? foundConn.name : connId;
      const preview = data.previews[connName] || data.previews["raw_customers"] || {
        columns: [{ name: "id", data_type: "Utf8", nullable: true, description: "" }],
        rows: [{ id: "1" }],
        row_limit: 50,
        total_rows_sampled: 1,
      };
      return preview;
    }

    if (subAction === "infer-schema") {
      return { success: true, message: "Schema inferred successfully (demo mode)." };
    }

    if (foundConn) {
      return { ...foundConn, folder_name: foundFolder };
    }

    return {
      id: connId,
      name: connId,
      connector: "e2f4d6f3-a4b9-5dd7-afbb-1a71d98a4616",
      is_source: true,
      is_destination: false,
      folder_name: foundFolder,
      description: "NovaMart warehouse connection",
      options: {},
      columns: [],
    };
  }

  if (pathname === "/api/catalog/folders" || pathname.startsWith("/api/catalog/folders/")) {
    return { success: true };
  }

  if (pathname === "/api/catalog/name") {
    return { success: true };
  }

  if (pathname === "/api/catalog") {
    return data.catalog;
  }

  // 5. Pipeline execution
  if (pathname === "/api/pipelines/run") {
    let pipelineName = "pipeline";
    try {
      const parsed = typeof options.body === "string" ? JSON.parse(options.body) : options.body;
      pipelineName = (typeof parsed === "string" ? parsed : parsed?.name) || "pipeline";
    } catch (e) {}
    return {
      status: "SUCCESS",
      pipeline_name: pipelineName,
      total_duration_seconds: 0.038,
      steps: [
        {
          step_name: "normalize_and_clean",
          status: "SUCCESS",
          duration_ms: 19.4,
          rows_processed: 500,
          destinations: [{ destination_name: "gold_mart", format: "delta", rows_written: 500, duration_ms: 12.1 }],
        },
        {
          step_name: "aggregate_and_publish",
          status: "SUCCESS",
          duration_ms: 18.6,
          rows_processed: 500,
          destinations: [{ destination_name: "analytics_mart", format: "parquet", rows_written: 500, duration_ms: 11.2 }],
        },
      ],
    };
  }

  // 6. Validation
  if (pathname === "/api/pipelines/validate" || pathname === "/api/pipelines/validate-sql") {
    return { valid: true, error: null, hints: [], steps: [{ step_name: "step_1", column_count: 6 }] };
  }

  // 7. Pipeline item details
  if (pathname.startsWith("/api/pipelines/item/")) {
    const rawKey = decodeURIComponent(pathname.slice("/api/pipelines/item/".length));
    let pipe = data.pipeline_details?.[rawKey] || data.pipeline_details?.[`Sample_Warehouse_Pipelines/${rawKey}`];
    if (!pipe) {
      for (const [k, p] of Object.entries(data.pipeline_details || {})) {
        if (p.name === rawKey || p.id === rawKey || k.endsWith("/" + rawKey)) {
          pipe = p;
          break;
        }
      }
    }
    if (!pipe && data.pipelines && data.pipelines.length) {
      const first = data.pipelines[0];
      pipe = data.pipeline_details?.[`${first.folder}/${first.name}`] || first;
    }
    return pipe || { name: rawKey, folder: "Sample_Warehouse_Pipelines", steps: [] };
  }

  // 8. Pipelines list
  if (pathname === "/api/pipelines") {
    return { folders: ["Sample_Warehouse_Pipelines"], items: data.pipelines };
  }

  if (pathname === "/api/pipelines/folders" || pathname.startsWith("/api/pipelines/folders/")) {
    return { success: true };
  }

  // 9. Monitoring
  if (pathname === "/api/monitoring/runs") {
    return { items: data.monitoring_runs };
  }

  if (pathname.startsWith("/api/monitoring/runs/")) {
    const runId = decodeURIComponent(pathname.slice("/api/monitoring/runs/".length));
    const run = (data.monitoring_runs || []).find((r) => r.id === runId || r.run_id === runId);
    return run || (data.monitoring_runs && data.monitoring_runs[0]) || { status: "SUCCESS" };
  }

  if (pathname.startsWith("/api/monitoring/pipelines/")) {
    return {
      runs: data.monitoring_runs || [],
      summary: data.monitoring_summary || {},
    };
  }

  if (pathname === "/api/monitoring/summary") {
    return data.monitoring_summary;
  }

  // 10. Documentation
  if (pathname.startsWith("/api/docs/item/")) {
    const rel_path = decodeURIComponent(pathname.slice("/api/docs/item/".length));
    const item = (data.docs?.items || []).find((d) => d.path === rel_path || d.name === rel_path) || (data.docs?.items && data.docs.items[0]);
    const content = (data.docs_contents && (data.docs_contents[rel_path] || data.docs_contents[item?.name])) ||
      `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${item?.name || "Documentation"}</title><style>body{font-family:sans-serif;padding:2rem;background:#0f172a;color:#f8fafc;}</style></head><body><h1>Pipeline: ${item?.name || "Documentation"}</h1><p>Folder: ${item?.folder || "Sample_Warehouse_Pipelines"}</p><p>SQL ETL Pipeline documentation generated by det.</p></body></html>`;
    return {
      folder: item?.folder || "Sample_Warehouse_Pipelines",
      filename: item ? `${item.name}.html` : "doc.html",
      name: item?.name || "Pipeline Documentation",
      format: "html",
      rel_path: rel_path,
      size_bytes: item?.bytes || content.length,
      modified_at: "2026-10-13T09:15:00Z",
      content: content,
    };
  }

  if (pathname.startsWith("/api/docs/verify/")) {
    return { is_stale: false, reason: "In sync with pipeline definition" };
  }

  if (pathname === "/api/docs/regenerate") {
    return { success: true, message: "Documentation regenerated (demo mode)." };
  }

  if (pathname === "/api/docs") {
    return data.docs;
  }

  // 11. Sample Data
  if (pathname === "/api/sample-data/install") {
    return { success: true, message: "NovaMart Global warehouse loaded." };
  }

  return { success: true, message: "Operation simulated (demo mode)." };
}

async function api(path, options = {}) {
  if (isStaticDemoMode()) {
    const mockRes = handleStaticMockApi(path, options);
    if (mockRes !== null) {
      return mockRes;
    }
  }

  try {
    const response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(apiErrorMessage(result, `Request failed (${response.status}).`));
    }
    return result;
  } catch (error) {
    if (window.DET_DEMO_DATA) {
      const mockRes = handleStaticMockApi(path, options);
      if (mockRes !== null) {
        return mockRes;
      }
    }
    throw error;
  }
}

async function updatePreferences(preferences) {
  return api("/api/state", { method: "POST", body: JSON.stringify(preferences) });
}

function showNotification(message, duration = 3200) {
  let toast = document.querySelector("#app-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "app-toast";
    toast.className = "app-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.classList.remove("show");
  }, duration);
}

const bgTaskDock = document.querySelector("#bg-task-dock");
const activeBgTasks = new Map();

function showBackgroundTask({ id, title, status = "running", actionLabel, onAction, autoDismissMs }) {
  if (!bgTaskDock) return;
  let pill = activeBgTasks.get(id);
  if (!pill) {
    pill = document.createElement("div");
    pill.className = `bg-task-pill is-${status}`;
    pill.id = `bg-task-${id}`;
    bgTaskDock.appendChild(pill);
    activeBgTasks.set(id, pill);
  } else {
    pill.className = `bg-task-pill is-${status}`;
  }

  const iconSvg = status === "running"
    ? `<svg class="bg-task-spinner" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4" stroke-linecap="round"/></svg>`
    : status === "success"
    ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;

  pill.innerHTML = `
    <div class="bg-task-icon">${iconSvg}</div>
    <div class="bg-task-text" title="${escapeHtml(title)}">${escapeHtml(title)}</div>
    ${actionLabel ? `<button type="button" class="bg-task-action">${escapeHtml(actionLabel)}</button>` : ""}
    <button type="button" class="bg-task-close" title="Dismiss" aria-label="Dismiss">&times;</button>
  `;

  if (actionLabel && onAction) {
    pill.querySelector(".bg-task-action").addEventListener("click", () => {
      onAction();
    });
  }

  pill.querySelector(".bg-task-close").addEventListener("click", () => {
    dismissBackgroundTask(id);
  });

  if (pill._dismissTimeout) clearTimeout(pill._dismissTimeout);
  const timeoutMs = autoDismissMs || (status === "success" ? 5000 : status === "failed" ? 8000 : null);
  if (timeoutMs) {
    pill._dismissTimeout = setTimeout(() => {
      dismissBackgroundTask(id);
    }, timeoutMs);
  }
}

function dismissBackgroundTask(id) {
  const pill = activeBgTasks.get(id);
  if (!pill) return;
  pill.classList.add("is-dismissing");
  setTimeout(() => {
    pill.remove();
    activeBgTasks.delete(id);
  }, 300);
}

function switchToModule(moduleName) {
  if (!currentState) {
    currentState = { module: moduleName };
  } else {
    currentState.module = moduleName;
  }
  for (const tab of moduleTabs) {
    const isActive = tab.dataset.module === moduleName;
    tab.setAttribute("aria-pressed", String(isActive));
  }
  renderModule(moduleName);
  updatePreferences({ module: moduleName }).catch(console.error);
}

function applyState(state) {
  currentState = state;
  for (const tab of moduleTabs) {
    const isActive = tab.dataset.module === state.module;
    tab.setAttribute("aria-pressed", String(isActive));
  }
  themeRoot.dataset.theme = state.theme;
  document.title = `${state.app_name} | ${state.app_description}`;
  renderModule(state.module);
  if (monCrumbWorkspace && state?.workspace) {
    monCrumbWorkspace.textContent = state.workspace.split(/[\\/]/).pop() || "WORKSPACE";
  }
  const nextTheme = state.theme === "light" ? "dark" : "light";
  themeToggle.setAttribute("aria-label", `Switch to ${nextTheme} mode`);
  themeToggle.title = `Switch to ${nextTheme} mode`;
}

function renderModule(module) {
  const content = moduleContent[module];
  const isCatalog = module === "Catalog";
  const isETL = module === "ETL";
  const isMonitoring = module === "Monitoring";
  const isDocs = module === "Documentation";
  const isHelp = module === "Help";

  catalogExplorer.hidden = !isCatalog;
  etlExplorer.hidden = !isETL;
  if (monitoringExplorer) monitoringExplorer.hidden = !isMonitoring;
  if (docsExplorer) docsExplorer.hidden = !isDocs;
  if (helpExplorer) helpExplorer.hidden = !isHelp;
  genericExplorer.hidden = isCatalog || isETL || isMonitoring || isDocs || isHelp;

  genericModuleContent.hidden = isCatalog || isETL || isMonitoring || isDocs || isHelp;
  catalogModule.hidden = !isCatalog;
  etlModule.hidden = !isETL;
  if (monitoringModule) monitoringModule.hidden = !isMonitoring;
  if (docsModule) docsModule.hidden = !isDocs;
  if (helpModule) helpModule.hidden = !isHelp;

  if (isETL) {
    refreshETL();
  } else if (isMonitoring) {
    refreshMonitoring();
  } else if (isDocs) {
    refreshDocs();
  } else if (isHelp) {
    refreshHelp();
  } else if (!isCatalog) {
    explorerTitle.textContent = `${module} explorer`;
    explorerMessage.textContent = content.explorer;
    breadcrumbModule.textContent = module.toUpperCase();
    moduleTitle.textContent = `${module} workspace`;
    moduleDescription.textContent = content.description;
  }
}

async function refreshCatalog() {
  activeCatalog = await api("/api/catalog");
  pipelineCatalogCache.set(activeCatalog.filename, activeCatalog);
  if (!etlActiveCatalog || etlActiveCatalog.filename === activeCatalog.filename) {
    etlActiveCatalog = activeCatalog;
  }
  const { catalog, filename } = activeCatalog;
  document.querySelector("#catalog-file-name").textContent = catalog.name;
  document.querySelector("#catalog-file-path").textContent = `catalog/${filename}`;
  catalogHeading.textContent = catalog.name;
  document.querySelector("#catalog-yaml").value = activeCatalog.yaml;
  document.querySelector("#catalog-code-status").textContent = "";
  if (selectedConnectionId && !findConnection(selectedConnectionId)) {
    selectedConnectionId = null;
  }
  if (selectedFolderId && !catalog.folders.some((folder) => folder.id === selectedFolderId)) {
    selectedFolderId = null;
  }
  renderCatalogTree();
  renderCatalogSummary();
  renderTableInsertDropdown();
  renderDestinations();
  if (selectedConnectionId) {
    await renderConnectionDetail(selectedConnectionId);
  } else if (selectedFolderId) {
    renderFolderDetail(selectedFolderId);
  } else {
    showCatalogOverview();
  }
}

function findConnection(connectionId) {
  for (const folder of activeCatalog.catalog.folders) {
    const connection = folder.connections.find((item) => item.id === connectionId);
    if (connection) return { ...connection, folder_id: folder.id, folder_name: folder.name };
  }
  return null;
}

function renderCatalogTree() {
  const query = catalogSearch.value.trim().toLowerCase();
  const catalogTitle = document.querySelector("#catalog-file-title");
  const catalogIsSelected = !selectedFolderId && !selectedConnectionId;
  catalogTitle.classList.toggle("is-selected", catalogIsSelected);
  catalogTitle.setAttribute("aria-pressed", String(catalogIsSelected));
  const folders = activeCatalog.catalog.folders.map((folder) => {
    const connections = folder.connections.filter((connection) =>
      `${connection.name} ${connection.description} ${connection.connector} ${connection.columns.map((column) => column.name).join(" ")}`
        .toLowerCase().includes(query));
    const folderMatches = folder.name.toLowerCase().includes(query);
    if (query && !folderMatches && connections.length === 0) return "";
    const isCollapsed = collapsedFolders.has(folder.id) && !query;
    return `<section class="tree-folder${isCollapsed ? " is-collapsed" : ""}" role="treeitem" aria-expanded="${!isCollapsed}">
      <div class="tree-row folder-row${selectedFolderId === folder.id ? " is-selected" : ""}">
        <button class="tree-chevron" type="button" data-toggle-folder="${escapeHtml(folder.id)}" aria-label="${isCollapsed ? "Expand" : "Collapse"} ${escapeHtml(folder.name)}">${svg.chevron}</button>
        <span class="tree-item-icon">${svg.folder}</span>
        <button class="tree-label folder-select" type="button" data-folder-id="${escapeHtml(folder.id)}" aria-pressed="${selectedFolderId === folder.id}">${escapeHtml(folder.name)}</button>
        <span class="tree-actions">
          <button class="icon-button tree-action" type="button" title="Add connection" aria-label="Add connection to ${escapeHtml(folder.name)}" data-action="add-connection" data-folder-id="${escapeHtml(folder.id)}">${svg.add}</button>
          <button class="icon-button tree-action" type="button" title="Rename folder" aria-label="Rename folder ${escapeHtml(folder.name)}" data-action="rename-folder" data-folder-id="${escapeHtml(folder.id)}">${svg.edit}</button>
          <button class="icon-button tree-action" type="button" title="Delete folder" aria-label="Delete folder ${escapeHtml(folder.name)}" data-action="delete-folder" data-folder-id="${escapeHtml(folder.id)}">${svg.delete}</button>
        </span>
      </div>
      <div class="tree-children">${connections.map((connection) => renderConnectionRow(connection)).join("")}</div>
    </section>`;
  }).join("");
  catalogTree.innerHTML = `${folders || '<p class="tree-empty">No matching folders or connections.</p>'}
    <button class="tree-add-folder" id="add-folder-button" type="button">${svg.add}<span>New folder</span></button>`;
}

function renderConnectionRow(connection) {
  const connector = connectors.find((item) => item.id === connection.connector);
  const selected = selectedConnectionId === connection.id;
  const roles = [connection.is_source && "Source", connection.is_destination && "Destination"].filter(Boolean).join(" · ");
  return `<div class="tree-row connection-row${selected ? " is-selected" : ""}" role="treeitem">
    <span class="tree-item-icon">${svg.connection}</span>
    <button class="tree-label connection-select" type="button" data-connection-id="${escapeHtml(connection.id)}" aria-pressed="${selected}">
      <span>${escapeHtml(connection.name)}</span><small>${escapeHtml(connector?.label || "Connector")} · ${roles}</small>
    </button>
    <span class="tree-actions">
      <button class="icon-button tree-action" type="button" title="Edit connection" aria-label="Edit connection ${escapeHtml(connection.name)}" data-action="edit-connection" data-connection-id="${escapeHtml(connection.id)}">${svg.edit}</button>
      <button class="icon-button tree-action" type="button" title="Delete connection" aria-label="Delete connection ${escapeHtml(connection.name)}" data-action="delete-connection" data-connection-id="${escapeHtml(connection.id)}">${svg.delete}</button>
    </span>
  </div>`;
}

function renderCatalogSummary() {
  const folders = activeCatalog.catalog.folders;
  const connections = folders.flatMap((folder) => folder.connections.map((connection) => ({
    ...connection,
    folder_name: folder.name,
  })));
  const sources = connections.filter((connection) => connection.is_source).length;
  const destinations = connections.filter((connection) => connection.is_destination).length;
  catalogSummary.innerHTML = `
    <div class="summary-card"><span class="summary-label">FOLDERS</span><strong>${folders.length}</strong><span class="summary-caption">Organized in this catalog</span></div>
    <div class="summary-card"><span class="summary-label">CONNECTIONS</span><strong>${connections.length}</strong><span class="summary-caption">Reusable data locations</span></div>
    <div class="summary-card"><span class="summary-label">SOURCES</span><strong>${sources}</strong><span class="summary-caption">Available to read</span></div>
    <div class="summary-card"><span class="summary-label">DESTINATIONS</span><strong>${destinations}</strong><span class="summary-caption">Available to write</span></div>
    ${renderConnectionTable(connections, true)}`;
}

function renderConnectionTable(connections, includeFolder) {
  const headers = ["CONNECTION", "DESCRIPTION", "CONNECTOR", "ROLE"];
  if (includeFolder) headers.push("FOLDER");
  const rows = connections.map((connection) => {
    const connector = connectors.find((item) => item.id === connection.connector);
    const roles = [connection.is_source && "Source", connection.is_destination && "Destination"].filter(Boolean).join(" · ");
    return `<tr><td><button class="table-link" type="button" data-connection-id="${escapeHtml(connection.id)}">${escapeHtml(connection.name)}</button></td>
      <td>${escapeHtml(connection.description || "—")}</td><td>${escapeHtml(connector?.label || "Unknown")}</td><td>${escapeHtml(roles)}</td>
      ${includeFolder ? `<td>${escapeHtml(connection.folder_name || "")}</td>` : ""}</tr>`;
  }).join("");
  const columnCount = headers.length;
  return `<div class="catalog-table-wrap"><table class="catalog-table"><thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
    <tbody>${rows || `<tr><td class="empty-table" colspan="${columnCount}">No connections in this ${includeFolder ? "catalog" : "folder"} yet.</td></tr>`}</tbody></table></div>`;
}

function showCatalogOverview() {
  if (addConnectionButton) addConnectionButton.hidden = true;
  catalogHeading.textContent = activeCatalog.catalog.name;
  catalogSubtitle.textContent = "Catalog overview and its saved connections.";
  catalogSummary.hidden = false;
  catalogDetail.hidden = true;
  codePanel.hidden = true;
}

function renderFolderDetail(folderId) {
  const folder = activeCatalog.catalog.folders.find((item) => item.id === folderId);
  if (!folder) {
    showCatalogOverview();
    return;
  }
  if (addConnectionButton) addConnectionButton.hidden = false;
  const connections = folder.connections.map((connection) => ({ ...connection, folder_name: folder.name }));
  const sources = connections.filter((connection) => connection.is_source).length;
  const destinations = connections.filter((connection) => connection.is_destination).length;
  catalogHeading.textContent = folder.name;
  catalogSubtitle.textContent = `${connections.length} connection${connections.length === 1 ? "" : "s"} in this folder.`;
  catalogSummary.hidden = true;
  catalogDetail.innerHTML = `
    <div class="catalog-summary folder-summary">
      <div class="summary-card"><span class="summary-label">CONNECTIONS</span><strong>${connections.length}</strong><span class="summary-caption">In this folder</span></div>
      <div class="summary-card"><span class="summary-label">SOURCES</span><strong>${sources}</strong><span class="summary-caption">Available to read</span></div>
      <div class="summary-card"><span class="summary-label">DESTINATIONS</span><strong>${destinations}</strong><span class="summary-caption">Available to write</span></div>
    </div>
    ${renderConnectionTable(connections, false)}`;
  catalogDetail.hidden = false;
  codePanel.hidden = true;
}

async function selectConnection(connectionId) {
  selectedConnectionId = connectionId;
  selectedFolderId = null;
  activeDetailTab = "Overview";
  await renderConnectionDetail(connectionId);
  renderCatalogTree();
}

function selectFolder(folderId) {
  selectedFolderId = folderId;
  selectedConnectionId = null;
  renderFolderDetail(folderId);
  renderCatalogTree();
}

function selectCatalog() {
  selectedConnectionId = null;
  selectedFolderId = null;
  showCatalogOverview();
  renderCatalogTree();
}

async function renderConnectionDetail(connectionId) {
  if (addConnectionButton) addConnectionButton.hidden = true;
  const connection = await api(`/api/catalog/connections/${encodeURIComponent(connectionId)}`);
  const connector = connectors.find((item) => item.id === connection.connector);
  const role = [connection.is_source && "Source", connection.is_destination && "Destination"].filter(Boolean).join(" · ");
  const tabs = ["Overview", "Settings", "Schema", "Preview"];
  let pane;
  if (activeDetailTab === "Overview") {
    pane = `<div class="detail-overview">
      <div class="detail-facts"><div><span>CONNECTOR</span><strong>${escapeHtml(connector?.label || "Unknown")}</strong></div>
        <div><span>ROLE</span><strong>${escapeHtml(role)}</strong></div><div><span>FOLDER</span><strong>${escapeHtml(connection.folder_name)}</strong></div>
        <div><span>IDENTIFIER</span><code>${escapeHtml(connection.id)}</code></div></div>
      <div class="detail-description"><h3>Description</h3><p>${escapeHtml(connection.description || "No description provided.")}</p></div>
      <div class="detail-description"><h3>Location</h3><code>${escapeHtml(connection.options.path || connection.options.output_path || "Not configured")}</code></div>
      ${connection.is_destination ? '<p class="notice">Destination settings are saved as catalog metadata. Pipeline writing becomes active with ETL execution.</p>' : ""}
    </div>`;
  } else if (activeDetailTab === "Settings") {
    pane = `<div class="settings-sections">${["connection", "read", "write"].map((section) => {
      const fields = (connector?.fields || []).filter((field) => field.section === section && (
        section === "connection" || (section === "read" && connection.is_source) || (section === "write" && connection.is_destination)
      ));
      if (!fields.length) return "";
      return `<section class="settings-section"><h3>${section === "connection" ? "Connection" : section === "read" ? "Read options" : "Write options"}</h3>
        <dl>${fields.map((field) => {
          const value = connection.options[field.name];
          if (value === undefined || value === null || value === "") return "";
          return `<div><dt>${escapeHtml(field.label)}</dt><dd>${escapeHtml(Array.isArray(value) ? value.join(", ") : typeof value === "boolean" ? (value ? "Yes" : "No") : value)}</dd></div>`;
        }).join("") || '<div><dd>No options set.</dd></div>'}</dl></section>`;
    }).join("")}</div>
      <button class="secondary-button" data-action="edit-connection" data-connection-id="${escapeHtml(connection.id)}">${svg.edit} Edit settings</button>`;
  } else if (activeDetailTab === "Schema") {
    pane = `<div class="schema-toolbar"><div><h3>Saved schema</h3><p>Infer columns from a source or edit column descriptions.</p></div>
      ${connection.is_source ? '<button class="secondary-button" id="infer-schema-button" type="button">Infer schema</button>' : ""}
      ${connection.columns.length ? '<button class="primary-button" id="save-column-descriptions" type="button">Save descriptions</button>' : ""}</div>
      ${connection.columns.length ? `<div class="catalog-table-wrap"><table class="catalog-table schema-table"><thead><tr><th>COLUMN</th><th>TYPE</th><th>NULLABLE</th><th>DESCRIPTION</th></tr></thead><tbody>${connection.columns.map((column) =>
        `<tr><td>${escapeHtml(column.name)}</td><td><code>${escapeHtml(column.data_type)}</code></td><td>${column.nullable ? "Yes" : "No"}</td><td><input class="column-description" data-column-id="${escapeHtml(column.id)}" value="${escapeHtml(column.description)}" aria-label="Description for ${escapeHtml(column.name)}"></td></tr>`
      ).join("")}</tbody></table></div>` : '<div class="empty-state"><strong>No saved schema</strong><p>Infer a source schema, or add saved column definitions when editing this connection.</p></div>'}`;
  } else {
    pane = `<div class="schema-toolbar"><div><h3>Data preview</h3><p>First 50 rows, evaluated lazily by DataFusion.</p></div>
      ${connection.is_source ? '<button class="secondary-button" id="load-preview-button" type="button">Load preview</button>' : ""}</div>
      <div id="preview-result" class="preview-result"><div class="empty-state"><strong>Preview not loaded</strong><p>Load a source preview when you are ready.</p></div></div>`;
  }
  catalogDetail.innerHTML = `<div class="detail-header"><div class="connection-badge">${svg.connection}</div>
      <div class="detail-title"><h2>${escapeHtml(connection.name)}</h2><p>${escapeHtml(connector?.label || "Unknown connector")} · ${escapeHtml(role)}</p></div>
      <div class="detail-header-actions">
        ${connection.is_source ? `<button class="primary-button compact-btn" id="query-in-pipeline-btn" data-connection-name="${escapeHtml(connection.name)}" title="Query this source in a new pipeline"><svg viewBox="0 0 24 24" aria-hidden="true" style="width:13px;height:13px;margin-right:4px;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>Query in Pipeline</button>` : ""}
        <button class="icon-button" data-action="edit-connection" data-connection-id="${escapeHtml(connection.id)}" title="Edit connection" aria-label="Edit connection">${svg.edit}</button>
      </div></div>
    <nav class="detail-tabs" aria-label="Connection details">${tabs.map((tab) =>
      `<button type="button" class="detail-tab${activeDetailTab === tab ? " is-active" : ""}" data-detail-tab="${tab}">${tab}</button>`
    ).join("")}</nav><div class="detail-body">${pane}</div>`;
  catalogDetail.hidden = false;
  catalogSummary.hidden = true;
  catalogHeading.textContent = connection.name;
  catalogSubtitle.textContent = `${connector?.label || "Unknown connector"} · ${role}`;
  codePanel.hidden = true;
}

function openEditor({ title, eyebrow = "CATALOG", fields, submitLabel = "Save", onSubmit }) {
  document.querySelector("#dialog-title").textContent = title;
  document.querySelector("#dialog-eyebrow").textContent = eyebrow;
  document.querySelector("#dialog-save").textContent = submitLabel;
  dialogFields.innerHTML = fields;
  dialogStatus.textContent = "";
  editorHandler = onSubmit;
  dialog.showModal();
}

function closeEditor() {
  editorHandler = null;
  if (dialogPreviewBtn) dialogPreviewBtn.hidden = true;
  dialog.close();
}

function textField(name, label, value = "", placeholder = "", options = {}) {
  const input = options.multiline
    ? `<textarea name="${escapeHtml(name)}" placeholder="${escapeHtml(placeholder)}"${options.required ? " required" : ""}>${escapeHtml(value)}</textarea>`
    : `<input name="${escapeHtml(name)}" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}"${options.required ? " required" : ""}${options.type ? ` type="${options.type}"` : ""}${options.maxlength ? ` maxlength="${options.maxlength}"` : ""}${options.pattern ? ` pattern="${escapeHtml(options.pattern)}"` : ""}${options.title ? ` title="${escapeHtml(options.title)}"` : ""}>`;
  return `<label class="form-field"><span>${escapeHtml(label)}${options.required ? " *" : ""}</span>${input}${options.help ? `<small>${escapeHtml(options.help)}</small>` : ""}</label>`;
}

function renderConnectorField(field, values) {
  const value = values[field.name] ?? field.default ?? "";
  let control;
  if (field.kind === "boolean") {
    control = `<input type="checkbox" name="option:${escapeHtml(field.name)}" ${value ? "checked" : ""}>`;
  } else if (field.kind === "select") {
    control = `<select name="option:${escapeHtml(field.name)}">${(field.choices || []).map((choice) =>
      `<option value="${escapeHtml(choice)}" ${String(choice) === String(value) ? "selected" : ""}>${escapeHtml(choice || "Default")}</option>`
    ).join("")}</select>`;
  } else if (field.kind === "list" || field.kind === "textarea") {
    const listValue = Array.isArray(value)
      ? value.join("\n")
      : value && typeof value === "object"
        ? JSON.stringify(value, null, 2)
        : value;
    control = `<textarea name="option:${escapeHtml(field.name)}" placeholder="${escapeHtml(field.placeholder || "")}">${escapeHtml(listValue)}</textarea>`;
  } else {
    control = `<input name="option:${escapeHtml(field.name)}" type="${field.kind === "number" ? "number" : "text"}" value="${escapeHtml(value)}" placeholder="${escapeHtml(field.placeholder || "")}"${field.required ? " required" : ""}>`;
  }
  return `<label class="form-field"><span>${escapeHtml(field.label)}${field.required ? " *" : ""}</span>${control}${field.description ? `<small>${escapeHtml(field.description)}</small>` : ""}</label>`;
}

function connectionEditor(connection = null, folderId = null) {
  let activeConnectionTab = "general";
  let previewData = null;
  let isPreviewLoading = false;
  const initialConnector = connectors.find((item) => item.id === connection?.connector) || connectors[0];
  const initialFolder = folderId || connection?.folder_id || activeCatalog.catalog.folders[0]?.id;

  const renderFields = (connector, previousValues = {}) => {
    const selected = connectors.find((item) => item.id === connector) || initialConnector;
    const wasSource = dialogForm.elements.namedItem("is_source")?.checked ?? connection?.is_source !== false;
    const wasDestination = dialogForm.elements.namedItem("is_destination")?.checked ?? Boolean(connection?.is_destination);
    const descriptor = (field) => renderConnectorField(field, connection?.options || {});

    // Categorize fields by section
    const connFields = selected.fields.filter((field) => field.section === "connection");
    const coreConnFields = connFields.filter((field) => !field.advanced);
    const advConnFields = connFields.filter((field) => field.advanced);

    const readFields = selected.fields.filter((field) => field.section === "read");
    const coreReadFields = readFields.filter((field) => !field.advanced);
    const advReadFields = readFields.filter((field) => field.advanced);

    const writeFields = selected.fields.filter((field) => field.section === "write");
    const coreWriteFields = writeFields.filter((field) => !field.advanced);
    const advWriteFields = writeFields.filter((field) => field.advanced);

    const isFieldConfigured = (field) => {
      const val = previousValues[`option:${field.name}`] ?? connection?.options?.[field.name];
      return val !== undefined && val !== null && val !== "" && val !== field.default;
    };

    const advConnConfiguredCount = advConnFields.filter(isFieldConfigured).length;
    const readConfiguredCount = readFields.filter(isFieldConfigured).length;
    const writeConfiguredCount = writeFields.filter(isFieldConfigured).length;
    const schemaCount = (connection?.columns || []).length;

    // Validate active tab
    if (activeConnectionTab === "read" && !wasSource) activeConnectionTab = "general";
    if (activeConnectionTab === "write" && !wasDestination) activeConnectionTab = "general";

    // 1. Tab Bar
    const tabsHtml = `
      <div class="conn-dialog-tabs" role="tablist" aria-label="Connection sections">
        <button type="button" class="conn-dialog-tab ${activeConnectionTab === "general" ? "active" : ""}" data-tab="general" role="tab" aria-selected="${activeConnectionTab === "general"}">
          <span>General</span>
        </button>
        ${wasSource ? `
          <button type="button" class="conn-dialog-tab ${activeConnectionTab === "read" ? "active" : ""}" data-tab="read" role="tab" aria-selected="${activeConnectionTab === "read"}">
            <span>Read Options (${escapeHtml(selected.label)})</span>
            ${readConfiguredCount > 0 ? `<span class="conn-tab-badge">${readConfiguredCount}</span>` : ""}
          </button>
        ` : ""}
        <button type="button" class="conn-dialog-tab ${activeConnectionTab === "schema" ? "active" : ""}" data-tab="schema" role="tab" aria-selected="${activeConnectionTab === "schema"}">
          <span>Schema &amp; Types</span>
          ${schemaCount > 0 ? `<span class="conn-tab-badge">${schemaCount} cols</span>` : ""}
        </button>
        ${wasDestination ? `
          <button type="button" class="conn-dialog-tab ${activeConnectionTab === "write" ? "active" : ""}" data-tab="write" role="tab" aria-selected="${activeConnectionTab === "write"}">
            <span>Write Options (${escapeHtml(selected.label)})</span>
            ${writeConfiguredCount > 0 ? `<span class="conn-tab-badge">${writeConfiguredCount}</span>` : ""}
          </button>
        ` : ""}
        ${wasSource ? `
          <button type="button" class="conn-dialog-tab ${activeConnectionTab === "preview" ? "active" : ""}" data-tab="preview" role="tab" aria-selected="${activeConnectionTab === "preview"}">
            <span>Data Preview</span>
            ${previewData?.success ? `<span class="conn-tab-badge">${previewData.row_count} rows</span>` : ""}
          </button>
        ` : wasDestination ? `
          <button type="button" class="conn-dialog-tab ${activeConnectionTab === "preview" ? "active" : ""}" data-tab="preview" role="tab" aria-selected="${activeConnectionTab === "preview"}">
            <span>Target Specs</span>
          </button>
        ` : ""}
      </div>
    `;

    // 2. General Panel
    const generalPanelHtml = `
      <div class="conn-dialog-tab-panel" data-panel="general" role="tabpanel" ${activeConnectionTab === "general" ? "" : "hidden"}>
        <div class="form-grid">
          ${textField("name", "Connection name", connection?.name || "", "e.g. DailySales_01", {
            required: true,
            maxlength: 30,
            pattern: "[A-Za-z][A-Za-z0-9_]{0,29}",
            title: "Start with a letter; use only letters, numbers, and underscores (maximum 30 characters).",
            help: "SQL identifier: starts with a letter; only letters, numbers, and underscores; maximum 30 characters.",
          })}
          <label class="form-field"><span>Folder *</span><select name="folder_id">${activeCatalog.catalog.folders.map((folder) => `<option value="${escapeHtml(folder.id)}" ${folder.id === initialFolder ? "selected" : ""}>${escapeHtml(folder.name)}</option>`).join("")}</select></label>
          <label class="form-field"><span>Connector *</span><select name="connector">${connectors.map((item) => `<option value="${escapeHtml(item.id)}" ${item.id === selected.id ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}</select></label>
          <div class="form-field role-fields"><span>Use as</span><div class="checkbox-options">
            <label><input name="is_source" type="checkbox" ${connection?.is_source !== false ? "checked" : ""}> Source</label>
            <label><input name="is_destination" type="checkbox" ${connection?.is_destination ? "checked" : ""}> Destination</label>
          </div></div>
          ${coreConnFields.map(descriptor).join("")}
          ${textField("description", "Description", connection?.description || "", "What data does this connection represent?", { multiline: true })}
        </div>
        ${advConnFields.length ? `
          <details class="connector-advanced"${advConnConfiguredCount > 0 ? " open" : ""}>
            <summary class="advanced-summary">
              <span class="advanced-title">
                <svg class="advanced-chevron" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3l5 5-5 5"/></svg>
                Advanced connection &amp; file matching settings
              </span>
              ${advConnConfiguredCount > 0 ? `<span class="advanced-badge">${advConnConfiguredCount} customized</span>` : `<span class="advanced-hint">Optional</span>`}
            </summary>
            <div class="form-grid advanced-grid">${advConnFields.map(descriptor).join("")}</div>
          </details>` : ""}
      </div>
    `;

    // 3. Read Panel
    const readAdvConfiguredCount = advReadFields.filter(isFieldConfigured).length;
    const readPanelHtml = wasSource ? `
      <div class="conn-dialog-tab-panel" data-panel="read" role="tabpanel" ${activeConnectionTab === "read" ? "" : "hidden"}>
        <div class="conn-tab-intro">
          Configure how <strong>${escapeHtml(selected.label)}</strong> files are scanned and parsed by the execution engine.
        </div>
        ${coreReadFields.length ? `<div class="form-grid">${coreReadFields.map(descriptor).join("")}</div>` : ""}
        ${advReadFields.length ? (
          coreReadFields.length === 0
            ? `<div class="form-grid">${advReadFields.map(descriptor).join("")}</div>`
            : `
            <details class="connector-advanced"${readAdvConfiguredCount > 0 ? " open" : ""}>
              <summary class="advanced-summary">
                <span class="advanced-title">
                  <svg class="advanced-chevron" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3l5 5-5 5"/></svg>
                  Advanced ${escapeHtml(selected.label)} read settings
                </span>
                ${readAdvConfiguredCount > 0 ? `<span class="advanced-badge">${readAdvConfiguredCount} customized</span>` : `<span class="advanced-hint">Optional</span>`}
              </summary>
              <div class="form-grid advanced-grid">${advReadFields.map(descriptor).join("")}</div>
            </details>`
        ) : ""}
        ${!readFields.length ? `<p class="field-help">No additional read settings required for ${escapeHtml(selected.label)}.</p>` : ""}
      </div>
    ` : "";

    // 4. Schema Panel
    const schemaPanelHtml = `
      <div class="conn-dialog-tab-panel" data-panel="schema" role="tabpanel" ${activeConnectionTab === "schema" ? "" : "hidden"}>
        <div class="conn-tab-intro">
          Define explicit column data types. Inferred types from raw files are automatically applied to any unlisted columns.
        </div>
        <div class="schema-helper-bar">
          <span class="schema-hint-tag">Syntax: <code>column_name:data_type</code></span>
          <span class="schema-hint-chips">
            <span>Common types:</span>
            <code>int64</code> <code>float64</code> <code>utf8</code> <code>boolean</code> <code>date32</code> <code>timestamp(ms, None)</code>
          </span>
        </div>
        <textarea name="columns" class="schema-editor" rows="10" placeholder="customer_id:int64&#10;region:utf8&#10;total_spend:float64&#10;signup_date:date32&#10;is_active:boolean">${escapeHtml((connection?.columns || []).map((column) => `${column.name}:${column.data_type}`).join("\n"))}</textarea>
        <p class="field-help">One column per line. Existing column descriptions and schema inference metadata are preserved on save.</p>
      </div>
    `;

    // 5. Write Panel
    const writeAdvConfiguredCount = advWriteFields.filter(isFieldConfigured).length;
    const writePanelHtml = wasDestination ? `
      <div class="conn-dialog-tab-panel" data-panel="write" role="tabpanel" ${activeConnectionTab === "write" ? "" : "hidden"}>
        <div class="conn-tab-intro">
          Configure destination output location, write mode, compression, and partitioning when exporting to <strong>${escapeHtml(selected.label)}</strong>.
        </div>
        ${coreWriteFields.length ? `<div class="form-grid">${coreWriteFields.map(descriptor).join("")}</div>` : ""}
        ${advWriteFields.length ? (
          coreWriteFields.length === 0
            ? `<div class="form-grid">${advWriteFields.map(descriptor).join("")}</div>`
            : `
            <details class="connector-advanced"${writeAdvConfiguredCount > 0 ? " open" : ""}>
              <summary class="advanced-summary">
                <span class="advanced-title">
                  <svg class="advanced-chevron" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3l5 5-5 5"/></svg>
                  Advanced ${escapeHtml(selected.label)} write settings
                </span>
                ${writeAdvConfiguredCount > 0 ? `<span class="advanced-badge">${writeAdvConfiguredCount} customized</span>` : `<span class="advanced-hint">Optional</span>`}
              </summary>
              <div class="form-grid advanced-grid">${advWriteFields.map(descriptor).join("")}</div>
            </details>`
        ) : ""}
        ${!writeFields.length ? `<p class="field-help">No additional write settings required for ${escapeHtml(selected.label)}.</p>` : ""}
      </div>
    ` : "";

    // 6. Preview Panel (Data Preview or Target Specs)
    const previewPanelHtml = `
      <div class="conn-dialog-tab-panel" data-panel="preview" role="tabpanel" ${activeConnectionTab === "preview" ? "" : "hidden"}>
      </div>
    `;

    // Inject HTML
    dialogFields.innerHTML = `${tabsHtml}${generalPanelHtml}${readPanelHtml}${schemaPanelHtml}${writePanelHtml}${previewPanelHtml}`;

    const renderPreviewPanelContent = () => {
      const panelEl = dialogFields.querySelector('.conn-dialog-tab-panel[data-panel="preview"]');
      if (!panelEl) return;

      if (!wasSource) {
        const outPath = dialogForm.elements.namedItem("option:output_path")?.value || "";
        const writeMode = dialogForm.elements.namedItem("option:write_mode")?.value || "overwrite";
        panelEl.innerHTML = `
          <div class="conn-target-specs-card">
            <div class="conn-target-specs-header">
              <span class="conn-tab-badge">Destination Target</span>
              <h3>${escapeHtml(selected.label)} Destination</h3>
            </div>
            <p class="conn-target-specs-desc">This connection is configured as a write-only target. The destination file or table will be created when an ETL pipeline step outputs to this connection.</p>
            <div class="conn-target-specs-grid">
              <div class="spec-item"><span class="spec-label">Target Format</span><strong>${escapeHtml(selected.label)}</strong></div>
              <div class="spec-item"><span class="spec-label">Target Path</span><code>${escapeHtml(outPath || "(Specify in Write Options)")}</code></div>
              <div class="spec-item"><span class="spec-label">Write Mode</span><strong>${escapeHtml(writeMode)}</strong></div>
            </div>
          </div>
        `;
        return;
      }

      if (isPreviewLoading) {
        panelEl.innerHTML = `
          <div class="conn-preview-loading">
            <span class="spinner" aria-hidden="true"></span>
            <p>Scanning sample records with Apache DataFusion...</p>
          </div>
        `;
        return;
      }

      if (!previewData) {
        panelEl.innerHTML = `
          <div class="conn-preview-idle">
            <div class="conn-preview-empty-icon">📊</div>
            <h3>Preview records before saving</h3>
            <p>Apache DataFusion will scan up to 25 sample rows directly from your file path without registering or modifying your catalog.</p>
            <button type="button" class="primary-button conn-run-preview-btn"><span>⚡ Scan &amp; Preview Rows</span></button>
          </div>
        `;
        panelEl.querySelector(".conn-run-preview-btn")?.addEventListener("click", executeAdhocPreview);
        return;
      }

      if (!previewData.success) {
        const curPath = dialogForm.elements.namedItem("option:path")?.value || "";
        panelEl.innerHTML = `
          <div class="conn-diagnostic-card">
            <div class="conn-diagnostic-title">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3.5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 4.5zm0 7a.875.875 0 110-1.75.875.875 0 010 1.75z"/></svg>
              <span>Could not read sample data</span>
            </div>
            <p class="conn-diagnostic-message">${escapeHtml(previewData.error || "Unknown error")}</p>
            <div class="conn-diagnostic-tips">
              <strong>Troubleshooting suggestions:</strong>
              <ul>
                <li>Verify that the file path exists in your workspace: <code>${escapeHtml(curPath || "(empty path)")}</code></li>
                <li>For CSV files, check delimiter and header settings under <strong>Read Options</strong>.</li>
                <li>For folders, check your file matching glob pattern under <strong>General &gt; Advanced</strong>.</li>
              </ul>
            </div>
            <button type="button" class="secondary-button conn-preview-rescan-btn" style="align-self: flex-start; margin-top: 6px;">
              <span>🔄 Try Again</span>
            </button>
          </div>
        `;
        panelEl.querySelector(".conn-preview-rescan-btn")?.addEventListener("click", executeAdhocPreview);
        return;
      }

      // Success table preview
      const cols = previewData.columns || [];
      const rows = previewData.rows || [];
      const elapsed = previewData.elapsed_ms || 0;
      panelEl.innerHTML = `
        <div class="conn-preview-header">
          <div class="conn-preview-meta">
            <span class="conn-preview-pill"><strong>${rows.length}</strong> rows sampled</span>
            <span class="conn-preview-pill"><strong>${cols.length}</strong> columns</span>
            <span class="conn-preview-pill">⚡ <strong>${elapsed}ms</strong> DataFusion</span>
          </div>
          <button type="button" class="conn-preview-rescan-btn"><span>🔄 Re-scan</span></button>
        </div>
        <div class="conn-preview-table-wrap">
          <table class="conn-preview-table">
            <thead>
              <tr>
                ${cols.map(c => `
                  <th>
                    <div class="th-content">
                      <span class="col-name">${escapeHtml(c.name)}</span>
                      <span class="col-type">${escapeHtml(c.data_type)}</span>
                    </div>
                  </th>
                `).join("")}
              </tr>
            </thead>
            <tbody>
              ${rows.length ? rows.map(r => `
                <tr>
                  ${cols.map(c => `<td>${escapeHtml(formatCell(r[c.name]))}</td>`).join("")}
                </tr>
              `).join("") : `<tr><td colspan="${cols.length || 1}" style="text-align:center; padding: 20px; color: var(--muted);">File contains 0 records.</td></tr>`}
            </tbody>
          </table>
        </div>
      `;
      panelEl.querySelector(".conn-preview-rescan-btn")?.addEventListener("click", executeAdhocPreview);
    };

    renderPreviewPanelContent();

    const switchTab = (targetTab) => {
      activeConnectionTab = targetTab;
      const tabButtons = dialogFields.querySelectorAll(".conn-dialog-tab");
      const panels = dialogFields.querySelectorAll(".conn-dialog-tab-panel");
      tabButtons.forEach((b) => {
        const isSelected = b.dataset.tab === activeConnectionTab;
        b.classList.toggle("active", isSelected);
        b.setAttribute("aria-selected", String(isSelected));
      });
      panels.forEach((p) => {
        p.hidden = p.dataset.panel !== activeConnectionTab;
      });

      // Update footer preview button visibility (hide when on preview tab)
      if (dialogPreviewBtn) {
        if (!wasSource || activeConnectionTab === "preview") {
          dialogPreviewBtn.hidden = true;
        } else {
          dialogPreviewBtn.hidden = false;
        }
      }
    };

    async function executeAdhocPreview() {
      const form = dialogForm;
      const connectorGuid = form.elements.namedItem("connector")?.value || selected.id;
      const connectorDef = connectors.find((item) => item.id === connectorGuid) || selected;
      const options = {};
      for (const field of connectorDef.fields) {
        const input = form.elements.namedItem(`option:${field.name}`);
        if (field.kind === "boolean") {
          options[field.name] = Boolean(input?.checked);
          continue;
        }
        let val = input?.value ?? "";
        if (typeof val === "string") val = val.trim();
        if (field.kind === "number" && val !== "") val = Number(val);
        if (field.kind === "list") val = val ? val.split(/\r?\n/).map((item) => item.trim()).filter(Boolean) : [];
        if (val !== "" && val !== null) options[field.name] = val;
      }

      if (!options.path && wasSource) {
        showNotification("Please specify a file or folder path in the General tab first.");
        switchTab("general");
        form.elements.namedItem("option:path")?.focus();
        return;
      }

      switchTab("preview");
      isPreviewLoading = true;
      renderPreviewPanelContent();

      const rawColumns = String(form.elements.namedItem("columns")?.value || "").trim();
      let parsedColumns = null;
      if (rawColumns) {
        try {
          parsedColumns = rawColumns.split(/\r?\n/).map((line) => {
            const [cName, ...typeParts] = line.split(":");
            return { name: cName.trim(), data_type: typeParts.join(":").trim() };
          }).filter(c => c.name && c.data_type);
        } catch {
          parsedColumns = null;
        }
      }

      try {
        const res = await api("/api/catalog/preview-adhoc", {
          method: "POST",
          body: JSON.stringify({
            connector: connectorGuid,
            options,
            columns: parsedColumns,
            limit: 25,
          }),
        });
        previewData = res;
        if (res.success && res.inferred_columns?.length) {
          // Auto-populate schema if empty
          const colTextarea = form.elements.namedItem("columns");
          if (colTextarea && !colTextarea.value.trim()) {
            colTextarea.value = res.inferred_columns.map(c => `${c.name}:${c.data_type}`).join("\n");
            const schemaTab = dialogFields.querySelector(".conn-dialog-tab[data-tab='schema']");
            if (schemaTab) {
              let b = schemaTab.querySelector(".conn-tab-badge");
              if (!b) {
                b = document.createElement("span");
                b.className = "conn-tab-badge";
                schemaTab.appendChild(b);
              }
              b.textContent = `${res.inferred_columns.length} cols`;
            }
          }
          // Update Preview Tab badge
          const previewTab = dialogFields.querySelector(".conn-dialog-tab[data-tab='preview']");
          if (previewTab) {
            let b = previewTab.querySelector(".conn-tab-badge");
            if (!b) {
              b = document.createElement("span");
              b.className = "conn-tab-badge";
              previewTab.appendChild(b);
            }
            b.textContent = `${res.row_count} rows`;
          }
        }
      } catch (err) {
        previewData = { success: false, error: err.message };
      } finally {
        isPreviewLoading = false;
        renderPreviewPanelContent();
      }
    }

    // Wire Tab Click Handlers
    const tabButtons = dialogFields.querySelectorAll(".conn-dialog-tab");
    tabButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        switchTab(btn.dataset.tab);
      });
    });

    // Wire footer preview button
    if (dialogPreviewBtn) {
      dialogPreviewBtn.hidden = !wasSource || activeConnectionTab === "preview";
      dialogPreviewBtn.onclick = executeAdhocPreview;
    }

    // Keyboard Arrow navigation between tabs
    dialogFields.querySelector(".conn-dialog-tabs")?.addEventListener("keydown", (event) => {
      if (event.target.classList.contains("conn-dialog-tab")) {
        const tabsArr = [...tabButtons];
        const idx = tabsArr.indexOf(event.target);
        if (event.key === "ArrowRight") {
          event.preventDefault();
          const next = tabsArr[(idx + 1) % tabsArr.length];
          next.focus();
          next.click();
        } else if (event.key === "ArrowLeft") {
          event.preventDefault();
          const prev = tabsArr[(idx - 1 + tabsArr.length) % tabsArr.length];
          prev.focus();
          prev.click();
        }
      }
    });

    // Restore previous field values
    for (const [name, value] of Object.entries(previousValues)) {
      if (name === "connector") continue;
      const control = dialogForm.elements.namedItem(name);
      if (!control) continue;
      if (control.type === "checkbox") control.checked = Boolean(value);
      else control.value = value;
    }
  };

  openEditor({
    title: connection ? "Edit connection" : "Add connection",
    fields: "",
    onSubmit: async (formData) => {
      const form = dialogForm;
      const connectorGuid = formData.get("connector");
      const connectorDefinition = connectors.find((item) => item.id === connectorGuid);
      const options = {};
      for (const field of connectorDefinition.fields) {
        const input = form.elements.namedItem(`option:${field.name}`);
        if (field.kind === "boolean") {
          options[field.name] = Boolean(input?.checked);
          continue;
        }
        let value = formData.get(`option:${field.name}`);
        if (typeof value === "string") value = value.trim();
        if (field.kind === "number" && value !== "") value = Number(value);
        if (field.kind === "list") value = value ? value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean) : [];
        if (field.name === "column_specific_options" && value) {
          try {
            value = JSON.parse(value);
          } catch (error) {
            throw new Error(`Per-column Parquet options must be valid JSON: ${error.message}`);
          }
          if (!value || Array.isArray(value) || typeof value !== "object") {
            throw new Error("Per-column Parquet options must be a JSON object.");
          }
        }
        if (value !== "" && value !== null) options[field.name] = value;
      }
      const body = {
        name: String(formData.get("name") || "").trim(),
        folder_id: String(formData.get("folder_id") || ""),
        connector: connectorGuid,
        is_source: form.elements.namedItem("is_source").checked,
        is_destination: form.elements.namedItem("is_destination").checked,
        description: String(formData.get("description") || "").trim(),
        options,
      };
      const rawColumns = String(formData.get("columns") || "").trim();
      if (rawColumns) {
        body.columns = rawColumns.split(/\r?\n/).map((line) => {
          const [name, ...typeParts] = line.split(":");
          const data_type = typeParts.join(":").trim();
          if (!name.trim() || !data_type) throw new Error(`Invalid schema column: ${line}`);
          const existing = connection?.columns?.find((column) => column.name === name.trim());
          return { ...(existing || {}), name: name.trim(), data_type, nullable: existing?.nullable ?? true };
        });
      } else if (connection) {
        body.columns = [];
      }
      const endpoint = connection
        ? `/api/catalog/connections/${encodeURIComponent(connection.id)}`
        : `/api/catalog/folders/${encodeURIComponent(body.folder_id)}/connections`;
      await api(endpoint, { method: connection ? "PUT" : "POST", body: JSON.stringify(body) });
      selectedConnectionId = connection?.id || null;
      activeDetailTab = "Overview";
      closeEditor();
      await refreshCatalog();
    },
  });
  renderFields(initialConnector.id);
  connectionEditorRenderer = renderFields;
}

function promptName(title, label, value, onSubmit) {
  openEditor({
    title,
    fields: `<div class="form-grid">${textField("name", label, value, "", { required: true })}</div>`,
    onSubmit,
  });
}

function toFormData(form) {
  return new FormData(form);
}

async function handleTreeAction(button) {
  const action = button.dataset.action;
  const folderId = button.dataset.folderId;
  const connectionId = button.dataset.connectionId;
  if (action === "add-connection") {
    connectionEditor(null, folderId);
  } else if (action === "edit-connection") {
    connectionEditor(findConnection(connectionId));
  } else if (action === "rename-folder") {
    const folder = activeCatalog.catalog.folders.find((item) => item.id === folderId);
    promptName("Rename folder", "Folder name", folder.name, async (data) => {
      await api(`/api/catalog/folders/${encodeURIComponent(folderId)}`, { method: "PUT", body: JSON.stringify({ name: data.get("name") }) });
      closeEditor();
      await refreshCatalog();
    });
  } else if (action === "delete-folder") {
    const folder = activeCatalog.catalog.folders.find((item) => item.id === folderId);
    if (!window.confirm(`Delete folder "${folder.name}"? It must be empty, and at least one folder must remain.`)) return;
    await api(`/api/catalog/folders/${encodeURIComponent(folderId)}`, { method: "DELETE" });
    await refreshCatalog();
  } else if (action === "delete-connection") {
    const connection = findConnection(connectionId);
    if (!window.confirm(`Delete connection "${connection.name}"?`)) return;
    await api(`/api/catalog/connections/${encodeURIComponent(connectionId)}`, { method: "DELETE" });
    if (selectedConnectionId === connectionId) selectedConnectionId = null;
    await refreshCatalog();
  }
}

async function loadPreview(connectionId) {
  const target = document.querySelector("#preview-result");
  target.innerHTML = '<p class="loading-state">Loading preview…</p>';
  const connection = findConnection(connectionId);
  const connName = connection ? connection.name : "source";
  showBackgroundTask({ id: "preview-scan", title: `Scanning preview for '${connName}'...`, status: "running" });
  try {
    const result = await api(`/api/catalog/connections/${encodeURIComponent(connectionId)}/preview`);
    dismissBackgroundTask("preview-scan");
    if (!result.columns.length) {
      target.innerHTML = '<div class="empty-state"><strong>No columns returned</strong><p>The source scan returned no schema.</p></div>';
      return;
    }
    target.innerHTML = `<div class="preview-scroll"><table class="catalog-table"><thead><tr>${result.columns.map((column) => `<th>${escapeHtml(column.name)}<small>${escapeHtml(column.data_type)}</small></th>`).join("")}</tr></thead>
      <tbody>${result.rows.length ? result.rows.map((row) => `<tr>${result.columns.map((column) => `<td>${escapeHtml(formatCell(row[column.name]))}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${result.columns.length}" class="empty-table">No rows found.</td></tr>`}</tbody></table></div>
      <div class="preview-footer-bar">
        <p class="preview-caption">${result.rows.length} of up to ${result.row_limit} rows</p>
        <button class="primary-button compact-btn" id="query-preview-in-pipeline-btn" data-connection-name="${escapeHtml(connName)}" title="Query this source in a new pipeline">
          <svg viewBox="0 0 24 24" aria-hidden="true" style="width:13px;height:13px;margin-right:4px;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          Query in Pipeline
        </button>
      </div>`;
  } catch (err) {
    dismissBackgroundTask("preview-scan");
    throw err;
  }
}

function formatCell(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function activateEditor() {
  dialogForm.addEventListener(
    "invalid",
    (event) => {
      const panel = event.target.closest(".conn-dialog-tab-panel");
      if (panel && panel.hidden) {
        const targetTab = panel.dataset.panel;
        if (targetTab) {
          const tabs = dialogFields.querySelectorAll(".conn-dialog-tab");
          const panels = dialogFields.querySelectorAll(".conn-dialog-tab-panel");
          tabs.forEach((btn) => {
            const isSelected = btn.dataset.tab === targetTab;
            btn.classList.toggle("active", isSelected);
            btn.setAttribute("aria-selected", String(isSelected));
          });
          panels.forEach((p) => {
            p.hidden = p.dataset.panel !== targetTab;
          });
        }
      }
    },
    true
  );

  dialogForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!editorHandler) return;
    const saveButton = document.querySelector("#dialog-save");
    saveButton.disabled = true;
    dialogStatus.textContent = "";
    try {
      await editorHandler(toFormData(dialogForm));
    } catch (error) {
      dialogStatus.textContent = error.message;
    } finally {
      saveButton.disabled = false;
    }
  });
}

for (const tab of moduleTabs) {
  tab.addEventListener("click", () => {
    switchToModule(tab.dataset.module);
  });
}

themeToggle.addEventListener("click", async () => {
  themeToggle.disabled = true;
  const nextTheme = themeRoot.dataset.theme === "light" ? "dark" : "light";
  try {
    applyState(await updatePreferences({ theme: nextTheme }));
  } catch (error) {
    console.error(error);
  } finally {
    themeToggle.disabled = false;
  }
});

catalogTree.addEventListener("click", async (event) => {
  const folderToggle = event.target.closest("[data-toggle-folder]");
  if (folderToggle) {
    const folderId = folderToggle.dataset.toggleFolder;
    if (collapsedFolders.has(folderId)) collapsedFolders.delete(folderId);
    else collapsedFolders.add(folderId);
    renderCatalogTree();
    return;
  }
  const actionButton = event.target.closest("[data-action]");
  if (actionButton) {
    try {
      await handleTreeAction(actionButton);
    } catch (error) {
      window.alert(error.message);
    }
    return;
  }
  const connectionButton = event.target.closest("[data-connection-id]");
  if (connectionButton) {
    try {
      await selectConnection(connectionButton.dataset.connectionId);
    } catch (error) {
      window.alert(error.message);
    }
  } else if (event.target.closest("#add-folder-button")) {
    promptName("Create folder", "Folder name", "", async (data) => {
      await api("/api/catalog/folders", { method: "POST", body: JSON.stringify({ name: data.get("name") }) });
      closeEditor();
      await refreshCatalog();
    });
  } else {
    const folderButton = event.target.closest(".folder-select");
    if (folderButton) {
      selectFolder(folderButton.dataset.folderId);
    }
  }
});

catalogSummary.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-connection-id]");
  if (!button) return;
  try {
    await selectConnection(button.dataset.connectionId);
  } catch (error) {
    window.alert(error.message);
  }
});

catalogSearch.addEventListener("input", renderCatalogTree);
if (addConnectionButton) {
  addConnectionButton.addEventListener("click", () => connectionEditor(null, selectedFolderId));
}
document.querySelector("#rename-catalog-button").addEventListener("click", () => {
  promptName("Rename catalog", "Catalog name", activeCatalog.catalog.name, async (data) => {
    await api("/api/catalog/name", { method: "PUT", body: JSON.stringify({ name: data.get("name") }) });
    closeEditor();
    await refreshCatalog();
  });
});
document.querySelector("#switch-catalog-button").addEventListener("click", async () => {
  try {
    const catalogs = await api("/api/catalogs");
    openEditor({
      title: "Open or create catalog",
      submitLabel: "Open / create",
      fields: `<div class="form-grid">
        <label class="form-field"><span>Open existing catalog</span><select name="filename">${catalogs.items.map((filename) => `<option value="${escapeHtml(filename)}" ${filename === catalogs.active ? "selected" : ""}>${escapeHtml(filename)}</option>`).join("")}</select></label>
        ${textField("new_catalog_name", "Or open/create by name", "", "e.g. Finance", {
          help: "An existing catalog with this name opens; otherwise a new catalog is created.",
        })}
      </div>`,
      onSubmit: async (data) => {
        const name = String(data.get("new_catalog_name") || "").trim();
        if (name) {
          await api("/api/catalogs", { method: "POST", body: JSON.stringify({ name }) });
        } else {
          await api("/api/catalogs/active", { method: "PUT", body: JSON.stringify({ filename: data.get("filename") }) });
        }
        selectedConnectionId = null;
        selectedFolderId = null;
        closeEditor();
        await refreshCatalog();
      },
    });
  } catch (error) {
    window.alert(error.message);
  }
});
document.querySelector("#catalog-file-title").addEventListener("click", selectCatalog);
document.querySelector("#catalog-code-button").addEventListener("click", () => {
  if (addConnectionButton) addConnectionButton.hidden = true;
  catalogSummary.hidden = true;
  catalogDetail.hidden = true;
  codePanel.hidden = false;
});
document.querySelector("#save-catalog-yaml").addEventListener("click", async () => {
  const status = document.querySelector("#catalog-code-status");
  try {
    activeCatalog = await api("/api/catalog", { method: "PUT", body: JSON.stringify({ content: document.querySelector("#catalog-yaml").value }) });
    selectedConnectionId = null;
    selectedFolderId = null;
    status.textContent = "Catalog YAML saved.";
    status.classList.remove("is-error");
    renderCatalogTree();
    renderCatalogSummary();
    document.querySelector("#catalog-file-name").textContent = activeCatalog.catalog.name;
    showCatalogOverview();
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("is-error");
  }
});
catalogDetail.addEventListener("click", async (event) => {
  const detailTab = event.target.closest("[data-detail-tab]");
  if (detailTab) {
    activeDetailTab = detailTab.dataset.detailTab;
    try {
      await renderConnectionDetail(selectedConnectionId);
    } catch (error) {
      window.alert(error.message);
    }
    return;
  }
  const actionButton = event.target.closest("[data-action]");
  if (actionButton) {
    try {
      await handleTreeAction(actionButton);
    } catch (error) {
      window.alert(error.message);
    }
    return;
  }
  const connectionButton = event.target.closest(".table-link[data-connection-id]");
  if (connectionButton) {
    try {
      await selectConnection(connectionButton.dataset.connectionId);
    } catch (error) {
      window.alert(error.message);
    }
    return;
  }
  const queryBtn = event.target.closest("#query-in-pipeline-btn, #query-preview-in-pipeline-btn");
  if (queryBtn) {
    const connName = queryBtn.dataset.connectionName;
    if (connName) {
      switchToModule("ETL");
      await createNewPipelineInMemory("default", `SELECT * FROM ${connName} LIMIT 100;\n`, `query_${connName}`, activeCatalog?.filename);
      showNotification(`Created pipeline querying source '${connName}'`);
    }
    return;
  }
  if (event.target.closest("#infer-schema-button")) {
    const button = document.querySelector("#infer-schema-button");
    button.disabled = true;
    button.textContent = "Inferring…";
    showBackgroundTask({ id: "infer-schema", title: "Inferring schema from source...", status: "running" });
    try {
      await api(`/api/catalog/connections/${encodeURIComponent(selectedConnectionId)}/infer-schema`, { method: "POST", body: "{}" });
      dismissBackgroundTask("infer-schema");
      showBackgroundTask({ id: "infer-schema", title: "Schema inferred successfully", status: "success", autoDismissMs: 3000 });
      await refreshCatalog();
      activeDetailTab = "Schema";
      await renderConnectionDetail(selectedConnectionId);
    } catch (error) {
      dismissBackgroundTask("infer-schema");
      window.alert(error.message);
    }
    return;
  }
  if (event.target.closest("#load-preview-button")) {
    try {
      await loadPreview(selectedConnectionId);
    } catch (error) {
      document.querySelector("#preview-result").innerHTML = `<div class="empty-state is-error"><strong>Preview failed</strong><p>${escapeHtml(error.message)}</p></div>`;
    }
    return;
  }
  if (event.target.closest("#save-column-descriptions")) {
    const connection = findConnection(selectedConnectionId);
    const columns = connection.columns.map((column) => ({
      ...column,
      description: document.querySelector(`[data-column-id="${CSS.escape(column.id)}"]`)?.value || "",
    }));
    try {
      await api(`/api/catalog/connections/${encodeURIComponent(selectedConnectionId)}`, { method: "PUT", body: JSON.stringify({ columns }) });
      await refreshCatalog();
      activeDetailTab = "Schema";
      await renderConnectionDetail(selectedConnectionId);
    } catch (error) {
      window.alert(error.message);
    }
  }
});
document.querySelector("#dialog-close").addEventListener("click", closeEditor);
document.querySelector("#dialog-cancel").addEventListener("click", closeEditor);
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) closeEditor();
});
dialogFields.addEventListener("change", (event) => {
  if (!connectionEditorRenderer || !["connector", "is_source", "is_destination"].includes(event.target.name)) return;
  const previousValues = {};
  for (const control of dialogForm.elements) {
    if (control.name && control.name !== "connector") {
      previousValues[control.name] = control.type === "checkbox" ? control.checked : control.value;
    }
  }
  const connector = dialogForm.elements.namedItem("connector")?.value;
  connectionEditorRenderer(connector, previousValues);
});
activateEditor();

// ==========================================
// ETL Module Controller & Logic
// ==========================================

const etlExplorer = document.querySelector("#etl-explorer");
const etlTree = document.querySelector("#etl-tree");
const etlSearch = document.querySelector("#etl-search");
const etlPipelineCount = document.querySelector("#etl-pipeline-count");
const etlNewFolderButton = document.querySelector("#etl-new-folder-button");
const etlNewPipelineButton = document.querySelector("#etl-new-pipeline-button");
const etlRefreshTreeButton = document.querySelector("#etl-refresh-tree-button");

const etlModule = document.querySelector("#etl-module");
const etlCrumbFolder = document.querySelector("#etl-crumb-folder");
const etlPipelineTitle = document.querySelector("#etl-pipeline-title");
const etlPipelineSubtitle = document.querySelector("#etl-pipeline-subtitle");
const etlSaveButton = document.querySelector("#etl-save-button");
const etlRunButton = document.querySelector("#etl-run-button");
const etlValidateButton = document.querySelector("#etl-validate-button");
const etlDocFormatSelect = document.querySelector("#etl-doc-format-select");
const etlDocsButton = document.querySelector("#etl-docs-button");

const etlRunBanner = document.querySelector("#etl-run-banner");
const etlRunBannerBody = document.querySelector("#etl-run-banner-body");
const etlRunStatusIndicator = document.querySelector("#etl-run-status-indicator");
const etlRunStatusTitle = document.querySelector("#etl-run-status-title");
const etlRunStatusMeta = document.querySelector("#etl-run-status-meta");
const etlRefreshRunButton = document.querySelector("#etl-refresh-run-button");
const etlCloseRunButton = document.querySelector("#etl-close-run-button");

const etlValidationBanner = document.querySelector("#etl-validation-banner");
const etlValidationIndicator = document.querySelector("#etl-validation-indicator");
const etlValidationText = document.querySelector("#etl-validation-text");
const etlValidationDetails = document.querySelector("#etl-validation-details");
const etlCloseValidationButton = document.querySelector("#etl-close-validation-button");

const etlFolderSelect = document.querySelector("#etl-folder-select");
const etlPipelineNameInput = document.querySelector("#etl-pipeline-name-input");
const etlCatalogSelect = document.querySelector("#etl-catalog-select");
const etlCatalogDesc = document.querySelector("#etl-catalog-desc");
const etlPipelineDescription = document.querySelector("#etl-pipeline-description");

const etlStepTabs = document.querySelector("#etl-step-tabs");
const etlAddStepButton = document.querySelector("#etl-add-step-button");
const etlStepNameInput = document.querySelector("#etl-step-name-input");
const destinationsChips = document.querySelector("#destinations-chips");
const destinationsAddSelect = document.querySelector("#destinations-add-select");
const etlStepTemporaryCheck = document.querySelector("#etl-step-temporary-check");
const etlStepDescInput = document.querySelector("#etl-step-desc-input");
const etlTabSql = document.querySelector("#etl-tab-sql");
const etlSqlInsertTableSelect = document.querySelector("#etl-sql-insert-table-select");
const etlSqlInsertTableBtn = document.querySelector("#etl-sql-insert-table-btn");
const etlTabNotes = document.querySelector("#etl-tab-notes");
const etlEditorWorkspace = document.querySelector("#etl-editor-workspace");
const sqlEditorContainer = document.querySelector("#sql-editor-container");
const etlEditorSplitter = document.querySelector("#etl-editor-splitter");
const notesEditorContainer = document.querySelector("#notes-editor-container");
const etlNotesCloseBtn = document.querySelector("#etl-notes-close-btn");
const etlNotesBadge = document.querySelector("#etl-notes-badge");
const notesCharCount = document.querySelector("#notes-char-count");

const etlSqlTextarea = document.querySelector("#etl-sql-textarea");
const sqlLineNumbers = document.querySelector("#sql-line-numbers");
const etlSqlStatusIndicator = document.querySelector("#etl-sql-status-indicator");
const etlSqlStatusLabel = document.querySelector("#etl-sql-status-label");
const etlSqlHints = document.querySelector("#etl-sql-hints");
const etlSqlSchemaTbody = document.querySelector("#etl-sql-schema-tbody");

let etlPipelines = [];
let etlFolders = [];
let selectedPipelineKey = null;
let activePipeline = null;
let activeStepIndex = 0;
let sqlValidateTimer = null;
const collapsedEtlFolders = new Set();
let activeRunData = null;
let customLeftRatio = null; // Percentage width for SQL pane when split
let isDraggingSplitter = false;

async function loadPipelineCatalog(filename) {
  const target = filename || activeCatalog?.filename || "default.yaml";
  if (activeCatalog && activeCatalog.filename === target) {
    etlActiveCatalog = activeCatalog;
    pipelineCatalogCache.set(target, activeCatalog);
    return activeCatalog;
  }
  if (pipelineCatalogCache.has(target)) {
    etlActiveCatalog = pipelineCatalogCache.get(target);
    return etlActiveCatalog;
  }
  try {
    const data = await api(`/api/catalog?filename=${encodeURIComponent(target)}`);
    pipelineCatalogCache.set(target, data);
    etlActiveCatalog = data;
    return data;
  } catch (err) {
    console.warn("Failed to load catalog for pipeline:", target, err);
    etlActiveCatalog = activeCatalog || null;
    return etlActiveCatalog;
  }
}

async function refreshETL(preferredKey) {
  try {
    const [pipelineRes, catalogRes] = await Promise.all([
      api("/api/pipelines"),
      api("/api/catalogs"),
    ]);

    etlFolders = pipelineRes.folders || [];
    etlPipelines = pipelineRes.items || [];

    etlPipelineCount.textContent = `${etlFolders.length} folders · ${etlPipelines.length} pipelines`;

    const catalogs = catalogRes.items || ["default.yaml"];
    etlCatalogSelect.innerHTML = catalogs
      .map((cat) => `<option value="${escapeHtml(cat)}">${escapeHtml(cat)}</option>`)
      .join("");

    renderETLTree();

    const targetKey =
      preferredKey ||
      selectedPipelineKey ||
      (etlPipelines.length > 0 ? `${etlPipelines[0].folder}/${etlPipelines[0].name}` : null);

    if (targetKey) {
      await selectPipeline(targetKey);
    } else {
      await createNewPipelineInMemory();
    }
  } catch (error) {
    console.error("Failed to load pipelines:", error);
  }
}

async function createNewPipelineInMemory(initialFolder = "default", initialSql = null, initialName = null, initialCatalog = null) {
  const folder = etlFolders.includes(initialFolder) ? initialFolder : (etlFolders[0] || "default");
  const pipelineName = initialName || "new_pipeline";
  const defaultSql = initialSql || "SELECT 1 AS sample_col";
  const defaultCatalog = initialCatalog || activeCatalog?.filename || "default.yaml";
  activePipeline = {
    id: crypto.randomUUID(),
    name: pipelineName,
    folder: folder,
    catalog: defaultCatalog,
    description: initialSql ? `Pipeline querying ${initialName || "source"}` : "",
    steps: [
      {
        id: crypto.randomUUID(),
        name: "step_1",
        description: "",
        sql: defaultSql,
        destinations: [],
        keep_temporary: true,
      },
    ],
  };
  selectedPipelineKey = `${activePipeline.folder}/${activePipeline.name}`;
  activeStepIndex = 0;
  await loadPipelineCatalog(defaultCatalog);
  populatePipelineForm();
}

async function selectPipeline(keyOrId) {
  try {
    const pipelineData = await api(`/api/pipelines/item/${encodeURI(keyOrId)}`);
    activePipeline = JSON.parse(JSON.stringify(pipelineData));
    selectedPipelineKey = `${activePipeline.folder}/${activePipeline.name}`;
    activeStepIndex = 0;
    await loadPipelineCatalog(activePipeline.catalog || "default.yaml");
    populatePipelineForm();
    renderETLTree();

    try {
      const runs = await api(`/api/monitoring/runs?pipeline_id=${encodeURIComponent(activePipeline.id)}&limit=1`);
      if (runs.items && runs.items.length > 0) {
        renderRunTelemetry(runs.items[0], false);
      } else {
        etlRunBanner.hidden = true;
      }
    } catch (_) {
      etlRunBanner.hidden = true;
    }
  } catch (error) {
    console.error("Failed to select pipeline:", error);
    showNotification(`Failed to load pipeline: ${error.message}`);
  }
}

function populatePipelineForm() {
  if (!activePipeline) return;

  const folderOptions = etlFolders
    .map((f) => `<option value="${escapeHtml(f)}" ${f === activePipeline.folder ? "selected" : ""}>${escapeHtml(f)}</option>`)
    .join("");

  etlFolderSelect.innerHTML = folderOptions +
    `<option value="__CREATE_NEW_FOLDER__">+ New folder...</option>`;

  if (!etlFolders.includes(activePipeline.folder)) {
    etlFolderSelect.insertAdjacentHTML(
      "afterbegin",
      `<option value="${escapeHtml(activePipeline.folder)}" selected>${escapeHtml(activePipeline.folder)}</option>`
    );
  }

  etlCrumbFolder.textContent = activePipeline.folder;
  etlPipelineTitle.textContent = activePipeline.name;
  etlPipelineSubtitle.textContent = activePipeline.description || "Use registered connections, build steps, and publish your results.";
  etlPipelineNameInput.value = activePipeline.name;

  const targetCatalog = activePipeline.catalog || activeCatalog?.filename || "default.yaml";
  activePipeline.catalog = targetCatalog;
  if (![...etlCatalogSelect.options].some((opt) => opt.value === targetCatalog)) {
    const opt = document.createElement("option");
    opt.value = targetCatalog;
    opt.textContent = targetCatalog;
    etlCatalogSelect.appendChild(opt);
  }
  etlCatalogSelect.value = targetCatalog;
  etlCatalogDesc.textContent = targetCatalog === "default.yaml" ? "Default catalog" : targetCatalog;
  etlPipelineDescription.value = activePipeline.description || "";

  renderStepTabs();
  renderActiveStep();
}

function toggleNotesEditor(shouldOpen) {
  if (!notesEditorContainer || !sqlEditorContainer) return;
  if (shouldOpen === undefined) {
    shouldOpen = notesEditorContainer.hidden;
  }

  if (shouldOpen) {
    notesEditorContainer.hidden = false;
    if (etlEditorSplitter) etlEditorSplitter.hidden = false;
    const leftRatio = customLeftRatio !== null ? customLeftRatio : 62.5; // 5:3 ratio = 5/8 = 62.5%
    const rightRatio = 100 - leftRatio;
    sqlEditorContainer.style.flex = `${leftRatio} 1 0%`;
    notesEditorContainer.style.flex = `${rightRatio} 1 0%`;
    if (etlTabNotes) {
      etlTabNotes.classList.add("is-active");
      etlTabNotes.setAttribute("aria-pressed", "true");
    }
    if (etlStepDescInput) etlStepDescInput.focus();
  } else {
    notesEditorContainer.hidden = true;
    if (etlEditorSplitter) etlEditorSplitter.hidden = true;
    sqlEditorContainer.style.flex = "1 1 100%";
    if (etlTabNotes) {
      etlTabNotes.classList.remove("is-active");
      etlTabNotes.setAttribute("aria-pressed", "false");
    }
    if (etlSqlTextarea) {
      etlSqlTextarea.focus();
      updateSqlLineNumbers();
    }
  }
}

function renderStepTabs() {
  if (!activePipeline) return;
  if (!activePipeline.steps || activePipeline.steps.length === 0) {
    activePipeline.steps = [
      {
        id: crypto.randomUUID(),
        name: "step_1",
        description: "",
        sql: "SELECT 1 AS sample_col",
        destinations: [],
        keep_temporary: true,
      },
    ];
    activeStepIndex = 0;
  }

  etlStepTabs.innerHTML = activePipeline.steps
    .map((step, idx) => {
      const numStr = String(idx + 1).padStart(2, "0");
      const isActive = idx === activeStepIndex;
      const canRemove = activePipeline.steps.length > 1;
      return `<button class="etl-step-tab${isActive ? " is-active" : ""}" type="button" data-step-index="${idx}">
        <span>${numStr} ${escapeHtml(step.name || "step")}</span>
        ${canRemove ? `<span class="step-remove-btn" title="Remove step" data-remove-step="${idx}">×</span>` : ""}
      </button>`;
    })
    .join("");
}

function renderActiveStep() {
  if (!activePipeline || !activePipeline.steps || !activePipeline.steps[activeStepIndex]) return;
  const step = activePipeline.steps[activeStepIndex];

  etlStepNameInput.value = step.name || "";
  etlStepTemporaryCheck.checked = step.keep_temporary !== false;
  etlStepDescInput.value = step.description || "";
  etlSqlTextarea.value = step.sql || "";

  const descLen = (step.description || "").trim().length;
  if (notesCharCount) {
    notesCharCount.textContent = `${(step.description || "").length} character${(step.description || "").length === 1 ? "" : "s"}`;
  }
  if (etlNotesBadge) {
    etlNotesBadge.hidden = descLen === 0;
  }

  if (notesEditorContainer && !notesEditorContainer.hidden) {
    const leftRatio = customLeftRatio !== null ? customLeftRatio : 62.5;
    sqlEditorContainer.style.flex = `${leftRatio} 1 0%`;
    notesEditorContainer.style.flex = `${100 - leftRatio} 1 0%`;
    if (etlTabNotes) etlTabNotes.classList.add("is-active");
  } else {
    if (sqlEditorContainer) sqlEditorContainer.style.flex = "1 1 100%";
    if (etlTabNotes) etlTabNotes.classList.remove("is-active");
  }
  renderDestinations();
  renderTableInsertDropdown();
  updateSqlLineNumbers();
  triggerValidateSql();
}

function renderTableInsertDropdown() {
  if (!etlSqlInsertTableSelect) return;

  const catalogToUse = etlActiveCatalog || activeCatalog;
  const allSources = (catalogToUse?.catalog?.folders || [])
    .flatMap((f) => f.connections || [])
    .filter((c) => c.is_source !== false && c.name);

  const priorSteps = (activePipeline?.steps || [])
    .slice(0, activeStepIndex)
    .filter((s) => s.name);

  let html = '<option value="">Select table or prior step...</option>';

  if (allSources.length > 0) {
    html += '<optgroup label="Catalog sources">';
    for (const src of allSources) {
      const connLabel = connectors.find((item) => item.id === src.connector)?.label || src.connector || "source";
      html += `<option value="${escapeHtml(src.name)}">${escapeHtml(src.name)} (${escapeHtml(connLabel)})</option>`;
    }
    html += '</optgroup>';
  }

  if (priorSteps.length > 0) {
    html += '<optgroup label="Prior created steps">';
    priorSteps.forEach((s, idx) => {
      html += `<option value="${escapeHtml(s.name)}">Step ${idx + 1}: ${escapeHtml(s.name)}</option>`;
    });
    html += '</optgroup>';
  }

  etlSqlInsertTableSelect.innerHTML = html;
}

function renderDestinations() {
  if (!activePipeline || !activePipeline.steps || !activePipeline.steps[activeStepIndex]) return;
  const step = activePipeline.steps[activeStepIndex];
  step.destinations = step.destinations || [];

  const catalogToUse = etlActiveCatalog || activeCatalog;
  const allDestConns = (catalogToUse?.catalog?.folders || [])
    .flatMap((f) => f.connections)
    .filter((c) => c.is_destination);

  if (step.destinations.length === 0) {
    destinationsChips.innerHTML = '<span class="destinations-empty-tag">None selected (materialized as temporary view)</span>';
  } else {
    destinationsChips.innerHTML = step.destinations
      .map(
        (destName) =>
          `<div class="etl-dest-tab" data-dest-name="${escapeHtml(destName)}">
            <span class="dest-tab-dot"></span>
            <span>${escapeHtml(destName)}</span>
            <button type="button" class="dest-remove-btn" data-remove-dest="${escapeHtml(destName)}" title="Remove destination">×</button>
          </div>`
      )
      .join("");
  }

  const unselected = allDestConns.filter(
    (c) => !step.destinations.includes(c.name) && !step.destinations.includes(c.id)
  );

  const addBtnText = document.querySelector("#destinations-add-btn-text");
  const addWrapper = document.querySelector("#etl-add-dest-wrapper");

  if (unselected.length > 0) {
    destinationsAddSelect.innerHTML =
      `<option value="">+ Add destination (${unselected.length} available)...</option>` +
      unselected
        .map((c) => {
          const connLabel = connectors.find((item) => item.id === c.connector)?.label || c.connector || "sink";
          return `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)} (${escapeHtml(connLabel)})</option>`;
        })
        .join("");
    destinationsAddSelect.disabled = false;
    if (addBtnText) addBtnText.textContent = `Add destination (${unselected.length})`;
    if (addWrapper) addWrapper.style.opacity = "1";
  } else if (allDestConns.length > 0) {
    destinationsAddSelect.innerHTML = `<option value="">All ${allDestConns.length} destinations selected</option>`;
    destinationsAddSelect.disabled = true;
    if (addBtnText) addBtnText.textContent = `All destinations added`;
    if (addWrapper) addWrapper.style.opacity = "0.6";
  } else {
    destinationsAddSelect.innerHTML = `<option value="">No destinations in catalog</option>`;
    destinationsAddSelect.disabled = true;
    if (addBtnText) addBtnText.textContent = `No destinations available`;
    if (addWrapper) addWrapper.style.opacity = "0.6";
  }
}

function renderETLTree() {
  const query = (etlSearch.value || "").trim().toLowerCase();

  const folderMap = new Map();
  for (const f of etlFolders) {
    folderMap.set(f, []);
  }
  for (const p of etlPipelines) {
    if (!folderMap.has(p.folder)) {
      folderMap.set(p.folder, []);
    }
    folderMap.get(p.folder).push(p);
  }

  let html = "";
  for (const [folderName, items] of folderMap.entries()) {
    const matchedItems = items.filter(
      (p) => p.name.toLowerCase().includes(query) || (p.description || "").toLowerCase().includes(query)
    );
    const folderMatches = folderName.toLowerCase().includes(query);

    if (query && !folderMatches && matchedItems.length === 0) continue;

    const displayItems = query && !folderMatches ? matchedItems : items;
    const isCollapsed = collapsedEtlFolders.has(folderName) && !query;

    const itemsHtml = displayItems
      .map((p) => {
        const isSelected = selectedPipelineKey === `${p.folder}/${p.name}`;
        const stepsBadge = p.steps_count ? `<span class="pipeline-step-badge">${p.steps_count} ${p.steps_count === 1 ? "step" : "steps"}</span>` : "";
        return `<div class="tree-row pipeline-row${isSelected ? " is-selected" : ""}" role="treeitem" data-pipeline-key="${escapeHtml(p.folder)}/${escapeHtml(p.name)}">
          <span class="tree-item-icon">${svg.pipeline}</span>
          <button class="tree-label pipeline-select" type="button" data-pipeline-key="${escapeHtml(p.folder)}/${escapeHtml(p.name)}" aria-pressed="${isSelected}">
            <span>${escapeHtml(p.name)}</span>
            ${stepsBadge}
          </button>
          <span class="tree-actions">
            <button class="icon-button tree-action" type="button" title="Duplicate pipeline" aria-label="Duplicate ${escapeHtml(p.name)}" data-action="duplicate-pipeline" data-pipeline-key="${escapeHtml(p.folder)}/${escapeHtml(p.name)}">${svg.copy}</button>
            <button class="icon-button tree-action" type="button" title="Delete pipeline" aria-label="Delete ${escapeHtml(p.name)}" data-action="delete-pipeline" data-pipeline-key="${escapeHtml(p.folder)}/${escapeHtml(p.name)}">${svg.delete}</button>
          </span>
        </div>`;
      })
      .join("");

    html += `<section class="tree-folder${isCollapsed ? " is-collapsed" : ""}" role="treeitem" aria-expanded="${!isCollapsed}">
      <div class="tree-row folder-row">
        <button class="tree-chevron" type="button" data-toggle-etl-folder="${escapeHtml(folderName)}" aria-label="${isCollapsed ? "Expand" : "Collapse"} ${escapeHtml(folderName)}">${svg.chevron}</button>
        <span class="tree-item-icon">${svg.folder}</span>
        <button class="tree-label folder-select" type="button" data-folder-name="${escapeHtml(folderName)}">${escapeHtml(folderName)}</button>
        <span class="tree-actions">
          <button class="icon-button tree-action" type="button" title="New pipeline in folder" aria-label="New pipeline in ${escapeHtml(folderName)}" data-action="add-pipeline-to-folder" data-folder-name="${escapeHtml(folderName)}">${svg.add}</button>
          <button class="icon-button tree-action" type="button" title="Rename folder" aria-label="Rename ${escapeHtml(folderName)}" data-action="rename-etl-folder" data-folder-name="${escapeHtml(folderName)}">${svg.edit}</button>
          <button class="icon-button tree-action" type="button" title="Delete folder" aria-label="Delete ${escapeHtml(folderName)}" data-action="delete-etl-folder" data-folder-name="${escapeHtml(folderName)}">${svg.delete}</button>
        </span>
      </div>
      <div class="tree-children">${itemsHtml || '<p class="tree-empty">No pipelines in this folder.</p>'}</div>
    </section>`;
  }

  etlTree.innerHTML = html || '<p class="tree-empty">No matching pipeline folders found.</p>';
}

function updateSqlLineNumbers() {
  const text = etlSqlTextarea.value || "";
  const lines = text.split("\n").length;
  sqlLineNumbers.textContent = Array.from({ length: lines }, (_, i) => i + 1).join("\n");
}

function triggerValidateSql() {
  clearTimeout(sqlValidateTimer);
  sqlValidateTimer = setTimeout(async () => {
    if (!activePipeline || !activePipeline.steps || !activePipeline.steps[activeStepIndex]) return;
    const currentStep = activePipeline.steps[activeStepIndex];
    const sql = (currentStep.sql || "").trim();
    if (!sql) {
      etlSqlStatusIndicator.className = "status-indicator";
      etlSqlStatusLabel.textContent = "Empty SQL";
      etlSqlHints.hidden = true;
      etlSqlSchemaTbody.innerHTML = '<tr><td colspan="3" class="empty-table">Enter SQL to derive schema.</td></tr>';
      return;
    }

    const priorSteps = activePipeline.steps.slice(0, activeStepIndex).map((s) => ({
      name: s.name,
      sql: s.sql,
    }));

    try {
      const res = await api("/api/pipelines/validate-sql", {
        method: "POST",
        body: JSON.stringify({
          sql: sql,
          catalog_file: activePipeline.catalog || "default.yaml",
          prior_steps: priorSteps,
        }),
      });

      if (res.valid) {
        etlSqlStatusIndicator.className = "status-indicator is-valid";
        etlSqlStatusLabel.textContent = "Plan validated successfully . End result schema as evaluated by the plan is given below";
        etlSqlHints.hidden = true;
        etlSqlHints.innerHTML = "";
        etlSqlSchemaTbody.innerHTML = res.schema
          .map(
            (col) =>
              `<tr><td><strong>${escapeHtml(col.name)}</strong></td><td><code>${escapeHtml(col.data_type)}</code></td><td>${col.nullable ? "Nullable" : "Required"}</td></tr>`
          )
          .join("");
      } else {
        etlSqlStatusIndicator.className = "status-indicator is-invalid";
        etlSqlStatusLabel.textContent = "Plan / syntax error";
        etlSqlHints.hidden = false;
        const hintsList = res.hints && res.hints.length
          ? `<ul style="margin:6px 0 0;padding-left:18px;">${res.hints.map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>`
          : "";
        etlSqlHints.innerHTML = `<strong>DataFusion error:</strong> ${escapeHtml(res.error || "Query planning failed")}${hintsList}`;
        etlSqlSchemaTbody.innerHTML = '<tr><td colspan="3" class="empty-table">Schema unavailable until plan errors are resolved.</td></tr>';
      }
    } catch (err) {
      etlSqlStatusIndicator.className = "status-indicator is-invalid";
      etlSqlStatusLabel.textContent = "Plan check failed";
      etlSqlHints.hidden = false;
      etlSqlHints.textContent = err.message;
    }
  }, 350);
}

function syncCurrentEditorToPipeline() {
  if (!activePipeline) return;
  activePipeline.name = etlPipelineNameInput.value.trim() || activePipeline.name;
  activePipeline.folder = etlFolderSelect.value || activePipeline.folder;
  activePipeline.catalog = etlCatalogSelect.value || "default.yaml";
  activePipeline.description = etlPipelineDescription.value.trim();

  if (activePipeline.steps && activePipeline.steps[activeStepIndex]) {
    const step = activePipeline.steps[activeStepIndex];
    step.name = etlStepNameInput.value.trim() || step.name;
    step.keep_temporary = etlStepTemporaryCheck.checked;
    step.description = etlStepDescInput.value.trim();
    step.sql = etlSqlTextarea.value;
  }
}

async function savePipeline(andRun = false) {
  syncCurrentEditorToPipeline();

  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(activePipeline.name)) {
    window.alert("Pipeline name must contain only letters, numbers, hyphens, and underscores.");
    return;
  }

  for (const step of activePipeline.steps) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(step.name)) {
      window.alert(`Step name '${step.name}' must start with a letter and contain only letters, numbers, and underscores.`);
      return;
    }
  }

  try {
    const saved = await api("/api/pipelines", {
      method: "POST",
      body: JSON.stringify(activePipeline),
    });
    activePipeline = JSON.parse(JSON.stringify(saved));
    selectedPipelineKey = `${activePipeline.folder}/${activePipeline.name}`;
    etlPipelineTitle.textContent = activePipeline.name;
    etlCrumbFolder.textContent = activePipeline.folder;

    await refreshETL(selectedPipelineKey);

    if (andRun) {
      await runPipeline();
    }
  } catch (error) {
    window.alert(`Save failed: ${error.message}`);
  }
}

async function runPipeline() {
  if (!activePipeline) return;
  syncCurrentEditorToPipeline();

  const pipelineName = activePipeline.name;
  etlRunBanner.hidden = false;
  etlRunBanner.className = "etl-run-banner is-running";
  etlRunStatusIndicator.className = "status-indicator is-running";
  etlRunStatusTitle.textContent = "Executing pipeline via Apache DataFusion…";
  etlRunStatusMeta.textContent = `Pipeline: ${pipelineName} · Started at: ${new Date().toLocaleTimeString()}`;
  etlRunBannerBody.innerHTML = '<p class="loading-state">Running stages sequentially, executing SQL transforms and writers…</p>';

  showBackgroundTask({
    id: "pipeline-run",
    title: `Running pipeline: ${pipelineName}...`,
    status: "running",
    actionLabel: "View in ETL",
    onAction: () => switchToModule("ETL"),
  });

  try {
    const runResult = await api("/api/pipelines/run", {
      method: "POST",
      body: JSON.stringify({ pipeline: activePipeline }),
    });
    activeRunData = runResult;
    renderRunTelemetry(runResult, true);
    const durationMs = ((runResult.total_duration_seconds || 0) * 1000).toFixed(0);
    showBackgroundTask({
      id: "pipeline-run",
      title: `Pipeline '${pipelineName}' succeeded (${durationMs}ms)`,
      status: "success",
      actionLabel: "Monitoring",
      onAction: () => {
        if (activePipeline) {
          selectedMonitoringPipeline = {
            id: activePipeline.id,
            name: activePipeline.name,
            folder: activePipeline.folder,
            key: `${activePipeline.folder}/${activePipeline.name}`,
          };
        }
        if (runResult && runResult.run_id) {
          selectedRunId = runResult.run_id;
        }
        switchToModule("Monitoring");
      },
      autoDismissMs: 6000,
    });
  } catch (error) {
    etlRunBanner.className = "etl-run-banner is-failed";
    etlRunStatusIndicator.className = "status-indicator is-failed";
    etlRunStatusTitle.textContent = "Pipeline execution failed";
    etlRunStatusMeta.textContent = `Encountered error during execution`;
    etlRunBannerBody.innerHTML = `<div class="empty-state is-error"><strong>Execution Error</strong><p>${escapeHtml(error.message)}</p></div>`;
    showBackgroundTask({
      id: "pipeline-run",
      title: `Pipeline '${pipelineName}' failed`,
      status: "failed",
      actionLabel: "Details",
      onAction: () => switchToModule("ETL"),
      autoDismissMs: 8000,
    });
  }
}

function renderRunTelemetry(run, scrollIntoView = false) {
  if (!run) return;
  etlRunBanner.hidden = false;
  const isSuccess = run.status === "SUCCESS";
  etlRunBanner.className = `etl-run-banner ${isSuccess ? "is-success" : "is-failed"}`;
  etlRunStatusIndicator.className = `status-indicator ${isSuccess ? "is-success" : "is-failed"}`;
  etlRunStatusTitle.textContent = isSuccess ? "Pipeline executed successfully" : "Pipeline execution failed";

  const durationMs = (run.total_duration_seconds * 1000).toFixed(1);
  const totalRows = (run.steps || []).reduce((acc, s) => acc + (s.rows_processed || 0), 0);
  etlRunStatusMeta.textContent = `Run ID: ${escapeHtml(run.run_id ? run.run_id.slice(0, 8) : "—")} · Duration: ${durationMs}ms · ${totalRows.toLocaleString()} rows processed`;

  let totalWrittenRows = 0;
  for (const s of run.steps || []) {
    for (const d of s.destinations || []) {
      totalWrittenRows += (d.rows_written || 0);
    }
  }

  let bodyHtml = `
    <div class="run-metrics-strip">
      <div class="run-metric-card">
        <span>STATUS</span>
        <strong style="color: ${isSuccess ? "var(--accent-strong)" : "#ef4444"}">${escapeHtml(run.status)}</strong>
      </div>
      <div class="run-metric-card">
        <span>TOTAL TIME</span>
        <strong>${durationMs} ms</strong>
      </div>
      <div class="run-metric-card">
        <span>STAGES</span>
        <strong>${(run.steps || []).length}</strong>
      </div>
      <div class="run-metric-card">
        <span>ROWS PROCESSED</span>
        <strong>${totalRows.toLocaleString()}</strong>
      </div>
      <div class="run-metric-card">
        <span>ROWS WRITTEN</span>
        <strong>${totalWrittenRows.toLocaleString()}</strong>
      </div>
    </div>
  `;

  if (run.error) {
    bodyHtml += `<div class="sql-hints-box" style="margin-top: 10px;">
      <strong>Pipeline Error:</strong> ${escapeHtml(run.error)}
    </div>`;
  }
  if (run.warnings && run.warnings.length > 0) {
    bodyHtml += `<div class="sql-hints-box" style="margin-top: 10px; border-color: #fcd34d; background: #fffbeb; color: #b45309;">
      <strong>Warnings:</strong>
      <ul style="margin: 4px 0 0; padding-left: 18px;">${run.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul>
    </div>`;
  }

  bodyHtml += `
    <div class="run-banner-footer">
      <button class="primary-button compact-btn" id="etl-see-detailed-log-btn" type="button" title="View execution breakdown and detailed logs in Monitoring">
        <svg viewBox="0 0 24 24" aria-hidden="true" style="width:13px;height:13px;margin-right:6px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        View in Monitoring
      </button>
      <button class="secondary-button compact-btn" id="etl-run-view-docs-btn" type="button" title="View documentation for this pipeline">
        <svg viewBox="0 0 24 24" aria-hidden="true" style="width:13px;height:13px;margin-right:6px;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        View Documentation
      </button>
    </div>
  `;

  etlRunBannerBody.innerHTML = bodyHtml;

  const seeDetailedLogBtn = document.querySelector("#etl-see-detailed-log-btn");
  if (seeDetailedLogBtn) {
    seeDetailedLogBtn.addEventListener("click", () => {
      if (activePipeline) {
        selectedMonitoringPipeline = {
          id: activePipeline.id,
          name: activePipeline.name,
          folder: activePipeline.folder,
          key: `${activePipeline.folder}/${activePipeline.name}`,
        };
      }
      if (run && run.run_id) {
        selectedRunId = run.run_id;
      }
      switchToModule("Monitoring");
    });
  }

  const runViewDocsBtn = document.querySelector("#etl-run-view-docs-btn");
  if (runViewDocsBtn) {
    runViewDocsBtn.addEventListener("click", () => {
      if (activePipeline) {
        navigateToDocsForPipeline(activePipeline.folder, activePipeline.name);
      }
    });
  }

  if (scrollIntoView) {
    etlRunBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

async function refreshLatestRunLog() {
  if (!activePipeline) return;
  try {
    const runs = await api(`/api/monitoring/runs?pipeline_id=${encodeURIComponent(activePipeline.id)}&limit=1`);
    if (runs.items && runs.items.length > 0) {
      renderRunTelemetry(runs.items[0], false);
    } else {
      window.alert("No execution runs found for this pipeline yet.");
    }
  } catch (err) {
    window.alert(`Could not read run log: ${err.message}`);
  }
}

async function validateEntirePipeline() {
  if (!activePipeline) return;
  syncCurrentEditorToPipeline();

  etlValidationBanner.hidden = false;
  etlValidationDetails.hidden = false;
  etlValidationIndicator.className = "status-indicator is-running";
  etlValidationText.textContent = "Running DataFusion pre-flight validation…";
  etlValidationDetails.innerHTML = "<p>Analyzing logical plans, schemas, and destination connections…</p>";

  try {
    const res = await api("/api/pipelines/validate", {
      method: "POST",
      body: JSON.stringify(activePipeline),
    });

    if (res.valid) {
      etlValidationBanner.className = "etl-validation-banner is-valid";
      etlValidationIndicator.className = "status-indicator is-valid";
      etlValidationText.textContent = `All ${res.steps.length} step(s) verified! DataFusion plans and schemas are valid.`;
      const stepHtml = res.steps
        .map(
          (s) =>
            `<div style="margin-bottom:6px;"><strong>✔ Step: ${escapeHtml(s.step_name)}</strong> — ${s.column_count} column(s) inferred.</div>`
        )
        .join("");
      etlValidationDetails.innerHTML = `${stepHtml}
        <div style="margin-top:10px;">
          <button class="primary-button compact-btn" id="etl-validation-run-now-btn" type="button">▶ Run Pipeline Now</button>
        </div>`;
      const runNowBtn = document.querySelector("#etl-validation-run-now-btn");
      if (runNowBtn) {
        runNowBtn.addEventListener("click", () => savePipeline(true));
      }
      etlRunButton.classList.add("btn-cta-ready");
      setTimeout(() => etlRunButton.classList.remove("btn-cta-ready"), 4000);
    } else {
      etlValidationBanner.className = "etl-validation-banner is-invalid";
      etlValidationIndicator.className = "status-indicator is-invalid";
      etlValidationText.textContent = `Pre-flight validation failed in step: ${escapeHtml(res.failed_step || "unknown")}`;
      const hintsHtml = res.hints && res.hints.length
        ? `<ul style="margin:4px 0 0;padding-left:18px;">${res.hints.map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>`
        : "";
      etlValidationDetails.innerHTML = `<div><strong>Error:</strong> ${escapeHtml(res.error || "")}</div>${hintsHtml}`;
    }
  } catch (err) {
    etlValidationBanner.className = "etl-validation-banner is-invalid";
    etlValidationIndicator.className = "status-indicator is-invalid";
    etlValidationText.textContent = "Validation request failed";
    etlValidationDetails.innerHTML = `<div>${escapeHtml(err.message)}</div>`;
  }
}

// Attach ETL DOM Event Listeners
etlSearch.addEventListener("input", renderETLTree);
etlRefreshTreeButton.addEventListener("click", () => refreshETL());

etlNewFolderButton.addEventListener("click", () => {
  promptName("Create pipeline folder", "Folder name", "", async (data) => {
    const name = String(data.get("name") || "").trim();
    if (!name) return;
    await api("/api/pipelines/folders", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    closeEditor();
    await refreshETL();
  });
});

etlNewPipelineButton.addEventListener("click", () => {
  const defaultCatalog = activeCatalog?.filename || "default.yaml";
  const catalogOptions = [...etlCatalogSelect.options];
  const catalogSelectHtml = catalogOptions.length
    ? `<label class="form-field"><span>Catalog file</span><select name="catalog">${catalogOptions.map((opt) => `<option value="${escapeHtml(opt.value)}" ${opt.value === defaultCatalog ? "selected" : ""}>${escapeHtml(opt.textContent)}</option>`).join("")}</select></label>`
    : "";
  openEditor({
    title: "New pipeline",
    fields: `<div class="form-grid">
      <label class="form-field"><span>Folder</span><select name="folder">${etlFolders.map((f) => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join("")}</select></label>
      ${textField("name", "Pipeline name", "", "e.g. daily_aggregation", { required: true })}
      ${catalogSelectHtml}
    </div>`,
    onSubmit: async (data) => {
      const folder = String(data.get("folder") || "default").trim();
      const name = String(data.get("name") || "").trim();
      const catalog = String(data.get("catalog") || defaultCatalog).trim();
      if (!name) return;
      activePipeline = {
        id: crypto.randomUUID(),
        name,
        folder,
        catalog,
        description: "",
        steps: [
          {
            id: crypto.randomUUID(),
            name: "step_1",
            description: "",
            sql: "SELECT 1 AS sample_col",
            destinations: [],
            keep_temporary: true,
          },
        ],
      };
      await api("/api/pipelines", {
        method: "POST",
        body: JSON.stringify(activePipeline),
      });
      closeEditor();
      selectedPipelineKey = `${folder}/${name}`;
      await refreshETL(selectedPipelineKey);
    },
  });
});

etlTree.addEventListener("click", async (event) => {
  const folderToggle = event.target.closest("[data-toggle-etl-folder]");
  if (folderToggle) {
    const folderName = folderToggle.dataset.toggleEtlFolder;
    if (collapsedEtlFolders.has(folderName)) collapsedEtlFolders.delete(folderName);
    else collapsedEtlFolders.add(folderName);
    renderETLTree();
    return;
  }

  const pipelineButton = event.target.closest("[data-pipeline-key]");
  if (pipelineButton && !event.target.closest("[data-action]")) {
    await selectPipeline(pipelineButton.dataset.pipelineKey);
    return;
  }

  const actionButton = event.target.closest("[data-action]");
  if (actionButton) {
    const action = actionButton.dataset.action;
    const folderName = actionButton.dataset.folderName;
    const pipelineKey = actionButton.dataset.pipelineKey;

    if (action === "add-pipeline-to-folder") {
      const defaultCatalog = activeCatalog?.filename || "default.yaml";
      promptName(`New pipeline in ${folderName}`, "Pipeline name", "", async (data) => {
        const name = String(data.get("name") || "").trim();
        if (!name) return;
        const newPipe = {
          id: crypto.randomUUID(),
          name,
          folder: folderName,
          catalog: defaultCatalog,
          description: "",
          steps: [{ id: crypto.randomUUID(), name: "step_1", description: "", sql: "SELECT 1 AS sample_col", destinations: [], keep_temporary: true }],
        };
        await api("/api/pipelines", { method: "POST", body: JSON.stringify(newPipe) });
        closeEditor();
        await refreshETL(`${folderName}/${name}`);
      });
    } else if (action === "rename-etl-folder") {
      promptName("Rename pipeline folder", "Folder name", folderName, async (data) => {
        const newName = String(data.get("name") || "").trim();
        if (!newName || newName === folderName) return;
        await api(`/api/pipelines/folders/${encodeURIComponent(folderName)}`, {
          method: "PUT",
          body: JSON.stringify({ name: newName }),
        });
        closeEditor();
        await refreshETL();
      });
    } else if (action === "delete-etl-folder") {
      if (!window.confirm(`Delete pipeline folder "${folderName}" and its pipelines?`)) return;
      await api(`/api/pipelines/folders/${encodeURIComponent(folderName)}`, { method: "DELETE" });
      await refreshETL();
    } else if (action === "duplicate-pipeline") {
      try {
        const orig = await api(`/api/pipelines/item/${encodeURI(pipelineKey)}`);
        const copyPipe = JSON.parse(JSON.stringify(orig));
        copyPipe.id = crypto.randomUUID();
        copyPipe.name = `${copyPipe.name}_copy`;
        await api("/api/pipelines", { method: "POST", body: JSON.stringify(copyPipe) });
        await refreshETL(`${copyPipe.folder}/${copyPipe.name}`);
      } catch (err) {
        window.alert(`Duplicate failed: ${err.message}`);
      }
    } else if (action === "delete-pipeline") {
      if (!window.confirm(`Delete pipeline "${pipelineKey}"?`)) return;
      await api(`/api/pipelines/item/${encodeURI(pipelineKey)}`, { method: "DELETE" });
      if (selectedPipelineKey === pipelineKey) selectedPipelineKey = null;
      await refreshETL();
    }
  }
});

etlStepTabs.addEventListener("click", (event) => {
  const removeBtn = event.target.closest("[data-remove-step]");
  if (removeBtn) {
    const idx = parseInt(removeBtn.dataset.removeStep, 10);
    if (activePipeline.steps.length <= 1) return;
    if (window.confirm(`Remove step "${activePipeline.steps[idx].name}"?`)) {
      syncCurrentEditorToPipeline();
      activePipeline.steps.splice(idx, 1);
      activeStepIndex = Math.min(activeStepIndex, activePipeline.steps.length - 1);
      renderStepTabs();
      renderActiveStep();
    }
    return;
  }

  const tabBtn = event.target.closest("[data-step-index]");
  if (tabBtn) {
    syncCurrentEditorToPipeline();
    activeStepIndex = parseInt(tabBtn.dataset.stepIndex, 10);
    renderStepTabs();
    renderActiveStep();
  }
});

etlAddStepButton.addEventListener("click", () => {
  if (!activePipeline) {
    createNewPipelineInMemory();
  }
  syncCurrentEditorToPipeline();
  const stepCount = (activePipeline.steps || []).length;
  const newName = `step_${stepCount + 1}`;
  const priorStep = stepCount > 0 ? activePipeline.steps[stepCount - 1] : null;
  const defaultSql = priorStep ? `SELECT * FROM ${priorStep.name} LIMIT 100` : `SELECT 1 AS sample_col`;
  activePipeline.steps.push({
    id: crypto.randomUUID(),
    name: newName,
    description: "",
    sql: defaultSql,
    destinations: [],
    keep_temporary: true,
  });
  activeStepIndex = activePipeline.steps.length - 1;
  renderStepTabs();
  renderActiveStep();
});

destinationsAddSelect.addEventListener("change", () => {
  const val = destinationsAddSelect.value;
  if (!val || !activePipeline?.steps[activeStepIndex]) return;
  const step = activePipeline.steps[activeStepIndex];
  if (!step.destinations.includes(val)) {
    step.destinations.push(val);
    if (etlStepTemporaryCheck) {
      step.keep_temporary = false;
      etlStepTemporaryCheck.checked = false;
    }
    renderDestinations();
  }
  destinationsAddSelect.value = "";
});

destinationsChips.addEventListener("click", (event) => {
  const removeBtn = event.target.closest("[data-remove-dest]");
  if (!removeBtn || !activePipeline?.steps[activeStepIndex]) return;
  const destName = removeBtn.dataset.removeDest;
  const step = activePipeline.steps[activeStepIndex];
  step.destinations = step.destinations.filter((d) => d !== destName);
  if (step.destinations.length === 0 && etlStepTemporaryCheck) {
    step.keep_temporary = true;
    etlStepTemporaryCheck.checked = true;
  }
  renderDestinations();
});

if (etlStepTemporaryCheck) {
  etlStepTemporaryCheck.addEventListener("change", () => {
    if (!activePipeline?.steps[activeStepIndex]) return;
    activePipeline.steps[activeStepIndex].keep_temporary = etlStepTemporaryCheck.checked;
    renderDestinations();
  });
}

etlStepNameInput.addEventListener("input", () => {
  if (!activePipeline?.steps[activeStepIndex]) return;
  activePipeline.steps[activeStepIndex].name = etlStepNameInput.value;
  renderStepTabs();
});

etlPipelineNameInput.addEventListener("input", () => {
  if (!activePipeline) return;
  activePipeline.name = etlPipelineNameInput.value;
  etlPipelineTitle.textContent = etlPipelineNameInput.value || "Untitled";
});

etlFolderSelect.addEventListener("change", async () => {
  if (etlFolderSelect.value === "__CREATE_NEW_FOLDER__") {
    promptName("Create pipeline folder", "Folder name", "", async (data) => {
      const name = String(data.get("name") || "").trim();
      if (!name) {
        etlFolderSelect.value = activePipeline ? activePipeline.folder : (etlFolders[0] || "default");
        return;
      }
      await api("/api/pipelines/folders", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      if (!etlFolders.includes(name)) {
        etlFolders.push(name);
      }
      if (activePipeline) {
        activePipeline.folder = name;
        etlCrumbFolder.textContent = name;
      }
      closeEditor();
      populatePipelineForm();
      renderETLTree();
    });
    return;
  }

  if (activePipeline) {
    activePipeline.folder = etlFolderSelect.value;
    etlCrumbFolder.textContent = activePipeline.folder;
    const origKey = selectedPipelineKey;
    const newKey = `${activePipeline.folder}/${activePipeline.name}`;
    if (origKey && origKey !== newKey) {
      etlPipelineSubtitle.textContent = `Pipeline will be moved to '${activePipeline.folder}' when saved.`;
    } else {
      etlPipelineSubtitle.textContent = activePipeline.description || "Use registered connections, build steps, and publish your results.";
    }
  }
});

if (etlTabSql) {
  etlTabSql.addEventListener("click", () => {
    if (etlSqlTextarea) {
      etlSqlTextarea.focus();
      updateSqlLineNumbers();
    }
  });
}

if (etlSqlInsertTableBtn && etlSqlInsertTableSelect) {
  etlSqlInsertTableBtn.addEventListener("click", () => {
    const tableName = etlSqlInsertTableSelect.value;
    if (!tableName) return;

    const textarea = etlSqlTextarea;
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;
    const currentVal = textarea.value || "";

    const newText = currentVal.substring(0, start) + tableName + currentVal.substring(end);
    textarea.value = newText;
    textarea.selectionStart = textarea.selectionEnd = start + tableName.length;
    textarea.focus();

    if (activePipeline?.steps[activeStepIndex]) {
      activePipeline.steps[activeStepIndex].sql = textarea.value;
    }
    updateSqlLineNumbers();
    triggerValidateSql();
    etlSqlInsertTableSelect.value = "";
  });
}
if (etlTabNotes) {
  etlTabNotes.addEventListener("click", () => toggleNotesEditor());
}
if (etlNotesCloseBtn) {
  etlNotesCloseBtn.addEventListener("click", () => toggleNotesEditor(false));
}

if (etlEditorSplitter) {
  etlEditorSplitter.addEventListener("mousedown", (e) => {
    isDraggingSplitter = true;
    etlEditorSplitter.classList.add("is-dragging");
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  });
}

window.addEventListener("mousemove", (e) => {
  if (!isDraggingSplitter || !etlEditorWorkspace) return;
  const rect = etlEditorWorkspace.getBoundingClientRect();
  const offsetX = e.clientX - rect.left;
  const totalWidth = rect.width;
  if (totalWidth <= 0) return;
  let leftPct = (offsetX / totalWidth) * 100;
  leftPct = Math.max(20, Math.min(80, leftPct));
  const rightPct = 100 - leftPct;
  customLeftRatio = leftPct;
  sqlEditorContainer.style.flex = `${leftPct} 1 0%`;
  notesEditorContainer.style.flex = `${rightPct} 1 0%`;
});

window.addEventListener("mouseup", () => {
  if (isDraggingSplitter) {
    isDraggingSplitter = false;
    if (etlEditorSplitter) etlEditorSplitter.classList.remove("is-dragging");
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
  }
});
if (etlStepDescInput) {
  etlStepDescInput.addEventListener("input", () => {
    if (activePipeline?.steps[activeStepIndex]) {
      activePipeline.steps[activeStepIndex].description = etlStepDescInput.value;
    }
    const len = (etlStepDescInput.value || "").length;
    if (notesCharCount) {
      notesCharCount.textContent = `${len} character${len === 1 ? "" : "s"}`;
    }
    if (etlNotesBadge) {
      etlNotesBadge.hidden = len === 0;
    }
  });
}

etlCatalogSelect.addEventListener("change", async () => {
  if (!activePipeline) return;
  activePipeline.catalog = etlCatalogSelect.value || "default.yaml";
  etlCatalogDesc.textContent = activePipeline.catalog === "default.yaml" ? "Default catalog" : activePipeline.catalog;
  await loadPipelineCatalog(activePipeline.catalog);
  renderTableInsertDropdown();
  renderDestinations();
  triggerValidateSql();
});

etlSqlTextarea.addEventListener("input", () => {
  if (activePipeline?.steps[activeStepIndex]) {
    activePipeline.steps[activeStepIndex].sql = etlSqlTextarea.value;
  }
  updateSqlLineNumbers();
  triggerValidateSql();
});

etlSqlTextarea.addEventListener("scroll", () => {
  sqlLineNumbers.scrollTop = etlSqlTextarea.scrollTop;
});

etlSqlTextarea.addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    event.preventDefault();
    const start = etlSqlTextarea.selectionStart;
    const end = etlSqlTextarea.selectionEnd;
    etlSqlTextarea.value = etlSqlTextarea.value.substring(0, start) + "  " + etlSqlTextarea.value.substring(end);
    etlSqlTextarea.selectionStart = etlSqlTextarea.selectionEnd = start + 2;
    if (activePipeline?.steps[activeStepIndex]) {
      activePipeline.steps[activeStepIndex].sql = etlSqlTextarea.value;
    }
    updateSqlLineNumbers();
    triggerValidateSql();
  }
});

etlSaveButton.addEventListener("click", () => savePipeline(false));
etlRunButton.addEventListener("click", () => savePipeline(true));
etlValidateButton.addEventListener("click", validateEntirePipeline);
if (etlDocsButton) {
  etlDocsButton.addEventListener("click", async () => {
    if (!activePipeline) return;
    syncCurrentEditorToPipeline();
    const docFormat = etlDocFormatSelect ? etlDocFormatSelect.value : "html";
    const origBtnHtml = etlDocsButton.innerHTML;
    etlDocsButton.disabled = true;
    etlDocsButton.innerHTML = `<span style="font-size:11px;">Generating...</span>`;
    try {
      const result = await api("/api/pipelines/docs", {
        method: "POST",
        body: JSON.stringify({
          pipeline: activePipeline,
          format: docFormat,
        }),
      });
      showNotification(`Documentation saved to: ${result.saved_path}`, 4000);
    } catch (err) {
      console.error("Documentation generation failed:", err);
      showNotification(`Documentation error: ${err.message}`);
    } finally {
      etlDocsButton.disabled = false;
      etlDocsButton.innerHTML = origBtnHtml;
    }
  });
}
etlRefreshRunButton.addEventListener("click", refreshLatestRunLog);
etlCloseRunButton.addEventListener("click", () => { etlRunBanner.hidden = true; });
etlCloseValidationButton.addEventListener("click", () => { etlValidationBanner.hidden = true; });

// ==========================================
// Monitoring Module Controller & Logic
// ==========================================

const monitoringExplorer = document.querySelector("#monitoring-explorer");
const monitoringTree = document.querySelector("#monitoring-tree");
const monitoringSearch = document.querySelector("#monitoring-search");
const monitoringRunsCount = document.querySelector("#monitoring-runs-count");
const monitoringRefreshBtn = document.querySelector("#monitoring-refresh-btn");
const monitoringStatusPills = [...document.querySelectorAll(".monitoring-filter-pills .status-filter-pill")];

const monitoringModule = document.querySelector("#monitoring-module");
const monEmptyState = document.querySelector("#mon-empty-state");
const monViewerContainer = document.querySelector("#mon-viewer-container");
const monitoringPageRefreshBtn = document.querySelector("#monitoring-page-refresh-btn");
const monCrumbWorkspace = document.querySelector("#mon-crumb-workspace");
const monCrumbPipelineWrap = document.querySelector("#mon-crumb-pipeline-wrap");
const monCrumbPipeline = document.querySelector("#mon-crumb-pipeline");
const monHeaderTitle = document.querySelector("#mon-header-title");
const monHeaderSubtitle = document.querySelector("#mon-header-subtitle");
const monOpenInEtlHeaderBtn = document.querySelector("#mon-open-in-etl-header-btn");

const monStatTotal = document.querySelector("#mon-stat-total");
const monStatSuccessRate = document.querySelector("#mon-stat-success-rate");
const monStatRows = document.querySelector("#mon-stat-rows");
const monStatAvgDur = document.querySelector("#mon-stat-avg-dur");

const monFilterStatus = document.querySelector("#mon-filter-status");
const monFilterDatePreset = document.querySelector("#mon-filter-date-preset");
const monCustomDateWrap = document.querySelector("#mon-custom-date-wrap");
const monFilterDateFrom = document.querySelector("#mon-filter-date-from");
const monFilterDateTo = document.querySelector("#mon-filter-date-to");
const monFilterSearch = document.querySelector("#mon-filter-search");
const monFilterLimit = document.querySelector("#mon-filter-limit");
const monFilterResetBtn = document.querySelector("#mon-filter-reset-btn");

const monitoringRunsTbody = document.querySelector("#monitoring-runs-tbody");

const monitoringRunDetailCard = document.querySelector("#monitoring-run-detail-card");
const monDetailIndicator = document.querySelector("#mon-detail-indicator");
const monDetailTitle = document.querySelector("#mon-detail-title");
const monDetailStatusBadge = document.querySelector("#mon-detail-status-badge");
const monDetailMeta = document.querySelector("#mon-detail-meta");
const monDetailCopyIdBtn = document.querySelector("#mon-detail-copy-id-btn");
const monDetailOpenEtlBtn = document.querySelector("#mon-detail-open-etl-btn");
const monDetailCloseBtn = document.querySelector("#mon-detail-close-btn");

const monTabInferred = document.querySelector("#mon-tab-inferred");
const monTabLogs = document.querySelector("#mon-tab-logs");
const monTabRaw = document.querySelector("#mon-tab-raw");
const monTabLogCount = document.querySelector("#mon-tab-log-count");

const monSectionInferred = document.querySelector("#mon-section-inferred");
const monSectionLogs = document.querySelector("#mon-section-logs");
const monSectionRaw = document.querySelector("#mon-section-raw");
const monRawLogPath = document.querySelector("#mon-raw-log-path");
const monRawCopyBtn = document.querySelector("#mon-raw-copy-btn");
const monRawJsonCode = document.querySelector("#mon-raw-json-code");

let selectedMonitoringPipeline = null; // null = all, or { id, name, folder, key }
let monitoringRuns = [];
let allPipelinesForMonitoring = [];
let monitoringPipelineFolders = [];
let selectedRunId = null;
let selectedRunData = null;
let activeMonSection = "inferred";
let activeLogLevelFilter = "ALL";
let logFilterSearchText = "";
const collapsedMonitoringFolders = new Set();

async function refreshMonitoring() {
  try {
    if (monCrumbWorkspace && currentState?.workspace) {
      monCrumbWorkspace.textContent = currentState.workspace.split(/[\\/]/).pop() || "WORKSPACE";
    }
    const pipelinesResult = await api("/api/pipelines");
    allPipelinesForMonitoring = pipelinesResult.items || [];
    monitoringPipelineFolders = pipelinesResult.folders || [];

    renderMonitoringTree();

    if (selectedMonitoringPipeline) {
      await showMonitoringForSelectedPipeline();
    } else {
      showMonitoringEmptyState();
    }
  } catch (error) {
    console.error("Failed to load monitoring:", error);
    showNotification(`Monitoring load error: ${error.message}`);
  }
}

function showMonitoringEmptyState() {
  selectedMonitoringPipeline = null;
  selectedRunId = null;
  selectedRunData = null;
  monitoringRuns = [];

  if (monEmptyState) monEmptyState.hidden = false;
  if (monViewerContainer) monViewerContainer.hidden = true;
  if (monCrumbPipelineWrap) monCrumbPipelineWrap.hidden = true;
  if (monOpenInEtlHeaderBtn) monOpenInEtlHeaderBtn.hidden = true;
  if (monitoringRunsCount) monitoringRunsCount.textContent = "Select a pipeline";
  if (monitoringRunDetailCard) monitoringRunDetailCard.hidden = true;

  renderMonitoringTree();
}

async function showMonitoringForSelectedPipeline() {
  if (!selectedMonitoringPipeline) {
    showMonitoringEmptyState();
    return;
  }

  if (monEmptyState) monEmptyState.hidden = true;
  if (monViewerContainer) monViewerContainer.hidden = false;

  const { id: pId, key: pKey, folder: pFolder, name: pName } = selectedMonitoringPipeline;
  if (monCrumbPipelineWrap) monCrumbPipelineWrap.hidden = false;
  if (monCrumbPipeline) monCrumbPipeline.textContent = pKey || pName;
  if (monHeaderTitle) monHeaderTitle.textContent = pName;
  if (monHeaderSubtitle) {
    monHeaderSubtitle.textContent = `Reading execution log from logs/pipelines/${pFolder ? pFolder + "/" : ""}${pId}.json`;
  }
  if (monOpenInEtlHeaderBtn) monOpenInEtlHeaderBtn.hidden = false;

  renderMonitoringTree();
  await loadMonitoringRuns();
}

function renderMonitoringTree() {
  if (!monitoringTree) return;
  const query = (monitoringSearch?.value || "").trim().toLowerCase();

  const folderMap = new Map();
  for (const f of monitoringPipelineFolders) {
    folderMap.set(f, []);
  }
  const rootPipelines = [];

  for (const p of allPipelinesForMonitoring) {
    if (p.folder && folderMap.has(p.folder)) {
      folderMap.get(p.folder).push(p);
    } else if (p.folder) {
      folderMap.set(p.folder, [p]);
    } else {
      rootPipelines.push(p);
    }
  }

  let html = "";

  for (const [folderName, pipelines] of folderMap.entries()) {
    const matchesPipelines = pipelines.filter((p) =>
      `${p.name} ${p.folder} ${p.description || ""}`.toLowerCase().includes(query)
    );
    const matchesFolder = folderName.toLowerCase().includes(query);
    if (query && !matchesFolder && matchesPipelines.length === 0) continue;

    const isCollapsed = collapsedMonitoringFolders.has(folderName) && !query;

    html += `
      <section class="tree-folder${isCollapsed ? " is-collapsed" : ""}" role="treeitem" aria-expanded="${!isCollapsed}">
        <div class="tree-row folder-row" data-mon-toggle-folder="${escapeHtml(folderName)}">
          <button class="tree-chevron" type="button" data-mon-toggle-folder="${escapeHtml(folderName)}" aria-label="${isCollapsed ? "Expand" : "Collapse"} ${escapeHtml(folderName)}">${svg.chevron}</button>
          <span class="tree-item-icon">${svg.folder}</span>
          <span class="tree-label mon-folder-label" data-mon-toggle-folder="${escapeHtml(folderName)}">
            <span>${escapeHtml(folderName)}</span>
            <small>${pipelines.length} pipeline${pipelines.length === 1 ? "" : "s"}</small>
          </span>
        </div>
        <div class="tree-children">
          ${matchesPipelines.map((p) => renderMonitoringPipelineRow(p)).join("")}
        </div>
      </section>
    `;
  }

  for (const p of rootPipelines) {
    if (query && !`${p.name} ${p.description || ""}`.toLowerCase().includes(query)) continue;
    html += renderMonitoringPipelineRow(p);
  }

  if (html.trim() === "") {
    html = `<div class="catalog-empty-hint" style="padding: 16px 8px; text-align: center; color: var(--quiet); font-size: 11px;">No pipelines found</div>`;
  }

  monitoringTree.innerHTML = html;
}

function renderMonitoringPipelineRow(p) {
  const pKey = `${p.folder}/${p.name}`;
  const isSelected = selectedMonitoringPipeline &&
    (selectedMonitoringPipeline.id === p.id || selectedMonitoringPipeline.key === pKey);

  return `
    <div class="tree-row pipeline-row${isSelected ? " is-selected" : ""}" data-mon-pipeline-id="${escapeHtml(p.id)}" data-mon-pipeline-key="${escapeHtml(pKey)}" data-mon-pipeline-folder="${escapeHtml(p.folder || "")}" data-mon-pipeline-name="${escapeHtml(p.name)}" role="treeitem" aria-pressed="${isSelected}">
      <span class="tree-item-icon">${svg.pipeline}</span>
      <button class="tree-label" type="button">
        <span>${escapeHtml(p.name)}</span>
        <small class="mon-pipeline-meta">
          <span class="mon-dot is-idle"></span>
          <span>Pipeline</span>
        </small>
      </button>
    </div>
  `;
}

function getMonitoringDateRange() {
  const preset = monFilterDatePreset ? monFilterDatePreset.value : "ALL";
  const now = new Date();
  if (preset === "TODAY") {
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return { from: start.toISOString(), to: null };
  } else if (preset === "7D") {
    const start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    return { from: start.toISOString(), to: null };
  } else if (preset === "30D") {
    const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    return { from: start.toISOString(), to: null };
  } else if (preset === "CUSTOM") {
    const fromVal = monFilterDateFrom?.value ? new Date(monFilterDateFrom.value).toISOString() : null;
    let toVal = null;
    if (monFilterDateTo?.value) {
      const d = new Date(monFilterDateTo.value);
      d.setHours(23, 59, 59, 999);
      toVal = d.toISOString();
    }
    return { from: fromVal, to: toVal };
  }
  return { from: null, to: null };
}

async function loadMonitoringRuns() {
  if (!monitoringRunsTbody) return;
  if (!selectedMonitoringPipeline) {
    showMonitoringEmptyState();
    return;
  }

  const status = monFilterStatus ? monFilterStatus.value : "ALL";
  const limit = monFilterLimit ? parseInt(monFilterLimit.value, 10) : 50;
  const { from: dateFrom, to: dateTo } = getMonitoringDateRange();

  monitoringRunsTbody.innerHTML = `<tr><td colspan="8" class="empty-table">Loading execution runs...</td></tr>`;

  try {
    const logIdent = selectedMonitoringPipeline.id || selectedMonitoringPipeline.key || selectedMonitoringPipeline.name;
    const logData = await api(`/api/monitoring/pipelines/${encodeURIComponent(logIdent)}`);
    let runs = logData.runs || [];

    if (status && status !== "ALL") {
      runs = runs.filter((r) => r.status === status);
    }
    if (dateFrom) {
      runs = runs.filter((r) => (r.started_at || "") >= dateFrom);
    }
    if (dateTo) {
      runs = runs.filter((r) => (r.started_at || "") <= dateTo);
    }
    runs.sort((a, b) => (b.started_at || "").localeCompare(a.started_at || ""));
    runs = runs.slice(0, limit);

    const textQuery = (monFilterSearch?.value || "").trim().toLowerCase();
    if (textQuery) {
      runs = runs.filter((r) => {
        const id = (r.run_id || "").toLowerCase();
        const pName = (r.pipeline_name_at_run || "").toLowerCase();
        const folder = (r.folder_at_run || "").toLowerCase();
        const err = (r.error || "").toLowerCase();
        return id.includes(textQuery) || pName.includes(textQuery) || folder.includes(textQuery) || err.includes(textQuery);
      });
    }

    monitoringRuns = runs;

    if (monitoringRunsCount) {
      monitoringRunsCount.textContent = `${runs.length} run${runs.length === 1 ? "" : "s"} tracked`;
    }

    updateMonitoringSummary(runs);
    renderMonitoringRunsTable(runs);

    if (selectedRunId) {
      const match = runs.find((r) => r.run_id === selectedRunId);
      if (match) {
        renderMonitoringRunDetail(match);
      } else if (runs.length > 0) {
        renderMonitoringRunDetail(runs[0]);
      } else {
        if (monitoringRunDetailCard) monitoringRunDetailCard.hidden = true;
      }
    } else if (runs.length > 0) {
      renderMonitoringRunDetail(runs[0]);
    } else {
      if (monitoringRunDetailCard) monitoringRunDetailCard.hidden = true;
    }
  } catch (error) {
    console.error("Failed to load runs:", error);
    monitoringRunsTbody.innerHTML = `<tr><td colspan="8" class="empty-table is-error">Failed to load runs: ${escapeHtml(error.message)}</td></tr>`;
  }
}

function updateMonitoringSummary(runs) {
  if (!runs || runs.length === 0) {
    if (monStatTotal) monStatTotal.textContent = "0";
    if (monStatSuccessRate) monStatSuccessRate.textContent = "100%";
    if (monStatRows) monStatRows.textContent = "0";
    if (monStatAvgDur) monStatAvgDur.textContent = "0 ms";
    return;
  }

  const total = runs.length;
  const successes = runs.filter((r) => r.status === "SUCCESS").length;
  const rate = Math.round((successes / total) * 100);

  let totalRows = 0;
  let totalDurationMs = 0;

  for (const r of runs) {
    totalDurationMs += (r.total_duration_seconds || 0) * 1000;
    for (const s of r.steps || []) {
      totalRows += (s.rows_processed || 0);
    }
  }

  const avgDur = (totalDurationMs / total).toFixed(1);

  if (monStatTotal) monStatTotal.textContent = total.toLocaleString();
  if (monStatSuccessRate) monStatSuccessRate.textContent = `${rate}%`;
  if (monStatRows) monStatRows.textContent = totalRows.toLocaleString();
  if (monStatAvgDur) monStatAvgDur.textContent = `${avgDur} ms`;
}

function renderMonitoringRunsTable(runs) {
  if (!monitoringRunsTbody) return;

  if (runs.length === 0) {
    monitoringRunsTbody.innerHTML = `
      <tr>
        <td colspan="8" class="empty-table">
          No execution runs found matching the selected pipeline and filters.
        </td>
      </tr>
    `;
    return;
  }

  monitoringRunsTbody.innerHTML = runs.map((run) => {
    const isSelected = selectedRunId === run.run_id;
    const isSuccess = run.status === "SUCCESS";
    const started = run.started_at ? new Date(run.started_at).toLocaleString() : "—";
    const durationMs = ((run.total_duration_seconds || 0) * 1000).toFixed(1);
    const stagesCount = (run.steps || []).length;
    const rowsProcessed = (run.steps || []).reduce((acc, s) => acc + (s.rows_processed || 0), 0);
    const shortId = (run.run_id || "—").slice(0, 8);

    return `
      <tr class="${isSelected ? "is-selected" : ""}" data-run-id="${escapeHtml(run.run_id)}">
        <td>
          <span class="mon-status-badge ${isSuccess ? "is-success" : "is-failed"}">
            <span class="mon-dot ${isSuccess ? "is-success" : "is-failed"}"></span>
            ${escapeHtml(run.status || "UNKNOWN")}
          </span>
        </td>
        <td><strong>${escapeHtml(run.pipeline_name_at_run || "pipeline")}</strong></td>
        <td>${escapeHtml(run.folder_at_run || "—")}</td>
        <td style="font-size:11px;color:var(--muted);">${escapeHtml(started)}</td>
        <td>${durationMs} ms</td>
        <td>${stagesCount} stage${stagesCount === 1 ? "" : "s"}</td>
        <td>${rowsProcessed.toLocaleString()}</td>
        <td><code class="mon-run-id-pill" title="${escapeHtml(run.run_id)}">${escapeHtml(shortId)}</code></td>
      </tr>
    `;
  }).join("");
}

function renderMonitoringRunDetail(run) {
  if (!run || !monitoringRunDetailCard) return;
  selectedRunId = run.run_id;
  selectedRunData = run;

  if (monitoringRunsTbody) {
    for (const tr of monitoringRunsTbody.querySelectorAll("tr")) {
      tr.classList.toggle("is-selected", tr.dataset.runId === run.run_id);
    }
  }

  monitoringRunDetailCard.hidden = false;

  const isSuccess = run.status === "SUCCESS";
  const durationMs = ((run.total_duration_seconds || 0) * 1000).toFixed(1);
  const started = run.started_at ? new Date(run.started_at).toLocaleString() : "—";

  if (monDetailIndicator) {
    monDetailIndicator.className = `status-indicator ${isSuccess ? "is-success" : "is-failed"}`;
  }
  if (monDetailTitle) {
    monDetailTitle.textContent = `${run.pipeline_name_at_run || "Pipeline"} execution`;
  }
  if (monDetailStatusBadge) {
    monDetailStatusBadge.className = `mon-status-badge ${isSuccess ? "is-success" : "is-failed"}`;
    monDetailStatusBadge.innerHTML = `<span class="mon-dot ${isSuccess ? "is-success" : "is-failed"}"></span> ${escapeHtml(run.status || "UNKNOWN")}`;
  }
  if (monDetailMeta) {
    monDetailMeta.textContent = `Run ID: ${run.run_id} · Folder: ${run.folder_at_run || "root"} · Started: ${started} · Duration: ${durationMs}ms`;
  }

  renderInferredResultsSection(run);
  renderLogEntriesSection(run);
  renderRawJsonSection(run);

  switchMonSection(activeMonSection);
}

function renderInferredResultsSection(run) {
  if (!monSectionInferred) return;

  const isSuccess = run.status === "SUCCESS";
  const durationMs = ((run.total_duration_seconds || 0) * 1000).toFixed(1);
  const steps = run.steps || [];
  const sources = run.sources || [];

  let totalProcessedRows = 0;
  let totalWrittenRows = 0;
  const destinations = [];

  for (const s of steps) {
    totalProcessedRows += (s.rows_processed || 0);
    for (const d of s.destinations || []) {
      totalWrittenRows += (d.rows_written || 0);
      destinations.push({
        step_name: s.step_name,
        destination_name: d.destination_name,
        format: d.format || "file",
        target: d.target || "—",
        rows_written: d.rows_written || 0,
        duration_ms: d.duration_ms || 0,
        status: d.status || "SUCCESS",
      });
    }
  }

  let html = `
    <div class="run-metrics-strip">
      <div class="run-metric-card">
        <span>STATUS</span>
        <strong style="color: ${isSuccess ? "var(--accent-strong)" : "#ef4444"}">${escapeHtml(run.status || "UNKNOWN")}</strong>
      </div>
      <div class="run-metric-card">
        <span>TOTAL TIME</span>
        <strong>${durationMs} ms</strong>
      </div>
      <div class="run-metric-card">
        <span>STAGES</span>
        <strong>${steps.length}</strong>
      </div>
      <div class="run-metric-card">
        <span>ROWS PROCESSED</span>
        <strong>${totalProcessedRows.toLocaleString()}</strong>
      </div>
      <div class="run-metric-card">
        <span>ROWS WRITTEN</span>
        <strong>${totalWrittenRows.toLocaleString()}</strong>
      </div>
    </div>
  `;

  if (run.error) {
    html += `
      <div class="sql-hints-box" style="margin-top: 6px;">
        <strong>Pipeline Execution Failure:</strong>
        <p style="margin: 4px 0 0; white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: 11px;">${escapeHtml(run.error)}</p>
      </div>
    `;
  }

  if (run.warnings && run.warnings.length > 0) {
    html += `
      <div class="sql-hints-box" style="margin-top: 6px; border-color: #fcd34d; background: #fffbeb; color: #b45309;">
        <strong>Warnings (${run.warnings.length}):</strong>
        <ul style="margin: 4px 0 0; padding-left: 18px;">${run.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul>
      </div>
    `;
  }

  html += `
    <div>
      <div class="mon-sub-heading">
        <span>Sources Scanned &amp; Registered (${sources.length})</span>
      </div>
      <div class="mon-sub-table-wrap">
        <table>
          <thead>
            <tr>
              <th>SOURCE TABLE</th>
              <th>CONNECTOR / TYPE</th>
              <th>ROWS READ</th>
              <th>SCAN LATENCY</th>
            </tr>
          </thead>
          <tbody>
            ${sources.length === 0
              ? `<tr><td colspan="4" class="empty-table">No external catalog sources scanned (internal CTEs / queries only).</td></tr>`
              : sources.map((s) => `
                <tr>
                  <td><strong>${escapeHtml(s.source_name || "—")}</strong></td>
                  <td><code class="mon-code-snippet">${escapeHtml(s.connector_type || "table")}</code></td>
                  <td>${(s.rows_read || 0).toLocaleString()}</td>
                  <td>${(s.duration_ms || 0).toFixed(1)} ms</td>
                </tr>
              `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;

  html += `
    <div>
      <div class="mon-sub-heading">
        <span>Step Execution Breakdown (${steps.length})</span>
      </div>
      <div class="mon-sub-table-wrap">
        <table>
          <thead>
            <tr>
              <th>STEP NAME</th>
              <th>STATUS</th>
              <th>DURATION</th>
              <th>ROWS</th>
              <th>DESTINATIONS</th>
              <th>SQL STATEMENT</th>
            </tr>
          </thead>
          <tbody>
            ${steps.length === 0
              ? `<tr><td colspan="6" class="empty-table">No steps recorded in this run.</td></tr>`
              : steps.map((s) => {
                const sSuccess = s.status === "SUCCESS";
                const destCount = (s.destinations || []).length;
                const destNames = (s.destinations || []).map((d) => d.destination_name).join(", ") || "None";
                const sqlSnippet = (s.sql || "").replace(/\s+/g, " ").trim();
                return `
                  <tr>
                    <td><strong>${escapeHtml(s.step_name || "step")}</strong></td>
                    <td>
                      <span class="mon-status-badge ${sSuccess ? "is-success" : "is-failed"}">
                        ${escapeHtml(s.status || "UNKNOWN")}
                      </span>
                    </td>
                    <td>${(s.duration_ms || 0).toFixed(1)} ms</td>
                    <td>${(s.rows_processed || 0).toLocaleString()}</td>
                    <td>${destCount > 0 ? `<span style="color:var(--accent);">${escapeHtml(destNames)}</span>` : "Temporary view"}</td>
                    <td><code class="mon-code-snippet" title="${escapeHtml(s.sql || "")}">${escapeHtml(sqlSnippet.slice(0, 70))}${sqlSnippet.length > 70 ? "…" : ""}</code></td>
                  </tr>
                `;
              }).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;

  html += `
    <div>
      <div class="mon-sub-heading">
        <span>Destination Writes (${destinations.length})</span>
      </div>
      <div class="mon-sub-table-wrap">
        <table>
          <thead>
            <tr>
              <th>DESTINATION</th>
              <th>FROM STEP</th>
              <th>TARGET / PATH</th>
              <th>ROWS WRITTEN</th>
              <th>WRITE LATENCY</th>
              <th>STATUS</th>
            </tr>
          </thead>
          <tbody>
            ${destinations.length === 0
              ? `<tr><td colspan="6" class="empty-table">No persistent destinations written (in-memory pipeline results).</td></tr>`
              : destinations.map((d) => `
                <tr>
                  <td><strong>${escapeHtml(d.destination_name)}</strong></td>
                  <td>${escapeHtml(d.step_name)}</td>
                  <td><code class="mon-code-snippet">${escapeHtml(d.target)}</code></td>
                  <td>${(d.rows_written || 0).toLocaleString()}</td>
                  <td>${(d.duration_ms || 0).toFixed(1)} ms</td>
                  <td>
                    <span class="mon-status-badge ${d.status === "SUCCESS" ? "is-success" : "is-failed"}">
                      ${escapeHtml(d.status)}
                    </span>
                  </td>
                </tr>
              `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;

  monSectionInferred.innerHTML = html;
}

function renderLogEntriesSection(run) {
  if (!monSectionLogs) return;

  const entries = run.log_entries || [];
  if (monTabLogCount) {
    monTabLogCount.textContent = entries.length;
  }

  const filtered = entries.filter((e) => {
    if (activeLogLevelFilter !== "ALL" && e.level !== activeLogLevelFilter) {
      return false;
    }
    if (logFilterSearchText) {
      const q = logFilterSearchText.toLowerCase();
      const msg = (e.message || "").toLowerCase();
      const stage = (e.stage || "").toLowerCase();
      return msg.includes(q) || stage.includes(q);
    }
    return true;
  });

  const levels = ["ALL", "INFO", "SCAN", "STEP", "WRITE", "WARN", "ERROR"];

  let html = `
    <div class="mon-logs-toolbar">
      <div class="mon-log-filter-pills" role="radiogroup" aria-label="Log level filter">
        ${levels.map((lvl) => `
          <button class="mon-log-pill${activeLogLevelFilter === lvl ? " is-active" : ""}" type="button" data-log-level="${lvl}">
            ${lvl}
          </button>
        `).join("")}
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <input id="mon-log-search-input" type="search" placeholder="Search log text..." value="${escapeHtml(logFilterSearchText)}" style="height: 28px; padding: 0 8px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--text); font-size: 11px;">
        <button id="mon-copy-logs-btn" class="secondary-button compact-btn" type="button" title="Copy chronological log stream">
          Copy logs
        </button>
      </div>
    </div>

    <div class="mon-log-stream" id="mon-log-stream">
      ${filtered.length === 0
        ? `<div class="empty-table">No log entries found matching level "${escapeHtml(activeLogLevelFilter)}" and search.</div>`
        : filtered.map((e) => {
          const timeStr = e.timestamp ? e.timestamp.split("T")[1]?.slice(0, 12) || e.timestamp : "—";
          const lvl = (e.level || "INFO").toLowerCase();
          return `
            <div class="mon-log-row">
              <span class="mon-log-time">${escapeHtml(timeStr)}</span>
              <span class="mon-log-badge level-${escapeHtml(lvl)}">${escapeHtml(e.level || "INFO")}</span>
              <span class="mon-log-stage">${escapeHtml(e.stage || "ENGINE")}</span>
              <span class="mon-log-message">${escapeHtml(e.message || "")}</span>
            </div>
          `;
        }).join("")}
    </div>
  `;

  monSectionLogs.innerHTML = html;

  for (const pill of monSectionLogs.querySelectorAll("[data-log-level]")) {
    pill.addEventListener("click", () => {
      activeLogLevelFilter = pill.dataset.logLevel;
      renderLogEntriesSection(run);
    });
  }

  const logSearchInput = monSectionLogs.querySelector("#mon-log-search-input");
  if (logSearchInput) {
    logSearchInput.addEventListener("input", (e) => {
      logFilterSearchText = e.target.value;
      renderLogEntriesSection(run);
    });
  }

  const copyLogsBtn = monSectionLogs.querySelector("#mon-copy-logs-btn");
  if (copyLogsBtn) {
    copyLogsBtn.addEventListener("click", () => {
      const text = entries.map((e) => `[${e.timestamp}] [${e.level}] [${e.stage}] ${e.message}`).join("\n");
      navigator.clipboard.writeText(text).then(() => {
        showNotification("Execution logs copied to clipboard.");
      });
    });
  }
}

function renderRawJsonSection(run) {
  if (!monSectionRaw) return;

  const folder = run.folder_at_run || "";
  const pId = run.pipeline_id || "pipeline";
  const pathStr = folder ? `logs/pipelines/${folder}/${pId}.json` : `logs/pipelines/${pId}.json`;

  if (monRawLogPath) {
    monRawLogPath.textContent = pathStr;
  }

  if (monRawJsonCode) {
    monRawJsonCode.textContent = JSON.stringify(run, null, 2);
  }
}

function switchMonSection(sectionName) {
  activeMonSection = sectionName;

  if (monTabInferred) {
    const isActive = sectionName === "inferred";
    monTabInferred.classList.toggle("is-active", isActive);
    monTabInferred.setAttribute("aria-selected", String(isActive));
  }
  if (monTabLogs) {
    const isActive = sectionName === "logs";
    monTabLogs.classList.toggle("is-active", isActive);
    monTabLogs.setAttribute("aria-selected", String(isActive));
  }
  if (monTabRaw) {
    const isActive = sectionName === "raw";
    monTabRaw.classList.toggle("is-active", isActive);
    monTabRaw.setAttribute("aria-selected", String(isActive));
  }

  if (monSectionInferred) monSectionInferred.hidden = sectionName !== "inferred";
  if (monSectionLogs) monSectionLogs.hidden = sectionName !== "logs";
  if (monSectionRaw) monSectionRaw.hidden = sectionName !== "raw";
}

if (monTabInferred) monTabInferred.addEventListener("click", () => switchMonSection("inferred"));
if (monTabLogs) monTabLogs.addEventListener("click", () => switchMonSection("logs"));
if (monTabRaw) monTabRaw.addEventListener("click", () => switchMonSection("raw"));

if (monDetailCloseBtn) {
  monDetailCloseBtn.addEventListener("click", () => {
    if (monitoringRunDetailCard) monitoringRunDetailCard.hidden = true;
  });
}

if (monDetailCopyIdBtn) {
  monDetailCopyIdBtn.addEventListener("click", () => {
    if (selectedRunData?.run_id) {
      navigator.clipboard.writeText(selectedRunData.run_id).then(() => {
        showNotification(`Run ID copied: ${selectedRunData.run_id.slice(0, 8)}`);
      });
    }
  });
}

if (monRawCopyBtn) {
  monRawCopyBtn.addEventListener("click", () => {
    if (selectedRunData) {
      navigator.clipboard.writeText(JSON.stringify(selectedRunData, null, 2)).then(() => {
        showNotification("Raw JSON log copied to clipboard.");
      });
    }
  });
}

function navigateToETLForPipeline(folder, name) {
  if (!name) return;
  selectedPipelineKey = folder ? `${folder}/${name}` : name;
  switchToModule("ETL");
}

function navigateToDocsForPipeline(folder, name) {
  if (!name) return;
  selectedDocPath = folder ? `${folder}/${name}.html` : `${name}.html`;
  switchToModule("Documentation");
}

if (monDetailOpenEtlBtn) {
  monDetailOpenEtlBtn.addEventListener("click", () => {
    if (selectedRunData) {
      navigateToETLForPipeline(selectedRunData.folder_at_run, selectedRunData.pipeline_name_at_run);
    }
  });
}

const monDetailOpenDocsBtn = document.querySelector("#mon-detail-open-docs-btn");
if (monDetailOpenDocsBtn) {
  monDetailOpenDocsBtn.addEventListener("click", () => {
    if (selectedRunData) {
      navigateToDocsForPipeline(selectedRunData.folder_at_run, selectedRunData.pipeline_name_at_run);
    }
  });
}

if (monOpenInEtlHeaderBtn) {
  monOpenInEtlHeaderBtn.addEventListener("click", () => {
    if (selectedMonitoringPipeline) {
      navigateToETLForPipeline(selectedMonitoringPipeline.folder, selectedMonitoringPipeline.name);
    }
  });
}

if (monitoringRefreshBtn) monitoringRefreshBtn.addEventListener("click", refreshMonitoring);
if (monitoringPageRefreshBtn) monitoringPageRefreshBtn.addEventListener("click", refreshMonitoring);

if (monitoringSearch) monitoringSearch.addEventListener("input", renderMonitoringTree);

if (monFilterStatus) monFilterStatus.addEventListener("change", () => loadMonitoringRuns());

if (monFilterDatePreset) {
  monFilterDatePreset.addEventListener("change", () => {
    if (monCustomDateWrap) {
      monCustomDateWrap.hidden = monFilterDatePreset.value !== "CUSTOM";
    }
    loadMonitoringRuns();
  });
}

if (monFilterDateFrom) monFilterDateFrom.addEventListener("change", () => loadMonitoringRuns());
if (monFilterDateTo) monFilterDateTo.addEventListener("change", () => loadMonitoringRuns());
if (monFilterSearch) monFilterSearch.addEventListener("input", () => loadMonitoringRuns());
if (monFilterLimit) monFilterLimit.addEventListener("change", () => loadMonitoringRuns());

if (monFilterResetBtn) {
  monFilterResetBtn.addEventListener("click", () => {
    if (monFilterStatus) monFilterStatus.value = "ALL";
    if (monFilterDatePreset) monFilterDatePreset.value = "ALL";
    if (monCustomDateWrap) monCustomDateWrap.hidden = true;
    if (monFilterDateFrom) monFilterDateFrom.value = "";
    if (monFilterDateTo) monFilterDateTo.value = "";
    if (monFilterSearch) monFilterSearch.value = "";
    if (monFilterLimit) monFilterLimit.value = "50";
    for (const pill of monitoringStatusPills) {
      pill.classList.toggle("is-active", pill.dataset.statusFilter === "ALL");
    }
    loadMonitoringRuns();
  });
}

for (const pill of monitoringStatusPills) {
  pill.addEventListener("click", () => {
    for (const p of monitoringStatusPills) p.classList.remove("is-active");
    pill.classList.add("is-active");
    const statusFilter = pill.dataset.statusFilter;
    if (monFilterStatus) monFilterStatus.value = statusFilter;
    if (selectedMonitoringPipeline) {
      loadMonitoringRuns();
    }
  });
}

if (monitoringTree) {
  monitoringTree.addEventListener("click", (event) => {
    const toggleBtn = event.target.closest("[data-mon-toggle-folder]");
    if (toggleBtn) {
      const fName = toggleBtn.dataset.monToggleFolder;
      if (collapsedMonitoringFolders.has(fName)) collapsedMonitoringFolders.delete(fName);
      else collapsedMonitoringFolders.add(fName);
      renderMonitoringTree();
      return;
    }

    const pRow = event.target.closest("[data-mon-pipeline-id]");
    if (pRow) {
      const pId = pRow.dataset.monPipelineId;
      const pKey = pRow.dataset.monPipelineKey;
      const pFolder = pRow.dataset.monPipelineFolder;
      const pName = pRow.dataset.monPipelineName;

      selectedMonitoringPipeline = { id: pId, key: pKey, folder: pFolder, name: pName };
      showMonitoringForSelectedPipeline();
      return;
    }
  });
}

if (monitoringRunsTbody) {
  monitoringRunsTbody.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-run-id]");
    if (!row) return;
    const rId = row.dataset.runId;
    const match = monitoringRuns.find((r) => r.run_id === rId);
    if (match) {
      renderMonitoringRunDetail(match);
      monitoringRunDetailCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  });
}

/* ==========================================================================
   Documentation Controller
   ========================================================================== */

const docsExplorer = document.querySelector("#documentation-explorer");
const docsTree = document.querySelector("#docs-tree");
const docsSearch = document.querySelector("#docs-search");
const docsCount = document.querySelector("#docs-count");
const docsRefreshBtn = document.querySelector("#docs-refresh-btn");

const docsModule = document.querySelector("#documentation-module");
const docsEmptyState = document.querySelector("#docs-empty-state");
const docsViewerContainer = document.querySelector("#docs-viewer-container");
const docsCrumbFolder = document.querySelector("#docs-crumb-folder");
const docsCrumbFile = document.querySelector("#docs-crumb-file");
const docsHeaderTitle = document.querySelector("#docs-header-title");
const docsHeaderFormatPill = document.querySelector("#docs-header-format-pill");
const docsHeaderMeta = document.querySelector("#docs-header-meta");
const docsActionVerifyBtn = document.querySelector("#docs-action-verify-btn");
const docsHeaderSyncPill = document.querySelector("#docs-header-sync-pill");
const docsStaleBanner = document.querySelector("#docs-stale-banner");
const docsStaleBannerText = document.querySelector("#docs-stale-banner-text");
const docsStaleBannerRegenBtn = document.querySelector("#docs-stale-banner-regen-btn");
const docsActionRegenBtn = document.querySelector("#docs-action-regen-btn");
const docsActionOpenTabBtn = document.querySelector("#docs-action-open-tab-btn");
const docsActionDownloadBtn = document.querySelector("#docs-action-download-btn");
const docsActionDeleteBtn = document.querySelector("#docs-action-delete-btn");

const docsHtmlWrap = document.querySelector("#docs-html-wrap");
const docsHtmlFrame = document.querySelector("#docs-html-frame");
if (docsHtmlFrame) {
  docsHtmlFrame.addEventListener("load", () => {
    try {
      const frameDoc = docsHtmlFrame.contentDocument || docsHtmlFrame.contentWindow?.document;
      if (!frameDoc) return;

      const frameHref = docsHtmlFrame.contentWindow?.location?.pathname || "";
      if (frameHref === "/" || frameHref.endsWith("index.html")) {
        console.warn("Blocked recursive app load inside doc iframe");
        if (selectedDocData && selectedDocData.content) {
          docsHtmlFrame.srcdoc = selectedDocData.content;
          return;
        }
      }

      frameDoc.addEventListener("click", (evt) => {
        const anchor = evt.target.closest("a");
        if (!anchor) return;
        const href = anchor.getAttribute("href") || "";
        if (href.startsWith("#")) {
          evt.preventDefault();
          const target = frameDoc.querySelector(href);
          if (target) target.scrollIntoView({ behavior: "smooth" });
        } else if (href && !href.startsWith("javascript:")) {
          evt.preventDefault();
          window.open(anchor.href, "_blank", "noopener,noreferrer");
        }
      }, true);
    } catch (_) {}
  });
}
const docsMdWrap = document.querySelector("#docs-md-wrap");
const docsMdTabPreview = document.querySelector("#docs-md-tab-preview");
const docsMdTabRaw = document.querySelector("#docs-md-tab-raw");
const docsMdPreviewPane = document.querySelector("#docs-md-preview-pane");
const docsMdRawPane = document.querySelector("#docs-md-raw-pane");
const docsMdRawCode = document.querySelector("#docs-md-raw-code");

let docsItems = [];
let docsFolders = [];
let selectedDocPath = null;
let selectedDocData = null;
const collapsedDocsFolders = new Set();
const staleDocsMap = new Map();
let activeMdTab = "preview";

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i] || "B"}`;
}

function renderMarkdown(mdText) {
  if (!mdText) return "";
  const lines = mdText.replace(/\r\n/g, "\n").split("\n");
  const htmlOut = [];
  let inCode = false;
  let codeLang = "";
  let codeLines = [];
  let inTable = false;
  let tableHeader = null;
  let tableRows = [];
  let inList = false;
  let listType = "ul";
  let inBlockquote = false;
  let blockquoteLines = [];

  function flushList() {
    if (inList) {
      htmlOut.push(`</${listType}>`);
      inList = false;
    }
  }

  function flushBlockquote() {
    if (inBlockquote) {
      const bqContent = blockquoteLines.map(inlineMd).join("<br>");
      htmlOut.push(`<blockquote>${bqContent}</blockquote>`);
      inBlockquote = false;
      blockquoteLines = [];
    }
  }

  function flushTable() {
    if (inTable) {
      let tHtml = '<div class="docs-table-wrap"><table>';
      if (tableHeader) {
        tHtml += `<thead><tr>${tableHeader.map((h) => `<th>${inlineMd(h.trim())}</th>`).join("")}</tr></thead>`;
      }
      if (tableRows.length) {
        tHtml += "<tbody>";
        for (const row of tableRows) {
          tHtml += `<tr>${row.map((c) => `<td>${inlineMd(c.trim())}</td>`).join("")}</tr>`;
        }
        tHtml += "</tbody>";
      }
      tHtml += "</table></div>";
      htmlOut.push(tHtml);
      inTable = false;
      tableHeader = null;
      tableRows = [];
    }
  }

  function inlineMd(str) {
    if (!str) return "";
    let s = escapeHtml(str);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
    s = s.replace(/(^|[^_])_([^_]+)_/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return s;
  }

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (trimmed.startsWith("```")) {
      if (inCode) {
        const escapedCode = escapeHtml(codeLines.join("\n"));
        const langClass = codeLang ? ` class="language-${escapeHtml(codeLang)}"` : "";
        htmlOut.push(`<pre><code${langClass}>${escapedCode}</code></pre>`);
        inCode = false;
        codeLang = "";
        codeLines = [];
        continue;
      } else {
        flushList();
        flushBlockquote();
        flushTable();
        inCode = true;
        codeLang = trimmed.slice(3).trim();
        codeLines = [];
        continue;
      }
    }

    if (inCode) {
      codeLines.push(rawLine);
      continue;
    }

    if (/^(---|___|\*\*\*)$/.test(trimmed)) {
      flushList();
      flushBlockquote();
      flushTable();
      htmlOut.push("<hr>");
      continue;
    }

    if (trimmed.startsWith(">")) {
      flushList();
      flushTable();
      inBlockquote = true;
      blockquoteLines.push(trimmed.replace(/^>\s?/, ""));
      continue;
    } else if (inBlockquote) {
      flushBlockquote();
    }

    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      flushList();
      flushBlockquote();
      const cells = trimmed
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());

      const isDelimiter = cells.every((c) => /^:?-+:?$/.test(c));
      if (isDelimiter) {
        continue;
      }

      if (!inTable) {
        inTable = true;
        tableHeader = cells;
        tableRows = [];
      } else {
        tableRows.push(cells);
      }
      continue;
    } else if (inTable) {
      flushTable();
    }

    const hMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (hMatch) {
      flushList();
      flushBlockquote();
      flushTable();
      const level = hMatch[1].length;
      htmlOut.push(`<h${level}>${inlineMd(hMatch[2])}</h${level}>`);
      continue;
    }

    const ulMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (ulMatch) {
      flushBlockquote();
      flushTable();
      if (!inList || listType !== "ul") {
        flushList();
        inList = true;
        listType = "ul";
        htmlOut.push("<ul>");
      }
      htmlOut.push(`<li>${inlineMd(ulMatch[1])}</li>`);
      continue;
    }

    const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (olMatch) {
      flushBlockquote();
      flushTable();
      if (!inList || listType !== "ol") {
        flushList();
        inList = true;
        listType = "ol";
        htmlOut.push("<ol>");
      }
      htmlOut.push(`<li>${inlineMd(olMatch[1])}</li>`);
      continue;
    }

    if (!trimmed) {
      flushList();
      flushBlockquote();
      flushTable();
      continue;
    }

    flushList();
    flushBlockquote();
    flushTable();
    htmlOut.push(`<p>${inlineMd(trimmed)}</p>`);
  }

  flushList();
  flushBlockquote();
  flushTable();

  return htmlOut.join("\n");
}

async function refreshDocs(preserveSelection = true) {
  try {
    const result = await api("/api/docs");
    docsItems = result.items || [];
    docsFolders = result.folders || [];

    if (docsCount) {
      docsCount.textContent = `${docsItems.length} document${docsItems.length === 1 ? "" : "s"} tracked`;
    }

    renderDocsTree();

    if (preserveSelection && selectedDocPath) {
      const match = docsItems.find((d) => d.rel_path === selectedDocPath);
      if (match) {
        await selectDoc(match.rel_path);
      } else {
        clearSelectedDoc();
      }
    } else if (!preserveSelection) {
      clearSelectedDoc();
    }
  } catch (error) {
    console.error("Failed to load documentation:", error);
    showNotification(`Documentation load error: ${error.message}`);
  }
}

function clearSelectedDoc() {
  selectedDocPath = null;
  selectedDocData = null;
  if (docsEmptyState) docsEmptyState.hidden = false;
  if (docsViewerContainer) docsViewerContainer.hidden = true;
  if (docsHtmlFrame) docsHtmlFrame.src = "about:blank";
  renderDocsTree();
}

function renderDocsTree() {
  if (!docsTree) return;
  const query = (docsSearch?.value || "").trim().toLowerCase();

  const folderMap = new Map();
  for (const f of docsFolders) {
    if (f) folderMap.set(f, []);
  }
  const rootDocs = [];

  for (const doc of docsItems) {
    if (doc.folder && folderMap.has(doc.folder)) {
      folderMap.get(doc.folder).push(doc);
    } else if (doc.folder) {
      folderMap.set(doc.folder, [doc]);
    } else {
      rootDocs.push(doc);
    }
  }

  let html = "";

  for (const [folderName, docs] of folderMap.entries()) {
    const matchesDocs = docs.filter((d) =>
      `${d.name} ${d.filename} ${d.folder} ${d.format}`.toLowerCase().includes(query)
    );
    const matchesFolder = folderName.toLowerCase().includes(query);
    if (query && !matchesFolder && matchesDocs.length === 0) continue;
    if (docs.length === 0) continue;

    const isCollapsed = collapsedDocsFolders.has(folderName) && !query;

    html += `
      <section class="tree-folder${isCollapsed ? " is-collapsed" : ""}" role="treeitem" aria-expanded="${!isCollapsed}">
        <div class="tree-row folder-row">
          <button class="tree-chevron" type="button" data-docs-toggle-folder="${escapeHtml(folderName)}" aria-label="${isCollapsed ? "Expand" : "Collapse"} ${escapeHtml(folderName)}">${svg.chevron}</button>
          <span class="tree-item-icon">${svg.folder}</span>
          <button class="tree-label" type="button" data-docs-toggle-folder="${escapeHtml(folderName)}">
            <span>${escapeHtml(folderName)}</span>
            <small>${docs.length} doc${docs.length === 1 ? "" : "s"}</small>
          </button>
        </div>
        <div class="tree-children">
          ${(query ? matchesDocs : docs).map((d) => renderDocItemRow(d)).join("")}
        </div>
      </section>
    `;
  }

  for (const d of rootDocs) {
    if (query && !`${d.name} ${d.filename} ${d.format}`.toLowerCase().includes(query)) continue;
    html += renderDocItemRow(d);
  }

  if (!html) {
    html = `<p class="tree-empty" style="padding:16px 12px;font-size:12px;color:var(--quiet);">${query ? "No documents match your search." : "No documentation generated yet."}</p>`;
  }

  docsTree.innerHTML = html;
}

function renderDocItemRow(doc) {
  const isSelected = selectedDocPath === doc.rel_path;
  const isHtml = doc.format === "html";
  const icon = isHtml ? svg.htmlDoc : svg.mdDoc;
  const badgeClass = isHtml ? "is-html" : "is-md";
  const staleInfo = staleDocsMap.get(doc.rel_path);
  const isStale = Boolean(staleInfo && staleInfo.is_stale);
  const staleBadge = isStale
    ? `<span class="doc-stale-badge" title="${escapeHtml(staleInfo.reason || 'Documentation is out of sync with pipeline definition')}">⚠️</span>`
    : "";

  return `
    <div class="tree-row doc-row${isSelected ? " is-selected" : ""}" data-doc-path="${escapeHtml(doc.rel_path)}" role="treeitem" aria-pressed="${isSelected}">
      <span class="tree-item-icon">${icon}</span>
      <button class="tree-label" type="button" data-doc-path="${escapeHtml(doc.rel_path)}">
        <span>${escapeHtml(doc.name)}${staleBadge}</span>
        <small class="doc-tree-meta">
          <span class="doc-format-badge ${badgeClass}">${escapeHtml(doc.format.toUpperCase())}</span>
          <span>${formatBytes(doc.size_bytes)}</span>
        </small>
      </button>
      <span class="tree-actions">
        <button class="icon-button tree-action" type="button" title="Regenerate doc" aria-label="Regenerate ${escapeHtml(doc.filename)}" data-doc-action="regenerate" data-doc-path="${escapeHtml(doc.rel_path)}">
          ${svg.sync}
        </button>
        <button class="icon-button tree-action doc-action-delete" type="button" title="Delete doc" aria-label="Delete ${escapeHtml(doc.filename)}" data-doc-action="delete" data-doc-path="${escapeHtml(doc.rel_path)}">
          ${svg.delete}
        </button>
      </span>
    </div>
  `;
}

async function selectDoc(rel_path) {
  try {
    selectedDocPath = rel_path;
    renderDocsTree();

    const data = await api(`/api/docs/item/${encodeURIComponent(rel_path)}`);
    selectedDocData = data;

    if (docsEmptyState) docsEmptyState.hidden = true;
    if (docsViewerContainer) docsViewerContainer.hidden = false;

    if (docsCrumbFolder) docsCrumbFolder.textContent = data.folder || "(root)";
    if (docsCrumbFile) docsCrumbFile.textContent = data.filename;
    if (docsHeaderTitle) docsHeaderTitle.textContent = data.name;
    if (docsHeaderFormatPill) {
      docsHeaderFormatPill.textContent = data.format.toUpperCase();
      docsHeaderFormatPill.className = `docs-format-pill is-${data.format}`;
    }
    if (docsHeaderMeta) {
      const modDate = data.modified_at ? new Date(data.modified_at).toLocaleString() : "—";
      docsHeaderMeta.textContent = `documentation/${data.rel_path} · ${formatBytes(data.size_bytes)} · Last modified: ${modDate}`;
    }

    // Sync / staleness state check
    const staleInfo = staleDocsMap.get(rel_path);
    if (staleInfo && staleInfo.is_stale) {
      if (docsStaleBanner) {
        docsStaleBanner.hidden = false;
        if (docsStaleBannerText) docsStaleBannerText.textContent = staleInfo.reason;
      }
      if (docsHeaderSyncPill) {
        docsHeaderSyncPill.hidden = false;
        docsHeaderSyncPill.className = "docs-sync-pill is-stale";
        docsHeaderSyncPill.textContent = "OUT OF SYNC";
      }
    } else if (staleInfo && !staleInfo.is_stale) {
      if (docsStaleBanner) docsStaleBanner.hidden = true;
      if (docsHeaderSyncPill) {
        docsHeaderSyncPill.hidden = false;
        docsHeaderSyncPill.className = "docs-sync-pill is-synced";
        docsHeaderSyncPill.textContent = "IN SYNC";
      }
    } else {
      if (docsStaleBanner) docsStaleBanner.hidden = true;
      if (docsHeaderSyncPill) docsHeaderSyncPill.hidden = true;
    }

    if (docsActionOpenTabBtn) {
      docsActionOpenTabBtn.href = data.rel_path && data.rel_path.startsWith("http") ? data.rel_path : `documentation/${data.rel_path}`;
    }

    if (data.format === "html") {
      if (docsHtmlWrap) docsHtmlWrap.hidden = false;
      if (docsMdWrap) docsMdWrap.hidden = true;
      if (docsHtmlFrame) {
        if (data.content) {
          docsHtmlFrame.srcdoc = data.content;
        } else {
          docsHtmlFrame.src = `/documentation/${data.rel_path}?t=${Date.now()}`;
        }
      }
    } else {
      if (docsHtmlWrap) docsHtmlWrap.hidden = true;
      if (docsMdWrap) docsMdWrap.hidden = false;
      if (docsMdRawCode) {
        docsMdRawCode.textContent = data.content;
      }
      if (docsMdPreviewPane) {
        docsMdPreviewPane.innerHTML = renderMarkdown(data.content);
      }
      setDocMdTab(activeMdTab);
    }
  } catch (error) {
    console.error("Failed to load document:", error);
    showNotification(`Failed to load document: ${error.message}`);
  }
}

async function verifyDocSync(rel_path) {
  if (!rel_path) return;
  try {
    if (docsActionVerifyBtn) {
      docsActionVerifyBtn.disabled = true;
      docsActionVerifyBtn.innerHTML = `<span>Checking...</span>`;
    }

    const checkResult = await api(`/api/docs/verify/${encodeURIComponent(rel_path)}`);
    staleDocsMap.set(rel_path, {
      is_stale: checkResult.is_stale,
      reason: checkResult.reason,
    });

    renderDocsTree();

    if (checkResult.is_stale) {
      if (docsStaleBanner) {
        docsStaleBanner.hidden = false;
        if (docsStaleBannerText) docsStaleBannerText.textContent = checkResult.reason;
      }
      if (docsHeaderSyncPill) {
        docsHeaderSyncPill.hidden = false;
        docsHeaderSyncPill.className = "docs-sync-pill is-stale";
        docsHeaderSyncPill.textContent = "OUT OF SYNC";
      }
      showNotification(`Warning: Documentation is out of sync with pipeline!`);
    } else {
      if (docsStaleBanner) docsStaleBanner.hidden = true;
      if (docsHeaderSyncPill) {
        docsHeaderSyncPill.hidden = false;
        docsHeaderSyncPill.className = "docs-sync-pill is-synced";
        docsHeaderSyncPill.textContent = "IN SYNC";
      }
      showNotification(`Documentation is in sync with pipeline definition.`);
    }
  } catch (error) {
    console.error("Verification failed:", error);
    showNotification(`Sync check error: ${error.message}`);
  } finally {
    if (docsActionVerifyBtn) {
      docsActionVerifyBtn.disabled = false;
      docsActionVerifyBtn.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true" style="width:13px;height:13px;"><path d="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/></svg>
        Verify sync
      `;
    }
  }
}

async function regenerateDoc(rel_path) {
  try {
    showNotification(`Regenerating ${rel_path}...`);
    const result = await api("/api/docs/regenerate", {
      method: "POST",
      body: JSON.stringify({ rel_path }),
    });

    // Mark as in sync after regeneration
    staleDocsMap.set(rel_path, { is_stale: false, reason: "Recently regenerated" });
    renderDocsTree();
    if (docsStaleBanner) docsStaleBanner.hidden = true;
    if (docsHeaderSyncPill) {
      docsHeaderSyncPill.hidden = false;
      docsHeaderSyncPill.className = "docs-sync-pill is-synced";
      docsHeaderSyncPill.textContent = "IN SYNC";
    }

    showNotification(`Document updated: ${result.path || result.saved_path} (${result.format.toUpperCase()})`);
    await refreshDocs(true);
    if (selectedDocPath === rel_path) {
      await selectDoc(rel_path);
    }
  } catch (error) {
    console.error("Failed to regenerate doc:", error);
    showNotification(`Regeneration failed: ${error.message}`);
  }
}

async function deleteDoc(rel_path) {
  const confirmed = window.confirm(`Are you sure you want to delete documentation file "${rel_path}"?`);
  if (!confirmed) return;
  try {
    await api(`/api/docs/item/${encodeURIComponent(rel_path)}`, {
      method: "DELETE",
    });
    staleDocsMap.delete(rel_path);
    showNotification(`Deleted documentation file: ${rel_path}`);
    if (selectedDocPath === rel_path) {
      clearSelectedDoc();
    }
    await refreshDocs(false);
  } catch (error) {
    console.error("Failed to delete doc:", error);
    showNotification(`Delete failed: ${error.message}`);
  }
}

function setDocMdTab(tab) {
  activeMdTab = tab;
  if (!docsMdTabPreview || !docsMdTabRaw || !docsMdPreviewPane || !docsMdRawPane) return;
  const isPreview = tab === "preview";
  docsMdTabPreview.classList.toggle("is-active", isPreview);
  docsMdTabRaw.classList.toggle("is-active", !isPreview);
  docsMdPreviewPane.hidden = !isPreview;
  docsMdRawPane.hidden = isPreview;
}

if (docsMdTabPreview) {
  docsMdTabPreview.addEventListener("click", () => setDocMdTab("preview"));
}
if (docsMdTabRaw) {
  docsMdTabRaw.addEventListener("click", () => setDocMdTab("raw"));
}

const docsActionOpenEtlBtn = document.querySelector("#docs-action-open-etl-btn");
if (docsActionOpenEtlBtn) {
  docsActionOpenEtlBtn.addEventListener("click", () => {
    if (!selectedDocPath) return;
    const clean = selectedDocPath.replace(/\.(html|md)$/, "");
    const parts = clean.split("/");
    const folder = parts.length > 1 ? parts[0] : "default";
    const name = parts.length > 1 ? parts[1] : parts[0];
    navigateToETLForPipeline(folder, name);
  });
}

if (docsActionVerifyBtn) {
  docsActionVerifyBtn.addEventListener("click", () => {
    if (selectedDocPath) verifyDocSync(selectedDocPath);
  });
}
if (docsStaleBannerRegenBtn) {
  docsStaleBannerRegenBtn.addEventListener("click", () => {
    if (selectedDocPath) regenerateDoc(selectedDocPath);
  });
}
if (docsActionRegenBtn) {
  docsActionRegenBtn.addEventListener("click", () => {
    if (selectedDocPath) regenerateDoc(selectedDocPath);
  });
}
if (docsActionDeleteBtn) {
  docsActionDeleteBtn.addEventListener("click", () => {
    if (selectedDocPath) deleteDoc(selectedDocPath);
  });
}
if (docsActionDownloadBtn) {
  docsActionDownloadBtn.addEventListener("click", () => {
    if (!selectedDocPath) return;
    const filename = selectedDocPath.split("/").pop() || "documentation";
    try {
      if (selectedDocData && selectedDocData.content) {
        const mimeType = selectedDocPath.endsWith(".html") ? "text/html;charset=utf-8" : "text/markdown;charset=utf-8";
        const blob = new Blob([selectedDocData.content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showNotification(`Downloaded ${filename}`);
        return;
      }
    } catch (e) {
      console.warn("Client blob download fallback to server route", e);
    }
    const a = document.createElement("a");
    a.href = `/api/docs/download/${encodeURIComponent(selectedDocPath)}`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showNotification(`Downloaded ${filename}`);
  });
}

if (docsSearch) {
  docsSearch.addEventListener("input", () => {
    renderDocsTree();
  });
}

if (docsRefreshBtn) {
  docsRefreshBtn.addEventListener("click", () => {
    refreshDocs(true);
    showNotification("Documentation refreshed from disk.");
  });
}

if (docsTree) {
  docsTree.addEventListener("click", (event) => {
    const toggleFolderBtn = event.target.closest("[data-docs-toggle-folder]");
    if (toggleFolderBtn) {
      const folderName = toggleFolderBtn.dataset.docsToggleFolder;
      if (collapsedDocsFolders.has(folderName)) {
        collapsedDocsFolders.delete(folderName);
      } else {
        collapsedDocsFolders.add(folderName);
      }
      renderDocsTree();
      return;
    }

    const actionBtn = event.target.closest("[data-doc-action]");
    if (actionBtn) {
      event.stopPropagation();
      const action = actionBtn.dataset.docAction;
      const path = actionBtn.dataset.docPath;
      if (action === "regenerate") {
        regenerateDoc(path);
      } else if (action === "delete") {
        deleteDoc(path);
      }
      return;
    }

    const docRow = event.target.closest("[data-doc-path]");
    if (docRow) {
      const path = docRow.dataset.docPath;
      selectDoc(path);
      return;
    }
  });
}

/* ==========================================================================
   Help & Docs Portal Controller (Microsoft Learn Style Navigation & Portal)
   ========================================================================== */

const helpExplorer = document.querySelector("#help-explorer");
const helpTree = document.querySelector("#help-tree");
const helpSearch = document.querySelector("#help-search");
const helpTopicsCount = document.querySelector("#help-topics-count");
const helpExpandAllBtn = document.querySelector("#help-expand-all-btn");

const helpModule = document.querySelector("#help-module");
const helpBcCategory = document.querySelector("#help-bc-category");
const helpBcTitle = document.querySelector("#help-bc-title");
const helpArticleTitle = document.querySelector("#help-article-title");
const helpReadTime = document.querySelector("#help-read-time");
const helpArticleContent = document.querySelector("#help-article-content");
const helpInstallSampleBtn = document.querySelector("#help-install-sample-btn");
const helpSampleBanner = document.querySelector("#help-sample-banner");
const helpBannerClose = document.querySelector("#help-banner-close");
const helpPagerPrev = document.querySelector("#help-pager-prev");
const helpPagerPrevTitle = document.querySelector("#help-pager-prev-title");
const helpPagerNext = document.querySelector("#help-pager-next");
const helpPagerNextTitle = document.querySelector("#help-pager-next-title");

let activeHelpTopicId = "intro";
let helpCollapsedCategories = new Set();
let helpSearchQuery = "";

function getAllHelpTopics() {
  const categories = window.HELP_CATEGORIES || [];
  const list = [];
  for (const cat of categories) {
    for (const topic of cat.topics) {
      list.push({ ...topic, categoryId: cat.id, categoryTitle: cat.title });
    }
  }
  return list;
}

function findHelpTopic(topicId) {
  const categories = window.HELP_CATEGORIES || [];
  for (const cat of categories) {
    const topic = cat.topics.find((t) => t.id === topicId);
    if (topic) {
      return { topic, category: cat };
    }
  }
  return null;
}

function escapeHelpHTML(str) {
  return (str || "").replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}

function highlightSearchMatch(text, query) {
  if (!query) return escapeHelpHTML(text);
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return escapeHelpHTML(text).replace(regex, '<span class="help-search-highlight">$1</span>');
}

function renderHelpTree() {
  if (!helpTree) return;
  const categories = window.HELP_CATEGORIES || [];
  const query = helpSearchQuery.trim().toLowerCase();
  const allTopics = getAllHelpTopics();

  let visibleTopicsCount = 0;
  let html = "";

  categories.forEach((cat) => {
    // Filter topics in this category
    const matchingTopics = cat.topics.filter((topic) => {
      if (!query) return true;
      return (
        topic.title.toLowerCase().includes(query) ||
        (topic.summary && topic.summary.toLowerCase().includes(query)) ||
        cat.title.toLowerCase().includes(query)
      );
    });

    if (matchingTopics.length === 0) return;

    visibleTopicsCount += matchingTopics.length;
    // Auto-open if searching, otherwise respect collapse set
    const isOpen = query ? true : !helpCollapsedCategories.has(cat.id);

    html += `
      <div class="help-tree-category ${isOpen ? "is-open" : ""}" data-category-id="${cat.id}">
        <button class="help-category-header" type="button" aria-expanded="${isOpen}">
          <svg class="help-cat-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          <svg class="help-cat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
            <path d="M6 6h10M6 10h10M6 14h6"/>
          </svg>
          <span class="help-cat-title">${escapeHelpHTML(cat.title)}</span>
          <span class="help-cat-count">${matchingTopics.length}</span>
        </button>
        <div class="help-category-children">
          ${matchingTopics
            .map((topic) => {
              const isActive = topic.id === activeHelpTopicId;
              return `
                <button class="help-tree-topic ${isActive ? "is-active" : ""}" 
                        type="button" 
                        data-topic-id="${topic.id}" 
                        title="${escapeHelpHTML(topic.title)}">
                  <span class="help-topic-dot"></span>
                  <span class="help-topic-label">${highlightSearchMatch(topic.title, query)}</span>
                </button>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
  });

  if (visibleTopicsCount === 0) {
    html = `
      <div class="catalog-empty-hint" style="padding: 24px 12px; text-align: center;">
        <p style="margin: 0; font-size: 12px; color: var(--quiet);">No documentation articles match &ldquo;${escapeHelpHTML(query)}&rdquo;</p>
      </div>
    `;
  }

  helpTree.innerHTML = html;

  if (helpTopicsCount) {
    if (query) {
      helpTopicsCount.textContent = `Showing ${visibleTopicsCount} of ${allTopics.length} articles`;
    } else {
      helpTopicsCount.textContent = `${allTopics.length} articles · ${categories.length} sections`;
    }
  }
}

function selectHelpTopic(topicId) {
  const match = findHelpTopic(topicId);
  if (!match) return;

  activeHelpTopicId = topicId;
  const { topic, category } = match;

  if (helpBcCategory) helpBcCategory.textContent = category.title;
  if (helpBcTitle) helpBcTitle.textContent = topic.title;
  if (helpArticleTitle) helpArticleTitle.textContent = topic.title;
  if (helpReadTime) helpReadTime.textContent = ⏱️ ;

  if (helpArticleContent) {
    helpArticleContent.innerHTML = topic.content;
  }

  // Update active state in tree
  if (helpTree) {
    helpTree.querySelectorAll(".help-tree-topic").forEach((el) => {
      el.classList.toggle("is-active", el.dataset.topicId === topicId);
    });
  }

  // Configure Prev / Next Pager
  const allTopics = getAllHelpTopics();
  const currentIndex = allTopics.findIndex((t) => t.id === topicId);

  if (helpPagerPrev) {
    if (currentIndex > 0) {
      const prevTopic = allTopics[currentIndex - 1];
      helpPagerPrev.disabled = false;
      helpPagerPrev.dataset.targetTopicId = prevTopic.id;
      if (helpPagerPrevTitle) helpPagerPrevTitle.textContent = prevTopic.title;
    } else {
      helpPagerPrev.disabled = true;
      delete helpPagerPrev.dataset.targetTopicId;
      if (helpPagerPrevTitle) helpPagerPrevTitle.textContent = "Beginning of docs";
    }
  }

  if (helpPagerNext) {
    if (currentIndex >= 0 && currentIndex < allTopics.length - 1) {
      const nextTopic = allTopics[currentIndex + 1];
      helpPagerNext.disabled = false;
      helpPagerNext.dataset.targetTopicId = nextTopic.id;
      if (helpPagerNextTitle) helpPagerNextTitle.textContent = nextTopic.title;
    } else {
      helpPagerNext.disabled = true;
      delete helpPagerNext.dataset.targetTopicId;
      if (helpPagerNextTitle) helpPagerNextTitle.textContent = "End of docs";
    }
  }

  // Scroll article container to top
  if (helpModule) {
    helpModule.scrollTop = 0;
  }
}

async function installSampleWarehouseFromHelp(btnElement) {
  const originalText = btnElement ? btnElement.innerHTML : null;
  if (btnElement) {
    btnElement.disabled = true;
    btnElement.innerHTML = `
      <svg class="spinning" viewBox="0 0 24 24" aria-hidden="true" style="width:14px;height:14px;stroke:currentColor;fill:none;animation:spin 1s linear infinite;"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
      <span>Installing NovaMart...</span>
    `;
  }

  try {
    const res = await api("/api/sample-data/install", { method: "POST" });
    if (helpSampleBanner) {
      const bannerDesc = document.querySelector("#help-sample-banner-desc");
      if (bannerDesc) {
        bannerDesc.textContent = `NovaMart omnichannel dataset, catalog (${res.catalog || "sample_warehouse.yaml"}), and ${res.pipelines_copied || 10} pipelines were installed. Active catalog switched to ${res.active_catalog || "sample_warehouse.yaml"}.`;
      }
      helpSampleBanner.hidden = false;
    }
    await refreshCatalog();
  } catch (err) {
    alert(`Failed to load sample warehouse: ${err.message}`);
  } finally {
    if (btnElement && originalText) {
      btnElement.disabled = false;
      btnElement.innerHTML = originalText;
    }
  }
}

function refreshHelp() {
  renderHelpTree();
  selectHelpTopic(activeHelpTopicId);
}

// Help Tree & Event Listeners setup
if (helpTree) {
  helpTree.addEventListener("click", (e) => {
    // Topic click
    const topicBtn = e.target.closest(".help-tree-topic");
    if (topicBtn && topicBtn.dataset.topicId) {
      selectHelpTopic(topicBtn.dataset.topicId);
      return;
    }

    // Category header click (collapse/expand)
    const catHeader = e.target.closest(".help-category-header");
    if (catHeader) {
      const catRow = catHeader.closest(".help-tree-category");
      if (catRow && catRow.dataset.categoryId) {
        const catId = catRow.dataset.categoryId;
        if (helpCollapsedCategories.has(catId)) {
          helpCollapsedCategories.delete(catId);
          catRow.classList.add("is-open");
          catHeader.setAttribute("aria-expanded", "true");
        } else {
          helpCollapsedCategories.add(catId);
          catRow.classList.remove("is-open");
          catHeader.setAttribute("aria-expanded", "false");
        }
      }
    }
  });
}

if (helpSearch) {
  helpSearch.addEventListener("input", (e) => {
    helpSearchQuery = e.target.value;
    renderHelpTree();
  });
}

if (helpExpandAllBtn) {
  helpExpandAllBtn.addEventListener("click", () => {
    const categories = window.HELP_CATEGORIES || [];
    if (helpCollapsedCategories.size === 0) {
      // Collapse all
      categories.forEach((cat) => helpCollapsedCategories.add(cat.id));
    } else {
      // Expand all
      helpCollapsedCategories.clear();
    }
    renderHelpTree();
  });
}

if (helpInstallSampleBtn) {
  helpInstallSampleBtn.addEventListener("click", () => {
    installSampleWarehouseFromHelp(helpInstallSampleBtn);
  });
}

// In-article button / link delegation
if (helpModule) {
  helpModule.addEventListener("click", (e) => {
    // In-article sample warehouse install button
    const installActionBtn = e.target.closest(".help-install-sample-action-btn");
    if (installActionBtn) {
      installSampleWarehouseFromHelp(installActionBtn);
      return;
    }

    // In-article quick jump links [data-help-jump="topicId"]
    const jumpLink = e.target.closest("[data-help-jump]");
    if (jumpLink) {
      const targetId = jumpLink.dataset.helpJump;
      if (targetId) {
        selectHelpTopic(targetId);
      }
      return;
    }

    // Code copy buttons
    const codeCopyBtn = e.target.closest(".help-code-copy-btn");
    if (codeCopyBtn) {
      const codeBlock = codeCopyBtn.closest(".help-code-wrap")?.querySelector("code");
      if (codeBlock) {
        navigator.clipboard.writeText(codeBlock.innerText).then(() => {
          const original = codeCopyBtn.textContent;
          codeCopyBtn.textContent = "Copied!";
          setTimeout(() => {
            codeCopyBtn.textContent = original;
          }, 1500);
        });
      }
      return;
    }
  });
}


if (helpBannerClose && helpSampleBanner) {
  helpBannerClose.addEventListener("click", () => {
    helpSampleBanner.hidden = true;
  });
}

if (helpPagerPrev) {
  helpPagerPrev.addEventListener("click", () => {
    if (helpPagerPrev.dataset.targetTopicId) {
      selectHelpTopic(helpPagerPrev.dataset.targetTopicId);
    }
  });
}

if (helpPagerNext) {
  helpPagerNext.addEventListener("click", () => {
    if (helpPagerNext.dataset.targetTopicId) {
      selectHelpTopic(helpPagerNext.dataset.targetTopicId);
    }
  });
}

Promise.all([api("/api/state"), api("/api/connectors")])
  .then(async ([state, connectorResult]) => {
    connectors = connectorResult.items;
    applyState(state);
    await refreshCatalog();
    if (state.module === "ETL") {
      await refreshETL();
    } else if (state.module === "Monitoring") {
      await refreshMonitoring();
    } else if (state.module === "Documentation") {
      await refreshDocs();
    } else if (state.module === "Help") {
      await refreshHelp();
    }
  })
  .catch((error) => {
    console.error(error);
    moduleDescription.textContent = `The workspace could not be loaded: ${error.message}`;
  });

