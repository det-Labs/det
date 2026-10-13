"""Build static documentation and interactive web showcase for GitHub Pages."""

import shutil
from pathlib import Path

from det.docs import PipelineDocsGenerator
from det.sample_data import install_sample_data
from det.workspace import Workspace


def build_site(output_dir: str = "_site") -> Path:
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Initialize temporary workspace and install NovaMart sample warehouse
    ws_dir = Path("demo_workspace").resolve()
    ws = Workspace(ws_dir)
    install_sample_data(ws_dir)

    # 2. Generate static HTML documentation for every pipeline
    gen = PipelineDocsGenerator(ws_dir)
    doc_count = 0
    for p_path in ws_dir.glob("pipelines/*/*.yaml"):
        p_key = f"{p_path.parent.name}/{p_path.stem}"
        try:
            res = gen.save(p_key, doc_format="html")
            print(f"Generated doc: {res['saved_path']}")
            doc_count += 1
        except Exception as e:
            print(f"Warning: could not generate doc for {p_key}: {e}")

    print(f"Generated {doc_count} pipeline documentation files.")

    # 3. Copy pipeline documentation to output
    docs_src = ws_dir / "documentation"
    if docs_src.is_dir():
        for item in docs_src.iterdir():
            dest = out_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    # 4. Copy static UI assets for interactive Web IDE showcase
    try:
        from generate_demo_data import generate_demo_data
        generate_demo_data()
    except Exception as e:
        print(f"Notice: skipped runtime demo-data generation: {e}")

    ui_src = Path(__file__).parent.parent / "src" / "det" / "ui"
    if ui_src.is_dir():
        for f in ui_src.iterdir():
            if f.is_file():
                if f.name == "index.html":
                    shutil.copy2(f, out_path / "demo.html")
                else:
                    shutil.copy2(f, out_path / f.name)

    # 5. Write portal landing page
    landing_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>det — Data Engineering Tool</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col items-center justify-center p-6 font-sans">
  <div class="max-w-2xl w-full bg-slate-800 border border-slate-700 rounded-2xl p-8 shadow-2xl text-center">
    <div class="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 text-3xl font-black shadow-lg shadow-blue-500/20">
      d
    </div>
    <h1 class="text-3xl font-bold tracking-tight mb-2">det &mdash; Data Engineering Tool</h1>
    <p class="text-slate-400 mb-6 text-sm">
      Fast, local-first SQL ETL workspace &amp; pipeline orchestrator powered by Apache DataFusion &amp; Apache Arrow.
    </p>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 my-6 text-left">
      <a href="demo.html" class="p-5 bg-slate-900/60 border border-slate-700/60 rounded-xl hover:border-blue-500 transition-all block group">
        <div class="font-semibold text-blue-400 group-hover:text-blue-300 flex items-center gap-2">
          <i class="fa-solid fa-desktop"></i> Interactive Web IDE
        </div>
        <p class="text-xs text-slate-400 mt-2">
          Explore visual DAG topologies, SQL editor, catalog viewer, and live data previews.
        </p>
      </a>
      <a href="https://github.com/det-Labs/det" class="p-5 bg-slate-900/60 border border-slate-700/60 rounded-xl hover:border-emerald-500 transition-all block group">
        <div class="font-semibold text-emerald-400 group-hover:text-emerald-300 flex items-center gap-2">
          <i class="fa-brands fa-github"></i> GitHub Repository
        </div>
        <p class="text-xs text-slate-400 mt-2">
          Star the repo, explore source code, report issues, and submit custom connectors.
        </p>
      </a>
    </div>

    <div class="bg-slate-950 rounded-xl p-4 font-mono text-xs text-slate-300 text-left border border-slate-800">
      <span class="text-slate-500"># Install &amp; launch in 30 seconds</span><br>
      <span class="text-blue-400">pip</span> install det-core<br>
      <span class="text-blue-400">det</span> sample-data<br>
      <span class="text-blue-400">det</span> gui
    </div>
  </div>
  <footer class="mt-8 text-xs text-slate-500">
    Maintained by Saurabh Rai &amp; det-Labs &bull; Released under MIT License
  </footer>
</body>
</html>
"""
    (out_path / "index.html").write_text(landing_html, encoding="utf-8")
    print(f"Site built successfully in: {out_path}")
    return out_path


if __name__ == "__main__":
    build_site()
