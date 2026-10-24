// det Web IDE - SQL Scratchpad Runner & Diagnostics
function setupScratchpadShortcuts() {
    const textarea = document.getElementById("scratchpad-sql");
    if (!textarea) return;
    textarea.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            runScratchpadQuery();
        }
    });
}

async function runScratchpadQuery() {
    const textarea = document.getElementById("scratchpad-sql");
    const resultsContainer = document.getElementById("scratchpad-results");
    const statusPill = document.getElementById("query-status-pill");
    const query = textarea ? textarea.value.trim() : "";
    if (!query) return;

    if (statusPill) {
        statusPill.style.display = "inline-block";
        statusPill.className = "badge badge-entity";
        statusPill.textContent = "Executing...";
    }
    if (resultsContainer) {
        resultsContainer.style.display = "block";
        resultsContainer.innerHTML = '<div style="padding:0.75rem;" class="pane-subtitle">Executing query against session...</div>';
    }

    try {
        const res = await fetch("/api/catalog/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });
        const data = await res.json();
        if (data.status === "error" || data.error) {
            if (statusPill) {
                statusPill.className = "badge btn-danger";
                statusPill.textContent = "Error";
            }
            if (resultsContainer) {
                resultsContainer.style.display = "block";
                resultsContainer.innerHTML = `<div style="padding:1rem; color:#ef4444; font-family:monospace; font-size:0.8rem;">${data.error}</div>`;
            }
            return;
        }
        if (statusPill) {
            statusPill.className = "badge badge-database";
            statusPill.textContent = `${data.row_count} rows in ${data.duration_ms}ms`;
        }
        if (resultsContainer) {
            renderQueryResultsTable(data.columns, data.rows, resultsContainer);
        }
    } catch (err) {
        if (statusPill) {
            statusPill.className = "badge btn-danger";
            statusPill.textContent = "Query failed";
        }
        if (resultsContainer) {
            resultsContainer.style.display = "block";
            resultsContainer.innerHTML = `<div style="padding:1rem; color:#ef4444;">${err.message}</div>`;
        }
    }
}

function renderQueryResultsTable(columns, rows, container) {
    container.style.display = "block";
    if (!columns || !columns.length) {
        container.innerHTML = '<div style="padding:0.75rem;" class="pane-subtitle">Query executed successfully (0 columns returned).</div>';
        return;
    }
    let html = '<table class="query-table"><thead><tr>';
    columns.forEach((col) => { html += `<th>${col}</th>`; });
    html += "</tr></thead><tbody>";
    rows.forEach((r) => {
        html += "<tr>";
        r.forEach((cell) => { html += `<td>${cell === null ? '<span class="muted">null</span>' : cell}</td>`; });
        html += "</tr>";
    });
    html += "</tbody></table>";
    container.innerHTML = html;
}

async function testSelectedConnection(name) {
    const statusLabel = document.getElementById(`detail-status-${name}`);
    if (statusLabel) {
        statusLabel.textContent = "Testing probe...";
        statusLabel.style.color = "var(--accent)";
    }
    try {
        const res = await fetch("/api/catalog/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
        });
        const data = await res.json();
        if (statusLabel) {
            if (data.healthy) {
                statusLabel.textContent = `● Healthy (${data.latency_ms}ms)`;
                statusLabel.style.color = "var(--success)";
            } else {
                statusLabel.textContent = `✗ Failed`;
                statusLabel.style.color = "#ef4444";
                statusLabel.title = data.error_message || "Probe failed";
            }
        }
    } catch (err) {
        if (statusLabel) {
            statusLabel.textContent = `✗ Error`;
            statusLabel.style.color = "#ef4444";
        }
    }
}

async function deleteSelectedConnection(name) {
    if (!confirm(`Are you sure you want to delete connection '${name}'?`)) return;
    try {
        const res = await fetch("/api/catalog/connections/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
        });
        const data = await res.json();
        if (data.status === "ok") {
            state.selectedConnection = null;
            await reloadCatalogAndExplorer();
        } else {
            alert(data.error || "Failed to delete connection.");
        }
    } catch (err) {
        alert("Error deleting connection: " + err.message);
    }
}

