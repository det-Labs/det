// det Web IDE - Catalog & Connections Management Component

function promptCreateFolder() {
    showPromptModal({
        title: "Create Connection Folder",
        label: "Folder Name *",
        placeholder: "e.g. Ingestion, Data Warehouse",
        submitText: "Create Folder",
        onConfirm: (cleanName) => {
            if (!state.customFolders) state.customFolders = new Set();
            state.customFolders.add(cleanName);
            renderExplorer();
            populateFoldersSelect(cleanName);
        }
    });
}

function deleteFolder(event, folderName, count) {
    if (event) event.stopPropagation();
    if (count > 0) {
        alert(`Cannot delete folder '${folderName}' with ${count} connection(s). Move or delete connections first.`);
        return;
    }
    if (!confirm(`Are you sure you want to delete empty folder '${folderName}'?`)) return;
    if (state.customFolders) state.customFolders.delete(folderName);
    renderExplorer();
    populateFoldersSelect();
}

function onFolderAddConnection(event, folderName) {
    if (event) event.stopPropagation();
    openAddConnModal(folderName);
}

function onExplorerTest(event, name) {
    if (event) event.stopPropagation();
    state.selectedConnection = name;
    renderExplorer();
    renderMainStage();
    testSelectedConnection(name);
}

function onExplorerEdit(event, name) {
    if (event) event.stopPropagation();
    openEditConnModal(name);
}

function onExplorerDelete(event, name) {
    if (event) event.stopPropagation();
    deleteSelectedConnection(name);
}

function _buildFolderGroups(connections, customFolders) {
    const allFolders = new Set(customFolders || []);
    connections.forEach((c) => { if (c.folder) allFolders.add(c.folder); });
    const groups = {};
    allFolders.forEach((f) => { groups[f] = []; });
    groups["Ungrouped"] = [];
    connections.forEach((c) => {
        const folder = c.folder || "Ungrouped";
        if (!groups[folder]) groups[folder] = [];
        groups[folder].push(c);
    });
    return groups;
}

function renderCatalogConnectionsExplorer(container) {
    container.innerHTML = "";
    const query = state.searchQuery;
    const groups = _buildFolderGroups(state.connections, state.customFolders);
    const folderKeys = Object.keys(groups).sort((a, b) => a === "Ungrouped" ? 1 : b === "Ungrouped" ? -1 : a.localeCompare(b));
    let renderedAny = false;

    folderKeys.forEach((folderName) => {
        let conns = groups[folderName];
        if (query && !folderName.toLowerCase().includes(query)) {
            conns = conns.filter((c) => c.name.toLowerCase().includes(query) || (c.type && c.type.toLowerCase().includes(query)));
            if (conns.length === 0) return;
        }
        if (folderName === "Ungrouped" && conns.length === 0) return;
        renderedAny = true;
        container.appendChild(_createFolderHeaderElement(folderName, conns.length));
        if (conns.length === 0) {
            const emptyNotice = document.createElement("div");
            emptyNotice.className = "explorer-item sub-item muted";
            emptyNotice.style.fontSize = "0.75rem";
            emptyNotice.textContent = "(Empty folder)";
            container.appendChild(emptyNotice);
        } else {
            conns.forEach((c) => container.appendChild(_createConnectionRowElement(c)));
        }
    });
    if (!renderedAny) container.innerHTML = '<div class="explorer-item muted">No matching connections</div>';
}

function _createFolderHeaderElement(folderName, count) {
    const groupHeader = document.createElement("div");
    groupHeader.className = "explorer-folder-header";
    const canDelete = folderName !== "Ungrouped";
    const folderTarget = folderName === "Ungrouped" ? "" : folderName;
    groupHeader.innerHTML = `
        <span class="explorer-folder-title" title="${folderName}">${icons.folder} <span>${folderName}</span></span>
        <div class="explorer-folder-actions">
            <button class="icon-btn icon-btn-sm" title="Add connection to ${folderName}" onclick="onFolderAddConnection(event, '${escapeJs(folderTarget)}')">${icons.plus}</button>
            <span class="item-badge">${count}</span>
            ${canDelete ? `<button class="icon-btn icon-btn-sm text-danger" title="Delete folder" onclick="deleteFolder(event, '${escapeJs(folderName)}', ${count})">${icons.trash}</button>` : ""}
        </div>
    `;
    return groupHeader;
}

function _createConnectionRowElement(c) {
    const item = document.createElement("div");
    const isSelected = c.name === state.selectedConnection;
    item.className = `explorer-item sub-item ${isSelected ? "active" : ""}`;
    const itemIcon = c.tier === "database" ? icons.database : icons.plug;
    item.innerHTML = `
        <span class="item-icon">${itemIcon}</span>
        <span class="truncate" title="${c.name}">${c.name}</span>
        <span class="item-badge item-badge-hide-on-hover">${c.tier}</span>
        <div class="explorer-item-actions">
            <button class="icon-btn icon-btn-sm" title="Test Connection" onclick="onExplorerTest(event, '${escapeJs(c.name)}')">${icons.test}</button>
            <button class="icon-btn icon-btn-sm" title="Edit Connection" onclick="onExplorerEdit(event, '${escapeJs(c.name)}')">${icons.edit}</button>
            <button class="icon-btn icon-btn-sm text-danger" title="Delete Connection" onclick="onExplorerDelete(event, '${escapeJs(c.name)}')">${icons.trash}</button>
        </div>
    `;
    item.onclick = () => selectConnection(c.name);
    return item;
}

function selectConnection(name) {
    state.selectedConnection = name;
    renderExplorer();
    renderMainStage();
}

function renderCatalogStage(stage) {
    if (!stage) stage = document.getElementById("main-stage");
    if (!stage) return;
    const selectedConn = state.connections && state.connections.length > 0
        ? (state.connections.find((c) => c.name === state.selectedConnection) || state.connections[0])
        : null;
    const defaultQuery = selectedConn
        ? (selectedConn.tier === "database" ? `SHOW TABLES;` : `SELECT * FROM ${selectedConn.name} LIMIT 10;`)
        : "SELECT 1 AS ready;";

    stage.innerHTML = `
        <div class="pane-header">
            <div class="pane-header-row">
                <h2 class="pane-title">Catalog & Connections</h2>
                <button class="btn btn-primary" onclick="openAddConnModal()">${icons.plus} Add Connection</button>
            </div>
            <div class="pane-subtitle">Select a connection from the left explorer to inspect configuration and run queries.</div>
        </div>
        ${selectedConn ? renderSelectedConnectionView(selectedConn) : renderEmptyConnectionView()}
        <div class="scratchpad-card">
            <div class="scratchpad-header">
                <div>
                    <strong>Direct SQL Scratchpad</strong>
                    <span class="pane-subtitle" style="margin-left:0.5rem;">Execute queries directly against active session</span>
                </div>
                <span id="query-status-pill" class="badge badge-entity" style="display:none;"></span>
            </div>
            <textarea id="scratchpad-sql" class="sql-textarea">${defaultQuery}</textarea>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="pane-subtitle" style="font-size:0.75rem;">Press <strong>Ctrl+Enter</strong> to execute query</span>
                <button class="btn btn-primary btn-sm" onclick="runScratchpadQuery()">${icons.play} Run Query</button>
            </div>
            <div class="table-scroll" id="scratchpad-results" style="display:none;"></div>
        </div>
    `;
    setupScratchpadShortcuts();
}

function _renderConfigGrid(options) {
    const keys = Object.keys(options || {});
    if (!keys.length) return '<span class="pane-subtitle">No additional options specified.</span>';
    return keys.map((key) => `
        <div class="config-param">
            <span class="config-param-label">${key}</span>
            <span class="config-param-value">${options[key]}</span>
        </div>
    `).join("");
}

function renderSelectedConnectionView(conn) {
    const mainIcon = conn.tier === "database" ? icons.database : icons.plug;
    const tierBadgeClass = conn.tier === "database" ? "badge-database" : "badge-entity";

    return `
        <div class="conn-detail-card" id="detail-card-${conn.name}">
            <div class="conn-detail-header">
                <div class="conn-detail-title-group">
                    <div class="conn-detail-name">
                        <span>${mainIcon} ${conn.name}</span>
                        ${conn.folder ? `<span class="badge badge-folder">${icons.folder} <span>${conn.folder}</span></span>` : ""}
                        <span class="badge ${tierBadgeClass}">${conn.tier}</span>
                        <span class="item-badge">${conn.type}</span>
                    </div>
                    <div class="pane-subtitle">${conn.description || "No description provided."}</div>
                </div>
            </div>
            <div class="config-summary-box">
                <div class="config-grid">${_renderConfigGrid(conn.options)}</div>
            </div>
            <div class="conn-detail-actions">
                <span id="detail-status-${conn.name}" class="pane-subtitle">● Ready</span>
                <div class="conn-actions-group">
                    <button class="btn btn-secondary btn-sm" onclick="testSelectedConnection('${conn.name}')">${icons.test} Test Connection</button>
                    <button class="btn btn-secondary btn-sm" onclick="openEditConnModal('${conn.name}')">${icons.edit} Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteSelectedConnection('${conn.name}')">${icons.trash} Delete</button>
                </div>
            </div>
        </div>
    `;
}

function renderEmptyConnectionView() {
    return `
        <div class="conn-detail-card" style="text-align:center; padding:2rem;">
            <div style="font-size:2rem; margin-bottom:0.5rem; opacity:0.4;">${icons.plug}</div>
            <h3>No connection selected</h3>
            <p class="pane-subtitle">Choose a connection from the Left Explorer or click "+ Add Connection" above.</p>
        </div>
    `;
}

