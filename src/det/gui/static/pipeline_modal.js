// det Web IDE - Model Creation & Inspector Modal Component

let _promptModalCallback = null;

function showPromptModal({ title, label, placeholder, defaultValue, submitText, onConfirm }) {
    const titleEl = document.getElementById("prompt-modal-title");
    const labelEl = document.getElementById("prompt-modal-label");
    const input = document.getElementById("prompt-modal-input");
    const submitBtn = document.getElementById("prompt-modal-submit");
    if (titleEl) titleEl.textContent = title;
    if (labelEl) labelEl.textContent = label || "Name *";
    if (input) {
        input.placeholder = placeholder || "Enter name...";
        input.value = defaultValue || "";
        input.onkeydown = (e) => {
            if (e.key === "Enter") { e.preventDefault(); submitPromptModal(); }
            if (e.key === "Escape") closePromptModal();
        };
    }
    if (submitBtn) submitBtn.textContent = submitText || "Create";
    _promptModalCallback = onConfirm;
    const modal = document.getElementById("prompt-modal");
    if (modal) modal.style.display = "flex";
    setTimeout(() => { if (input) { input.focus(); input.select(); } }, 50);
}

function closePromptModal() {
    const modal = document.getElementById("prompt-modal");
    if (modal) modal.style.display = "none";
    _promptModalCallback = null;
}

function submitPromptModal() {
    const input = document.getElementById("prompt-modal-input");
    const val = (input?.value || "").trim();
    if (!val) { if (input) input.focus(); return; }
    const cb = _promptModalCallback;
    closePromptModal();
    if (cb) cb(val);
}

function openAddModelModal(preselectedFolder = "") {
    const sel = document.getElementById("model-modal-pipeline");
    if (sel) {
        sel.innerHTML = "";
        state.pipelines.forEach((p) => {
            const opt = document.createElement("option");
            opt.value = p.name; opt.textContent = p.name;
            if (p.name === state.selectedPipeline) opt.selected = true;
            sel.appendChild(opt);
        });
    }
    const folderInput = document.getElementById("model-modal-folder");
    if (folderInput) folderInput.value = preselectedFolder || "staging";
    document.getElementById("model-modal-name").value = "";
    document.getElementById("model-modal-sql").value = "SELECT 1 AS sample_id;";
    document.getElementById("model-modal").style.display = "flex";
}

function closeModelModal() {
    document.getElementById("model-modal").style.display = "none";
}

async function saveNewModel() {
    const project = document.getElementById("model-modal-pipeline").value;
    const name = document.getElementById("model-modal-name").value.trim();
    const folder = document.getElementById("model-modal-folder").value.trim();
    const mat = document.getElementById("model-modal-mat").value;
    let sql = document.getElementById("model-modal-sql").value.trim();

    if (!name || !isValidIdentifier(name)) {
        alert("Invalid model name! Names must start with a letter/underscore and contain only letters, numbers, or underscores (no spaces or special characters).");
        return;
    }
    if (!sql.includes("config(")) sql = `{{ config(materialized='${mat}') }}\n\n${sql}`;

    try {
        const res = await fetch("/api/pipelines/model/save", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project, name, folder, sql }),
        });
        const resp = await res.json();
        if (resp.status === "ok") {
            closeModelModal();
            await reloadPipelinesData();
            selectPipeline(project);
        } else {
            alert(resp.error || "Failed to save model.");
        }
    } catch (err) { alert("Save error: " + err.message); }
}

async function onDeleteModel(event, name) {
    if (event) event.stopPropagation();
    if (!confirm(`Are you sure you want to delete model '${name}'?`)) return;
    try {
        const res = await fetch("/api/pipelines/model/delete", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline, name }),
        });
        const resp = await res.json();
        if (resp.status === "ok") {
            await reloadPipelinesData();
            selectPipeline(state.selectedPipeline);
        } else {
            alert(resp.error || "Failed to delete model.");
        }
    } catch (err) { alert("Delete error: " + err.message); }
}

async function saveCurrentModelCode(name) {
    const sql = document.getElementById("model-inspector-sql")?.value;
    if (sql === undefined) return;
    try {
        const res = await fetch("/api/pipelines/model/save", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: state.selectedPipeline, name, sql }),
        });
        const resp = await res.json();
        if (resp.status === "ok") {
            const resBox = document.getElementById("model-run-result");
            if (resBox) {
                resBox.style.display = "block";
                resBox.className = "test-result-box test-result-success";
                resBox.textContent = `✓ Model '${name}' saved successfully.`;
            }
            await reloadPipelinesData();
        } else {
            alert(resp.error || "Failed to save model.");
        }
    } catch (err) { alert("Save error: " + err.message); }
}
