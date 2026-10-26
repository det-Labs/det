// det Web IDE - Interactive Zero-Dependency SVG DAG Canvas Renderer

function _computeTopologicalRanks(nodes, edges) {
    const ranks = {}, inDegrees = {}, adj = {};
    nodes.forEach((n) => { ranks[n.id] = 0; inDegrees[n.id] = 0; adj[n.id] = []; });
    edges.forEach((e) => {
        if (adj[e.from]) adj[e.from].push(e.to);
        inDegrees[e.to] = (inDegrees[e.to] || 0) + 1;
    });

    const queue = nodes.filter((n) => (inDegrees[n.id] || 0) === 0).map((n) => n.id);
    while (queue.length > 0) {
        const curr = queue.shift();
        const currRank = ranks[curr] || 0;
        (adj[curr] || []).forEach((nextId) => {
            ranks[nextId] = Math.max(ranks[nextId] || 0, currRank + 1);
            queue.push(nextId);
        });
    }
    return ranks;
}

function _assignNodeCoordinates(nodes, ranks) {
    const columns = {}, positions = {};
    nodes.forEach((n) => {
        const r = ranks[n.id] || 0;
        if (!columns[r]) columns[r] = [];
        columns[r].push(n);
    });

    const colWidth = 265, nodeWidth = 205, nodeHeight = 58, rowHeight = 85;
    Object.keys(columns).forEach((rStr) => {
        const r = parseInt(rStr, 10);
        columns[r].forEach((n, idx) => {
            positions[n.id] = { x: 40 + r * colWidth, y: 40 + idx * rowHeight, w: nodeWidth, h: nodeHeight };
        });
    });
    return positions;
}

function computeDAGLayout(nodes, edges) {
    const ranks = _computeTopologicalRanks(nodes, edges);
    return _assignNodeCoordinates(nodes, ranks);
}

function _buildEdgeSvg(edges, positions) {
    return edges.map((e) => {
        const p1 = positions[e.from], p2 = positions[e.to];
        if (!p1 || !p2) return "";
        const x1 = p1.x + p1.w, y1 = p1.y + p1.h / 2;
        const x2 = p2.x, y2 = p2.y + p2.h / 2;
        const cx1 = x1 + (x2 - x1) * 0.5, cx2 = x2 - (x2 - x1) * 0.5;
        const isHigh = state.highlightedNode && (e.from === state.highlightedNode || e.to === state.highlightedNode);
        return `<path d="M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}" class="dag-edge ${isHigh ? 'highlighted' : ''}" marker-end="url(#dag-arrow${isHigh ? '-active' : ''})"/>`;
    }).join("");
}

function _getNodeTestBadge(n) {
    if (n.type === "source") return null;
    const nodeResults = (state.testResults || []).filter((r) => r.model_name === n.name);
    if (nodeResults.length > 0) {
        const failed = nodeResults.filter((r) => !r.passed).length;
        if (failed > 0) {
            return { text: `✗ ${failed} fail`, color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)" };
        }
        return { text: `✓ ${nodeResults.length} pass`, color: "#10b981", bg: "rgba(16, 185, 129, 0.15)" };
    }
    const count = n.tests_count || (n.tests ? n.tests.length : 0);
    if (count > 0) {
        return { text: `${count} tests`, color: "var(--muted)", bg: "var(--surface)" };
    }
    return { text: "no tests", color: "var(--muted)", bg: "var(--surface)" };
}

function _buildNodeSvg(n, p, clickFn = "selectDAGNode") {
    const isSel = state.selectedModel === n.id;
    const isHigh = state.highlightedNode === n.id;
    const isSource = n.type === "source";
    const iconSvg = isSource ? icons.plug : icons.model;
    const badgeText = n.materialized || n.type;
    const badgeColor = isSource ? "#10b981" : (n.materialized === "table" ? "#a855f7" : "#3b82f6");
    const testBadge = _getNodeTestBadge(n);

    const testBadgeSvg = testBadge ? `
        <g onclick="event.stopPropagation(); ${clickFn}('${escapeJs(n.id)}', 'tests');" style="cursor:pointer;" title="Click to view tests">
            <rect x="${p.x + 72}" y="${p.y + 34}" width="78" height="16" rx="3" fill="${testBadge.bg}" stroke="var(--border)"/>
            <text x="${p.x + 76}" y="${p.y + 46}" fill="${testBadge.color}" font-size="9" font-weight="600" font-family="monospace">${testBadge.text}</text>
        </g>
    ` : "";

    return `
        <g class="dag-node ${isSel ? 'active' : ''} ${isHigh ? 'highlighted' : ''}" onclick="${clickFn}('${escapeJs(n.id)}')">
            <rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" fill="var(--surface-card)" stroke="var(--border)" class="dag-node-rect"/>
            <g transform="translate(${p.x + 12}, ${p.y + 14})">
                ${iconSvg}
                <text x="22" y="11" fill="var(--text)" font-size="12" font-weight="600" font-family="-apple-system, sans-serif">${n.name}</text>
            </g>
            <rect x="${p.x + 12}" y="${p.y + 34}" width="54" height="16" rx="3" fill="var(--surface)" stroke="var(--border)"/>
            <text x="${p.x + 16}" y="${p.y + 46}" fill="${badgeColor}" font-size="10" font-weight="500" font-family="monospace">${badgeText}</text>
            ${testBadgeSvg}
        </g>
    `;
}

function renderDAGToContainer(container, dag, clickFn = "selectDAGNode") {
    if (!container) return;
    if (!dag || !dag.nodes || !dag.nodes.length) {
        container.innerHTML = '<div style="padding:2rem; text-align:center;" class="pane-subtitle">No models or DAG nodes to visualize in this pipeline.</div>';
        return;
    }
    const positions = computeDAGLayout(dag.nodes, dag.edges);
    let maxX = 600, maxY = 350;
    Object.values(positions).forEach((p) => {
        if (p.x + p.w + 60 > maxX) maxX = p.x + p.w + 60;
        if (p.y + p.h + 60 > maxY) maxY = p.y + p.h + 60;
    });

    const edgesHtml = _buildEdgeSvg(dag.edges, positions);
    const nodesHtml = dag.nodes.map((n) => positions[n.id] ? _buildNodeSvg(n, positions[n.id], clickFn) : "").join("");
    container.innerHTML = `
        <svg class="dag-svg" width="${maxX}" height="${maxY}" viewBox="0 0 ${maxX} ${maxY}">
            <defs>
                <marker id="dag-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="var(--border)"/></marker>
                <marker id="dag-arrow-active" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="var(--accent)"/></marker>
            </defs>
            <g class="dag-edges-layer">${edgesHtml}</g>
            <g class="dag-nodes-layer">${nodesHtml}</g>
        </svg>
    `;
}

function renderDAGCanvas() {
    renderDAGToContainer(document.getElementById("dag-svg-container"), state.activeDag || { nodes: [], edges: [] }, "selectDAGNode");
}

function selectDAGNode(nodeId, section = null) {
    state.highlightedNode = nodeId;
    if (section === "tests") {
        state.modelTestsCollapsed = false;
        state.modelSqlCollapsed = true;
        state.modelSchemaCollapsed = true;
        state.dagCanvasCollapsed = true;
        const dagCard = document.getElementById("dag-canvas-card");
        if (dagCard) dagCard.classList.add("collapsed");
    }
    const pipeline = state.pipelines.find((p) => p.name === state.selectedPipeline);
    const isModel = pipeline?.models?.some((m) => m.name === nodeId);
    if (isModel) {
        state.selectedModel = nodeId;
        renderSubExplorerModels();
    }
    renderDAGCanvas();
    const inspector = document.getElementById("model-inspector-container");
    if (inspector && isModel) {
        const modelDef = pipeline.models.find((m) => m.name === nodeId);
        inspector.innerHTML = renderModelInspector(modelDef);
        if (section === "tests") {
            setTimeout(() => document.getElementById("model-tests-card")?.scrollIntoView({ behavior: "smooth" }), 60);
        }
    }
}
