// det Web IDE - Interactive Guided Demo Tour & Showcase Engine

const demoTour = {
    currentStep: 0,
    isPlaying: false,
    playTimer: null,
    overlayEl: null,
    cardEl: null,

    steps: [
        {
            target: ".brand",
            title: "Welcome to det",
            content: "<strong>det</strong> is a modern, local-first SQL ETL & pipeline orchestrator powered by <strong>DuckDB 2.0</strong>. This quick 60-second guided tour walks you through the core platform workflows.",
            action: async () => {},
        },
        {
            target: "#explorer-bar",
            title: "Data Catalog & Direct Mounting",
            content: "Declare sources in <code>catalog/connections.yaml</code>. DuckDB binds virtual views directly to local <strong>Parquet</strong>, <strong>CSV</strong>, and <strong>JSON</strong> files with zero prior ingestion or storage duplication.",
            action: async () => {
                if (typeof switchModule === "function") switchModule("catalog");
            },
        },
        {
            target: "#dag-canvas-card",
            title: "Automated Lineage & Dependency DAG",
            content: "<code>det</code> parses your SQL models and <code>{{ ref(...) }}</code> macros to automatically construct an interactive dependency graph with zero cycle risk and topological execution.",
            action: async () => {
                if (typeof switchModule === "function") switchModule("pipelines");
                if (typeof selectPipeline === "function") selectPipeline("retail_medallion");
            },
        },
        {
            target: "#model-sql-card",
            title: "Model Inspector & Analytical SQL",
            content: "View clean source SQL or toggle to compiled executable SQL. Features complex analytical transformations: <strong>window functions</strong>, rolling lag metrics, and multi-stage CTE chains.",
            action: async () => {
                if (typeof switchModule === "function") switchModule("pipelines");
                const pipeline = state.pipelines.find((p) => p.name === "retail_medallion");
                const model = pipeline?.models?.find((m) => m.name === "gold_customer_360") || pipeline?.models?.[0];
                if (model && typeof selectPipeline === "function") {
                    state.selectedModel = model.name;
                    state.highlightedNode = model.name;
                    if (typeof renderSubExplorerModels === "function") renderSubExplorerModels();
                    if (typeof renderPipelinesDAGStage === "function") renderPipelinesDAGStage();
                }
            },
        },
        {
            target: "#model-schema-card",
            title: "Dual-Mode Schema & Column Docs",
            content: "Auto-introspect column types directly from DuckDB. Document column descriptions inline in <strong>Table View</strong> or switch to <strong>Raw YAML</strong>—both stay 100% in sync with <code>schema.yml</code>.",
            action: async () => {
                const el = document.getElementById("model-schema-card");
                if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
            },
        },
        {
            target: ".dag-toolbar-actions",
            title: "Command Ribbon: Compile, Test & Run",
            content: "Execute the entire pipeline in topological order, validate data quality assertions, or compile static documentation portals. Everything runs in-memory at native DuckDB speed!",
            action: async () => {
                const toolbar = document.querySelector(".dag-toolbar");
                if (toolbar) toolbar.scrollIntoView({ behavior: "smooth", block: "start" });
            },
        },
    ],

    async start() {
        this.currentStep = 0;
        this.createTourDOM();
        await this.goToStep(0);
        document.addEventListener("keydown", this._handleKey);
    },

    stop() {
        this.pause();
        if (this.overlayEl) this.overlayEl.remove();
        if (this.cardEl) this.cardEl.remove();
        this.overlayEl = null;
        this.cardEl = null;
        document.removeEventListener("keydown", this._handleKey);
    },

    createTourDOM() {
        if (this.overlayEl) this.overlayEl.remove();
        if (this.cardEl) this.cardEl.remove();

        this.overlayEl = document.createElement("div");
        this.overlayEl.className = "tour-spotlight-overlay";

        this.cardEl = document.createElement("div");
        this.cardEl.className = "tour-tooltip-card";

        document.body.appendChild(this.overlayEl);
        document.body.appendChild(this.cardEl);
    },

    async goToStep(idx) {
        if (idx < 0 || idx >= this.steps.length) return;
        this.currentStep = idx;
        const step = this.steps[idx];

        if (step.action) await step.action();
        await new Promise((r) => setTimeout(r, 200));

        const targetEl = document.querySelector(step.target);
        this.positionCardAndSpotlight(targetEl, step);
    },

    positionCardAndSpotlight(targetEl, step) {
        if (!this.cardEl || !this.overlayEl) return;
        const isFirst = this.currentStep === 0;
        const isLast = this.currentStep === this.steps.length - 1;

        this.cardEl.innerHTML = `
            <div class="tour-card-header">
                <div class="tour-step-pill">Step ${this.currentStep + 1} of ${this.steps.length}</div>
                <button class="tour-btn-close" title="Exit Tour" onclick="demoTour.stop()">✕</button>
            </div>
            <div class="tour-card-title">${step.title}</div>
            <div class="tour-card-body">${step.content}</div>
            <div class="tour-card-footer">
                <div class="tour-actions-left">
                    <button class="tour-btn tour-btn-secondary" onclick="demoTour.togglePlay()">
                        ${this.isPlaying ? "❚❚ Pause" : "▶ Auto"}
                    </button>
                </div>
                <div class="tour-actions-right">
                    <button class="tour-btn tour-btn-secondary" ${isFirst ? "disabled" : ""} onclick="demoTour.prev()">← Back</button>
                    <button class="tour-btn tour-btn-primary" onclick="${isLast ? 'demoTour.stop()' : 'demoTour.next()'}">
                        ${isLast ? "Finish Tour ✓" : "Next →"}
                    </button>
                </div>
            </div>
        `;

        if (targetEl) {
            const rect = targetEl.getBoundingClientRect();
            this.overlayEl.style.display = "block";
            this.overlayEl.style.top = `${Math.max(0, rect.top - 6)}px`;
            this.overlayEl.style.left = `${Math.max(0, rect.left - 6)}px`;
            this.overlayEl.style.width = `${rect.width + 12}px`;
            this.overlayEl.style.height = `${rect.height + 12}px`;

            // Position card below or above target
            const cardWidth = 360;
            let top = rect.bottom + 14;
            let left = rect.left + (rect.width / 2) - (cardWidth / 2);

            if (top + 220 > window.innerHeight) {
                top = Math.max(10, rect.top - 230);
            }
            if (left < 16) left = 16;
            if (left + cardWidth > window.innerWidth - 16) {
                left = window.innerWidth - cardWidth - 16;
            }

            this.cardEl.style.top = `${top}px`;
            this.cardEl.style.left = `${left}px`;
            targetEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
        } else {
            this.overlayEl.style.display = "none";
            this.cardEl.style.top = "80px";
            this.cardEl.style.left = "calc(50% - 180px)";
        }
    },

    next() {
        if (this.currentStep < this.steps.length - 1) {
            this.goToStep(this.currentStep + 1);
        } else {
            this.stop();
        }
    },

    prev() {
        if (this.currentStep > 0) {
            this.goToStep(this.currentStep - 1);
        }
    },

    togglePlay() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    },

    play() {
        this.isPlaying = true;
        this.goToStep(this.currentStep);
        this.playTimer = setInterval(() => {
            if (this.currentStep < this.steps.length - 1) {
                this.next();
            } else {
                this.stop();
            }
        }, 6000);
    },

    pause() {
        this.isPlaying = false;
        if (this.playTimer) {
            clearInterval(this.playTimer);
            this.playTimer = null;
        }
        if (this.cardEl) {
            const btn = this.cardEl.querySelector(".tour-actions-left button");
            if (btn) btn.textContent = "▶ Auto";
        }
    },

    _handleKey: (e) => {
        if (e.key === "ArrowRight") demoTour.next();
        else if (e.key === "ArrowLeft") demoTour.prev();
        else if (e.key === "Escape") demoTour.stop();
    },
};

// Global trigger invoked from title bar button
async function triggerDemoMode() {
    const btn = document.getElementById("btn-demo-mode");
    if (btn) {
        btn.innerHTML = `<span class="spinner-sm"></span> <span>Loading Demo...</span>`;
        btn.disabled = true;
    }

    try {
        const res = await fetch("/api/demo/setup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });
        const rep = await res.json();
        if (rep.status === "ok") {
            await loadInitialData();
            if (typeof renderNavigation === "function") renderNavigation();
            if (typeof renderExplorer === "function") renderExplorer();
            if (typeof renderMainStage === "function") renderMainStage();
            demoTour.start();
        } else {
            alert(`Demo setup failed: ${rep.error}`);
        }
    } catch (err) {
        console.error("Failed to setup demo mode:", err);
        alert(`Error loading demo workspace: ${err.message}`);
    } finally {
        if (btn) {
            btn.innerHTML = `<span>✨</span> <span>Demo Mode</span>`;
            btn.disabled = false;
        }
    }
}

