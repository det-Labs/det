// det Web IDE - Catalog Connection Add/Edit Modals

function onFolderSelectChange(val) {
    const customInput = document.getElementById("modal-conn-folder-custom");
    if (!customInput) return;
    customInput.style.display = (val === "__new__") ? "block" : "none";
    if (val === "__new__") customInput.focus();
}

function populateFoldersSelect(currentFolder = "") {
    const selector = document.getElementById("modal-conn-folder-select");
    const customInput = document.getElementById("modal-conn-folder-custom");
    if (!selector) return;

    selector.innerHTML = '<option value="">None (Ungrouped)</option><option value="__new__">+ Create New Folder...</option>';
    const allFolders = new Set(state.customFolders || []);
    state.connections.forEach((c) => { if (c.folder) allFolders.add(c.folder); });

    [...allFolders].sort().forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f; opt.textContent = f;
        selector.insertBefore(opt, selector.lastElementChild);
    });

    if (currentFolder && allFolders.has(currentFolder)) {
        selector.value = currentFolder; customInput.style.display = "none";
    } else if (currentFolder) {
        selector.value = "__new__"; customInput.style.display = "block"; customInput.value = currentFolder;
    } else {
        selector.value = ""; customInput.style.display = "none"; customInput.value = "";
    }
}

function openAddConnModal(preselectedFolder = "") {
    state.isEditing = false;
    document.getElementById("modal-title").textContent = preselectedFolder ? `Add Connection to '${preselectedFolder}'` : "Add Catalog Connection";
    document.getElementById("modal-conn-name").value = "";
    document.getElementById("modal-conn-name").readOnly = false;
    document.getElementById("modal-conn-desc").value = "";
    document.getElementById("modal-test-result").style.display = "none";
    populateFoldersSelect(preselectedFolder || "");
    document.getElementById("modal-conn-tier").value = "entity";
    onTierChange();
    document.getElementById("conn-modal").style.display = "flex";
}

function openEditConnModal(connName) {
    const conn = state.connections.find((c) => c.name === connName);
    if (!conn) return;

    state.isEditing = true;
    document.getElementById("modal-title").textContent = `Edit Connection: ${conn.name}`;
    document.getElementById("modal-conn-name").value = conn.name;
    document.getElementById("modal-conn-name").readOnly = true;
    document.getElementById("modal-conn-desc").value = conn.description || "";
    document.getElementById("modal-test-result").style.display = "none";
    populateFoldersSelect(conn.folder || "");

    document.getElementById("modal-conn-tier").value = conn.tier;
    onTierChange();
    document.getElementById("modal-conn-type").value = conn.type;
    onConnectorTypeChange();

    const opts = conn.options || {};
    const creds = conn.credentials || {};
    document.querySelectorAll("#dynamic-fields-container [data-field-name]").forEach((input) => {
        const fName = input.dataset.fieldName;
        if (opts[fName] !== undefined) input.value = opts[fName];
        if (creds[fName] !== undefined) input.value = creds[fName];
    });

    document.getElementById("conn-modal").style.display = "flex";
}

function closeConnModal() {
    document.getElementById("conn-modal").style.display = "none";
}

function onTierChange() {
    const tier = document.getElementById("modal-conn-tier").value;
    const typeSelect = document.getElementById("modal-conn-type");
    typeSelect.innerHTML = "";
    const available = state.connectors.filter((c) => c.tier === tier);
    if (tier === "database" && !available.some((c) => c.key === "duckdb")) {
        const opt = document.createElement("option");
        opt.value = "duckdb"; opt.textContent = "DuckDB (Embedded)";
        typeSelect.appendChild(opt);
    }
    available.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.key; opt.textContent = `${c.label || c.key.toUpperCase()}`;
        typeSelect.appendChild(opt);
    });
    onConnectorTypeChange();
}

function onConnectorTypeChange() {
    const typeSelect = document.getElementById("modal-conn-type");
    const container = document.getElementById("dynamic-fields-container");
    const selectedKey = typeSelect.value;
    container.innerHTML = "";

    if (selectedKey === "duckdb") {
        container.style.display = "grid";
        container.innerHTML = `
            <div class="form-group" style="grid-column: 1 / -1;">
                <label>Database Path *</label>
                <input type="text" class="form-input" data-field-name="path" value=":memory:" placeholder=":memory: or path/to/file.duckdb">
            </div>
        `;
        return;
    }
    const connector = state.connectors.find((c) => c.key === selectedKey);
    if (!connector || !connector.fields || !connector.fields.length) {
        container.style.display = "none";
        return;
    }
    container.style.display = "grid";
    connector.fields.forEach((f) => _renderConnectorField(f, container));
}

function _renderConnectorField(f, container) {
    const group = document.createElement("div");
    group.className = "form-group";
    const label = document.createElement("label");
    label.textContent = `${f.label || f.name} ${f.required ? "*" : ""}`;
    group.appendChild(label);

    let input;
    if (f.choices && f.choices.length) {
        input = document.createElement("select");
        input.className = "form-input";
        f.choices.forEach((choice) => {
            const opt = document.createElement("option");
            opt.value = choice; opt.textContent = choice;
            if (f.default === choice) opt.selected = true;
            input.appendChild(opt);
        });
    } else if (f.type === "boolean") {
        input = document.createElement("select");
        input.className = "form-input";
        input.innerHTML = '<option value="true">True</option><option value="false">False</option>';
        if (f.default === false) input.value = "false";
    } else {
        input = document.createElement("input");
        input.type = f.is_secret || f.type === "password" ? "password" : "text";
        input.className = "form-input";
        input.placeholder = f.placeholder || f.description || "";
        if (f.default !== null && f.default !== undefined) input.value = f.default;
    }
    input.dataset.fieldName = f.name;
    group.appendChild(input);
    container.appendChild(group);
}

function collectModalFormData() {
    const name = document.getElementById("modal-conn-name").value.trim();
    const folderSelectVal = document.getElementById("modal-conn-folder-select").value;
    const folder = folderSelectVal === "__new__" ? (document.getElementById("modal-conn-folder-custom").value || "").trim() : folderSelectVal;
    const tier = document.getElementById("modal-conn-tier").value;
    const type = document.getElementById("modal-conn-type").value;
    const description = document.getElementById("modal-conn-desc").value.trim();

    const options = {};
    const credentials = {};
    const connector = state.connectors.find((c) => c.key === type);

    document.querySelectorAll("#dynamic-fields-container [data-field-name]").forEach((input) => {
        const fieldName = input.dataset.fieldName;
        const val = input.value;
        const fieldMeta = connector?.fields?.find((f) => f.name === fieldName);
        if (val !== "") {
            if (fieldMeta?.is_secret) credentials[fieldName] = val;
            else options[fieldName] = val;
        }
    });

    return { name, folder, tier, type, description, options, credentials };
}

async function testModalConnection() {
    const data = collectModalFormData();
    const resultBox = document.getElementById("modal-test-result");
    resultBox.style.display = "block";
    resultBox.className = "test-result-box";
    resultBox.textContent = "Testing connection probe...";
    try {
        const res = await fetch("/api/catalog/test", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
        });
        const resData = await res.json();
        if (resData.healthy) {
            resultBox.className = "test-result-box test-result-success";
            resultBox.textContent = `✓ Success! Connection reachable (${resData.latency_ms}ms)`;
        } else {
            resultBox.className = "test-result-box test-result-fail";
            resultBox.textContent = `✗ Probe Failed: ${resData.error_message || "Could not connect"}`;
        }
    } catch (err) {
        resultBox.className = "test-result-box test-result-fail";
        resultBox.textContent = `✗ Test Error: ${err.message}`;
    }
}

async function saveModalConnection() {
    const data = collectModalFormData();
    if (!data.name || !isValidIdentifier(data.name)) {
        alert("Invalid connection name! Names must start with a letter/underscore and contain only letters, numbers, or underscores (no spaces or special characters).");
        return;
    }
    try {
        const res = await fetch("/api/catalog/connections", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
        });
        const resData = await res.json();
        if (resData.status === "ok") {
            if (data.folder && state.customFolders) state.customFolders.add(data.folder);
            state.selectedConnection = data.name;
            closeConnModal();
            await reloadCatalogAndExplorer();
        } else {
            alert(resData.error || "Failed to save connection.");
        }
    } catch (err) {
        alert("Save error: " + err.message);
    }
}

async function reloadCatalogAndExplorer() {
    const [explorerRes, connectionsRes] = await Promise.all([
        fetch("/api/explorer").then((r) => r.json()),
        fetch("/api/catalog/connections").then((r) => r.json()),
    ]);
    state.explorer = explorerRes;
    state.connections = connectionsRes;
    if (!state.customFolders) state.customFolders = new Set();
    state.connections.forEach((c) => { if (c.folder) state.customFolders.add(c.folder); });
    if (!state.selectedConnection && state.connections.length > 0) {
        state.selectedConnection = state.connections[0].name;
    }
    renderExplorer();
    renderMainStage();
}

