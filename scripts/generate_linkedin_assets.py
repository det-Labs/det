"""Generate LinkedIn Announcement Assets for det-core:
1. 7-Slide High-Resolution LinkedIn Carousel Images (PNG)
2. Compiled Multi-Page LinkedIn Carousel PDF (det_linkedin_carousel.pdf)
3. 1200x630 Landscape Announcement Banner (det_launch_banner.png)
4. Full HD 1080p MP4 Product Walkthrough Video (det_product_walkthrough.mp4)
"""

from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUTPUT_DIR = Path(__file__).parent.parent / "media" / "linkedin"
SLIDES_DIR = OUTPUT_DIR / "slides"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SLIDES_DIR.mkdir(parents=True, exist_ok=True)

FONT_REGULAR_PATH = "C:\\Windows\\Fonts\\segoeui.ttf"
FONT_BOLD_PATH = "C:\\Windows\\Fonts\\segoeuib.ttf"
FONT_CODE_PATH = "C:\\Windows\\Fonts\\consola.ttf"

def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

# Color Palette (Deep Modern Tech Aesthetic)
BG_COLOR = (15, 23, 42)          # Slate-900 #0f172a
CARD_BG = (30, 41, 59)           # Slate-800 #1e293b
CARD_BORDER = (51, 65, 85)       # Slate-700 #334155
ACCENT_BLUE = (37, 99, 235)      # Blue-600 #2563eb
ACCENT_CYAN = (56, 189, 248)     # Sky-400 #38bdf8
ACCENT_GREEN = (52, 211, 153)    # Emerald-400 #34d399
ACCENT_AMBER = (251, 191, 36)    # Amber-400 #fbbf24
ACCENT_RED = (248, 113, 113)     # Red-400 #f87171
TEXT_WHITE = (248, 250, 252)     # Slate-50 #f8fafc
TEXT_MUTED = (148, 163, 184)     # Slate-400 #94a3b8
CODE_BG = (10, 15, 29)           # Ultra Dark Slate

def draw_header(draw: ImageDraw.ImageDraw, slide_num: int, total_slides: int, eyebrow: str):
    # Brand Pill
    draw.rounded_rectangle([60, 60, 140, 105], radius=10, fill=ACCENT_BLUE)
    f_pill = get_font(FONT_BOLD_PATH, 24)
    draw.text((82, 68), "det", font=f_pill, fill=TEXT_WHITE)

    # Eyebrow
    f_eye = get_font(FONT_BOLD_PATH, 22)
    draw.text((160, 72), eyebrow.upper(), font=f_eye, fill=ACCENT_CYAN)

    # Slide Counter
    f_count = get_font(FONT_REGULAR_PATH, 20)
    counter_text = f"{slide_num}/{total_slides}"
    draw.text((1080 - 60 - 50, 72), counter_text, font=f_count, fill=TEXT_MUTED)

def draw_footer(draw: ImageDraw.ImageDraw, callout: str = "Swipe to explore →"):
    draw.line([60, 1010, 1020, 1010], fill=CARD_BORDER, width=2)
    f_brand = get_font(FONT_REGULAR_PATH, 18)
    draw.text((60, 1025), "det-core • Local-First SQL ETL Workspace", font=f_brand, fill=TEXT_MUTED)
    f_callout = get_font(FONT_BOLD_PATH, 18)
    bbox = draw.textbbox((0, 0), callout, font=f_callout)
    w = bbox[2] - bbox[0]
    draw.text((1020 - w, 1025), callout, font=f_callout, fill=ACCENT_CYAN)

# -------------------------------------------------------------
# SLIDE BUILDERS
# -------------------------------------------------------------

def build_slide_1() -> Image.Image:
    """Slide 1: Hook / Cover"""
    img = Image.new("RGB", (1080, 1080), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, 1, 7, "PRODUCT LAUNCH")

    # Hero Badge
    draw.rounded_rectangle([60, 160, 360, 205], radius=8, fill=(30, 58, 138))
    f_badge = get_font(FONT_BOLD_PATH, 20)
    draw.text((80, 172), "⚡ FAST • LOCAL-FIRST • OPEN SOURCE", font=f_badge, fill=ACCENT_CYAN)

    # Big Title
    f_title = get_font(FONT_BOLD_PATH, 58)
    draw.text((60, 240), "What if you could build\ncomplete ETL pipelines\nin Pure SQL...", font=f_title, fill=TEXT_WHITE, spacing=14)

    f_sub = get_font(FONT_REGULAR_PATH, 34)
    draw.text((60, 460), "Without Jinja templates,\nwithout a cloud database tax,\nand without JVM / Spark bloat?", font=f_sub, fill=ACCENT_AMBER, spacing=10)

    # Features Grid Card
    draw.rounded_rectangle([60, 620, 1020, 960], radius=16, fill=CARD_BG, outline=CARD_BORDER, width=2)
    
    pillars = [
        ("🧩 Pure ANSI SQL", "No Jinja, no complex macro spaghetti — clean SQL everywhere."),
        ("⚡ Apache DataFusion", "Rust vectorized query engine executing at bare-metal speeds."),
        ("🌐 Multi-Source & Sink", "Join Excel + Delta + Parquet + CSV; output to multiple destinations."),
        ("🖥️ Built-in Web IDE", "Visual DAG canvas, live SQL validator, and telemetry monitoring."),
    ]
    
    for i, (p_title, p_desc) in enumerate(pillars):
        x = 90 if i % 2 == 0 else 560
        y = 650 if i < 2 else 800
        f_pt = get_font(FONT_BOLD_PATH, 26)
        draw.text((x, y), p_title, font=f_pt, fill=TEXT_WHITE)
        f_pd = get_font(FONT_REGULAR_PATH, 19)
        # Wrap desc
        words = p_desc.split(" ")
        line1 = " ".join(words[:5])
        line2 = " ".join(words[5:])
        draw.text((x, y + 36), line1 + ("\n" + line2 if line2 else ""), font=f_pd, fill=TEXT_MUTED, spacing=4)

    draw_footer(draw, "Swipe to see the comparison →")
    return img

def build_slide_2() -> Image.Image:
    """Slide 2: The Modern Data Stack Pain Points"""
    img = Image.new("RGB", (1080, 1080), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, 2, 7, "THE CURRENT REALITY")

    f_title = get_font(FONT_BOLD_PATH, 50)
    draw.text((60, 160), "Why is Modern Data Engineering\nSo Unnecessarily Complex?", font=f_title, fill=TEXT_WHITE, spacing=12)

    pains = [
        ("1. The Jinja Macro Quagmire", "You wanted to write SQL, but ended up debugging nested {{ ref(...) }} and custom Jinja macros.", ACCENT_RED),
        ("2. The Heavy Cloud Warehouse Tax", "Forcing simple transformations into Snowflake or BigQuery burns compute credits and egress fees.", ACCENT_AMBER),
        ("3. The Single-Source Bottleneck", "dbt expects data to already live in one warehouse. Joining raw Excel + Parquet + Delta requires extra ETL tools.", ACCENT_CYAN),
        ("4. The Single-Destination Constraint", "Models in dbt / SQLMesh write to only one target table per file. Multi-destination publishing requires duplicate runs.", ACCENT_GREEN),
    ]

    for i, (title, desc, color) in enumerate(pains):
        y = 330 + i * 160
        draw.rounded_rectangle([60, y, 1020, y + 135], radius=14, fill=CARD_BG, outline=color, width=2)
        f_t = get_font(FONT_BOLD_PATH, 25)
        draw.text((90, y + 22), title, font=f_t, fill=TEXT_WHITE)
        f_d = get_font(FONT_REGULAR_PATH, 20)
        draw.text((90, y + 66), desc, font=f_d, fill=TEXT_MUTED)

    draw_footer(draw, "Swipe to see the solution →")
    return img

def build_slide_3() -> Image.Image:
    """Slide 3: Pure SQL & Vectorized In-Engine Execution"""
    img = Image.new("RGB", (1080, 1080), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, 3, 7, "SUPERPOWER #1 • ENGINE")

    f_title = get_font(FONT_BOLD_PATH, 48)
    draw.text((60, 150), "Pure SQL Everywhere.\nNo Jinja. No Database Server.", font=f_title, fill=TEXT_WHITE, spacing=10)

    f_sub = get_font(FONT_REGULAR_PATH, 24)
    draw.text((60, 280), "Powered by Apache DataFusion & Apache Arrow columnar memory.", font=f_sub, fill=ACCENT_CYAN)

    # Comparison Table
    draw.rounded_rectangle([60, 340, 1020, 680], radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)

    headers = ["Capability", "Traditional (dbt / SQLMesh)", "det (Data Engineering Tool)"]
    f_th = get_font(FONT_BOLD_PATH, 21)
    draw.text((90, 365), headers[0], font=f_th, fill=ACCENT_AMBER)
    draw.text((370, 365), headers[1], font=f_th, fill=TEXT_MUTED)
    draw.text((740, 365), headers[2], font=f_th, fill=ACCENT_GREEN)
    draw.line([60, 410, 1020, 410], fill=CARD_BORDER, width=2)

    rows = [
        ("Language", "SQL + Jinja templates", "100% Pure ANSI SQL"),
        ("Compute Engine", "Remote Cloud DB (Snowflake)", "Embedded Apache DataFusion (Rust)"),
        ("Memory Format", "Database proprietary", "Apache Arrow zero-copy memory"),
        ("Cloud Dependency", "Mandatory active connection", "Zero cloud lock-in / 100% Local-first"),
        ("Intermediate DAG", "Temporary DB tables/views", "Zero-copy in-engine registered views"),
    ]

    for i, (col1, col2, col3) in enumerate(rows):
        y = 430 + i * 48
        f_tb = get_font(FONT_REGULAR_PATH, 19)
        draw.text((90, y), col1, font=f_tb, fill=TEXT_WHITE)
        draw.text((370, y), col2, font=f_tb, fill=TEXT_MUTED)
        f_tb_b = get_font(FONT_BOLD_PATH, 19)
        draw.text((740, y), col3, font=f_tb_b, fill=ACCENT_GREEN)

    # Callout Box
    draw.rounded_rectangle([60, 710, 1020, 960], radius=14, fill=CODE_BG, outline=ACCENT_BLUE, width=2)
    f_box_t = get_font(FONT_BOLD_PATH, 22)
    draw.text((90, 735), "⚡ How intermediate DAG stages work in det:", font=f_box_t, fill=ACCENT_CYAN)
    f_code = get_font(FONT_CODE_PATH, 18)
    code_text = (
        "-- Step 1: Clean raw orders\n"
        "SELECT order_id, customer_id, net_amount FROM raw_orders WHERE status = 'OK';\n\n"
        "-- Step 2: Query Step 1 output directly without disk serialization!\n"
        "SELECT customer_id, SUM(net_amount) AS ltv FROM clean_orders GROUP BY 1;"
    )
    draw.text((90, 775), code_text, font=f_code, fill=(226, 232, 240), spacing=4)

    draw_footer(draw, "Swipe to see multi-source extraction →")
    return img

def build_slide_4() -> Image.Image:
    """Slide 4: Multi-Source Heterogeneous Extraction"""
    img = Image.new("RGB", (1080, 1080), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, 4, 7, "SUPERPOWER #2 • SOURCES")

    f_title = get_font(FONT_BOLD_PATH, 48)
    draw.text((60, 150), "Extract & Join Across\nMultiple Formats in One Query", font=f_title, fill=TEXT_WHITE, spacing=10)

    f_sub = get_font(FONT_REGULAR_PATH, 22)
    draw.text((60, 275), "Query Parquet, Delta Lake, Excel, CSV, JSON, and XML in standard ANSI SQL.", font=f_sub, fill=ACCENT_CYAN)

    # Format badges
    formats = ["📁 Delta Lake (ACID)", "📁 Parquet", "📁 Excel (.xlsx)", "📁 CSV", "📁 JSON / NDJSON", "📁 XML"]
    for i, fmt in enumerate(formats):
        x = 60 + (i % 3) * 330
        y = 330 + (i // 3) * 60
        draw.rounded_rectangle([x, y, x + 310, y + 48], radius=8, fill=CARD_BG, outline=CARD_BORDER, width=2)
        f_fmt = get_font(FONT_BOLD_PATH, 18)
        draw.text((x + 20, y + 13), fmt, font=f_fmt, fill=TEXT_WHITE)

    # Real Code Card
    draw.rounded_rectangle([60, 480, 1020, 960], radius=14, fill=CODE_BG, outline=ACCENT_BLUE, width=2)
    f_tag = get_font(FONT_BOLD_PATH, 20)
    draw.text((90, 505), "📊 Live Query Example: Joining Excel Quota with Delta Lake Transactions", font=f_tag, fill=ACCENT_GREEN)

    sql_code = (
        "SELECT \n"
        "    s.store_id,\n"
        "    s.store_name,\n"
        "    q.q1_target_usd,                 -- Scanned lazily from Excel (.xlsx)\n"
        "    SUM(o.net_amount) AS actual_usd, -- Scanned vectorized from Delta Lake\n"
        "    ROUND(SUM(o.net_amount) / q.q1_target_usd * 100.0, 2) AS attainment_pct\n"
        "FROM raw_stores s                    -- CSV customer catalog\n"
        "JOIN excel_financial_targets q       -- Multi-sheet Excel workbook\n"
        "  ON s.store_id = q.store_id\n"
        "JOIN delta_orders o                  -- ACID Delta Lake transaction table\n"
        "  ON s.store_id = o.store_id\n"
        "GROUP BY s.store_id, s.store_name, q.q1_target_usd;"
    )
    f_sql = get_font(FONT_CODE_PATH, 18)
    draw.text((90, 545), sql_code, font=f_sql, fill=(241, 245, 249), spacing=6)

    draw_footer(draw, "Swipe to see multi-destination publishing →")
    return img

def build_slide_5() -> Image.Image:
    """Slide 5: Multi-Destination Output Publishing"""
    img = Image.new("RGB", (1080, 1080), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, 5, 7, "SUPERPOWER #3 • DESTINATIONS")

    f_title = get_font(FONT_BOLD_PATH, 48)
    draw.text((60, 150), "Publish to Multiple Destinations\nFrom a Single Pipeline Step", font=f_title, fill=TEXT_WHITE, spacing=10)

    f_sub = get_font(FONT_REGULAR_PATH, 22)
    draw.text((60, 275), "dbt and SQLMesh tie one model to one table. det routes everywhere.", font=f_sub, fill=ACCENT_AMBER)

    # Architecture diagram card
    draw.rounded_rectangle([60, 330, 1020, 620], radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)
    f_diag_t = get_font(FONT_BOLD_PATH, 22)
    draw.text((90, 355), "DAG Pipeline Step: compute_customer_rfm_tiers", font=f_diag_t, fill=ACCENT_CYAN)

    destinations = [
        ("Destination 1: Delta Lake", "dw_customer_rfm_delta", "ACID time-travel table for downstream analytical queries"),
        ("Destination 2: Parquet", "dw_customer_rfm.parquet", "Snappy-compressed columnar file for fast cloud BI exports"),
        ("Destination 3: Delimited CSV", "rfm_executive_report.csv", "Clean CSV report ready for business stakeholders & Excel"),
    ]

    for i, (name, target, desc) in enumerate(destinations):
        y = 410 + i * 65
        draw.rounded_rectangle([90, y, 990, y + 54], radius=8, fill=CODE_BG, outline=ACCENT_BLUE, width=1)
        f_d1 = get_font(FONT_BOLD_PATH, 18)
        draw.text((110, y + 8), name, font=f_d1, fill=TEXT_WHITE)
        f_d2 = get_font(FONT_CODE_PATH, 16)
        draw.text((360, y + 9), f"→ {target}", font=f_d2, fill=ACCENT_GREEN)
        f_d3 = get_font(FONT_REGULAR_PATH, 15)
        draw.text((110, y + 30), desc, font=f_d3, fill=TEXT_MUTED)

    # Pipeline YAML snippet
    draw.rounded_rectangle([60, 650, 1020, 960], radius=14, fill=CODE_BG, outline=CARD_BORDER, width=2)
    f_yt = get_font(FONT_BOLD_PATH, 20)
    draw.text((90, 675), "📄 Declarative YAML Specification:", font=f_yt, fill=ACCENT_CYAN)

    yaml_code = (
        "steps:\n"
        "  - name: mart_customer_rfm\n"
        "    sql: \"SELECT customer_id, rfm_score, loyalty_tier FROM ranked_customers\"\n"
        "    destinations:\n"
        "      - name: dw_customer_rfm_delta    # Delta Lake table (mode: overwrite)\n"
        "      - name: dw_customer_rfm_parquet  # Parquet file (mode: overwrite)\n"
        "      - name: rfm_report_csv           # CSV file (mode: overwrite)"
    )
    f_yaml = get_font(FONT_CODE_PATH, 18)
    draw.text((90, 715), yaml_code, font=f_yaml, fill=(226, 232, 240), spacing=5)

    draw_footer(draw, "Swipe to see the Web IDE & GUI →")
    return img

def build_slide_6() -> Image.Image:
    """Slide 6: Built-in Web IDE, Visual DAG & Documentation"""
    img = Image.new("RGB", (1080, 1080), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, 6, 7, "DEVELOPER EXPERIENCE • GUI")

    f_title = get_font(FONT_BOLD_PATH, 48)
    draw.text((60, 150), "Zero-Install Web IDE\nRun Headless or Visually (`det gui`)", font=f_title, fill=TEXT_WHITE, spacing=10)

    f_sub = get_font(FONT_REGULAR_PATH, 22)
    draw.text((60, 275), "Everything you need to author, debug, monitor, and document pipelines.", font=f_sub, fill=ACCENT_CYAN)

    features = [
        ("📊 Visual DAG Canvas", "Auto-generated Mermaid DAG topology graphs reflecting exact dependency and step flow in real-time.", (37, 99, 235)),
        ("⚡ Real-Time SQL Runner", "Integrated Monaco-grade SQL editor with syntax highlighting, column autocomplete, and pre-flight validation.", (16, 185, 129)),
        ("👁️ Data Catalog Previews", "Browse all 14 data sources with live schema types, column contracts, and instant table sample views.", (245, 158, 11)),
        ("⏱️ Telemetry & Monitoring", "Inspect execution run histories, step duration breakdown (ms), processed row counts, and health rates.", (139, 92, 246)),
        ("📚 Living Documentation", "Export single-file HTML/Markdown documentation portals with embedded SVG lineages with one click.", (236, 72, 153)),
    ]

    for i, (title, desc, color) in enumerate(features):
        y = 330 + i * 125
        draw.rounded_rectangle([60, y, 1020, y + 105], radius=12, fill=CARD_BG, outline=CARD_BORDER, width=2)
        # Left accent pill
        draw.rounded_rectangle([60, y, 75, y + 105], radius=6, fill=color)
        f_t = get_font(FONT_BOLD_PATH, 23)
        draw.text((95, y + 16), title, font=f_t, fill=TEXT_WHITE)
        f_d = get_font(FONT_REGULAR_PATH, 18)
        draw.text((95, y + 54), desc, font=f_d, fill=TEXT_MUTED)

    draw_footer(draw, "Swipe to get started in 30 seconds →")
    return img

def build_slide_7() -> Image.Image:
    """Slide 7: Get Started / CTA"""
    img = Image.new("RGB", (1080, 1080), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, 7, 7, "GET STARTED")

    f_title = get_font(FONT_BOLD_PATH, 50)
    draw.text((60, 160), "Start Building Today\nIn 30 Seconds", font=f_title, fill=TEXT_WHITE, spacing=12)

    # Terminal card
    draw.rounded_rectangle([60, 300, 1020, 560], radius=16, fill=CODE_BG, outline=ACCENT_BLUE, width=2)
    # Window controls
    draw.ellipse([85, 325, 99, 339], fill=ACCENT_RED)
    draw.ellipse([110, 325, 124, 339], fill=ACCENT_AMBER)
    draw.ellipse([135, 325, 149, 339], fill=ACCENT_GREEN)
    f_wint = get_font(FONT_REGULAR_PATH, 16)
    draw.text((170, 322), "bash • quickstart", font=f_wint, fill=TEXT_MUTED)

    terminal_lines = [
        ("$ pip install det-core", TEXT_WHITE),
        ("# Unpack the production NovaMart sample warehouse", TEXT_MUTED),
        ("$ det sample-data", ACCENT_GREEN),
        ("# Launch the visual Web IDE in your browser", TEXT_MUTED),
        ("$ det gui", ACCENT_CYAN),
    ]

    for i, (line, color) in enumerate(terminal_lines):
        f_cmd = get_font(FONT_CODE_PATH, 24)
        draw.text((85, 370 + i * 36), line, font=f_cmd, fill=color)

    # Links Grid
    links = [
        ("🌐 Interactive Web Showcase", "det-labs.github.io/det/demo.html", "Try it right now without installing anything!"),
        ("⭐ GitHub Repository", "github.com/det-Labs/det", "Star the repo, check docs, and submit custom connectors."),
        ("📦 PyPI Release", "pypi.org/project/det-core/", "Official package release v0.2.0 is live!"),
        ("📚 GitHub Wiki", "github.com/det-Labs/det/wiki", "Architecture deep-dives and tutorials."),
    ]

    for i, (ltitle, lurl, ldesc) in enumerate(links):
        y = 590 + i * 95
        draw.rounded_rectangle([60, y, 1020, y + 80], radius=12, fill=CARD_BG, outline=CARD_BORDER, width=2)
        f_lt = get_font(FONT_BOLD_PATH, 20)
        draw.text((85, y + 14), ltitle, font=f_lt, fill=TEXT_WHITE)
        f_lu = get_font(FONT_CODE_PATH, 18)
        draw.text((450, y + 15), lurl, font=f_lu, fill=ACCENT_CYAN)
        f_ld = get_font(FONT_REGULAR_PATH, 15)
        draw.text((85, y + 46), ldesc, font=f_ld, fill=TEXT_MUTED)

    draw_footer(draw, "Share or save this post for your next project! ⭐")
    return img

# -------------------------------------------------------------
# LANDSCAPE ANNOUNCEMENT BANNER (1200 x 630)
# -------------------------------------------------------------

def build_announcement_banner() -> Image.Image:
    """High-Res Landscape Banner for LinkedIn feed (1200x630)"""
    img = Image.new("RGB", (1200, 630), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Accent Top Stripe
    draw.rectangle([0, 0, 1200, 6], fill=ACCENT_BLUE)

    # Brand Pill
    draw.rounded_rectangle([60, 45, 140, 90], radius=10, fill=ACCENT_BLUE)
    f_pill = get_font(FONT_BOLD_PATH, 24)
    draw.text((82, 53), "det", font=f_pill, fill=TEXT_WHITE)

    f_eye = get_font(FONT_BOLD_PATH, 20)
    draw.text((160, 58), "LOCAL-FIRST SQL ETL WORKSPACE", font=f_eye, fill=ACCENT_CYAN)

    f_pypi = get_font(FONT_CODE_PATH, 18)
    draw.text((1000, 58), "pip install det-core", font=f_pypi, fill=ACCENT_GREEN)

    # Title
    f_title = get_font(FONT_BOLD_PATH, 46)
    draw.text((60, 120), "Pure SQL ETL. Zero Jinja.\nPowered by Apache DataFusion.", font=f_title, fill=TEXT_WHITE, spacing=8)

    f_sub = get_font(FONT_REGULAR_PATH, 22)
    draw.text((60, 240), "Multi-Source Extraction • Multi-Destination Output • In-Engine Vectorized Compute", font=f_sub, fill=ACCENT_AMBER)

    # 3 Feature Cards
    cards = [
        ("📁 Multi-Source", "Join Excel, Delta Lake, Parquet, CSV, JSON, and XML in standard SQL."),
        ("⚡ Apache DataFusion", "Rust vectorized query engine executing at bare-metal CPU speeds."),
        ("🖥️ Visual Web IDE", "Mermaid DAG canvas, SQL editor, data catalog previews, and telemetry."),
    ]

    for i, (ctitle, cdesc) in enumerate(cards):
        x = 60 + i * 365
        draw.rounded_rectangle([x, 300, x + 350, 480], radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)
        f_ct = get_font(FONT_BOLD_PATH, 22)
        draw.text((x + 20, 325), ctitle, font=f_ct, fill=TEXT_WHITE)
        f_cd = get_font(FONT_REGULAR_PATH, 17)
        words = cdesc.split(" ")
        l1 = " ".join(words[:6])
        l2 = " ".join(words[6:12])
        l3 = " ".join(words[12:])
        draw.text((x + 20, 370), f"{l1}\n{l2}\n{l3}", font=f_cd, fill=TEXT_MUTED, spacing=4)

    # Footer Strip
    draw.rounded_rectangle([60, 520, 1140, 580], radius=10, fill=CODE_BG, outline=ACCENT_BLUE, width=1)
    f_foot = get_font(FONT_BOLD_PATH, 18)
    draw.text((85, 540), "🌐 Interactive Demo: det-labs.github.io/det/demo.html", font=f_foot, fill=ACCENT_CYAN)
    draw.text((700, 540), "⭐ GitHub: github.com/det-Labs/det", font=f_foot, fill=TEXT_WHITE)

    return img

# -------------------------------------------------------------
# MAIN COMPILER
# -------------------------------------------------------------

def generate_all_assets():
    print("1. Generating 7 high-resolution LinkedIn carousel slides...")
    slides = [
        build_slide_1(),
        build_slide_2(),
        build_slide_3(),
        build_slide_4(),
        build_slide_5(),
        build_slide_6(),
        build_slide_7(),
    ]

    slide_paths = []
    for i, slide in enumerate(slides, start=1):
        p = SLIDES_DIR / f"slide_{i}.png"
        slide.save(p, quality=95)
        slide_paths.append(p)
        print(f"   Saved {p}")

    print("2. Compiling multi-page LinkedIn Carousel PDF...")
    pdf_path = OUTPUT_DIR / "det_linkedin_carousel.pdf"
    
    # 1080 x 1080 points for square carousel
    c = canvas.Canvas(str(pdf_path), pagesize=(1080, 1080))
    for p in slide_paths:
        c.drawImage(str(p), 0, 0, width=1080, height=1080)
        c.showPage()
    c.save()
    print(f"   Saved {pdf_path} ({pdf_path.stat().st_size} bytes)")

    print("3. Generating high-resolution announcement banner...")
    banner = build_announcement_banner()
    banner_path = OUTPUT_DIR / "det_launch_banner.png"
    banner.save(banner_path, quality=95)
    print(f"   Saved {banner_path}")

    print("4. Rendering 1080p MP4 Product Walkthrough Video...")
    video_path = OUTPUT_DIR / "det_product_walkthrough.mp4"
    
    fps = 30
    seconds_per_slide = 4
    transition_frames = 15
    total_frames_per_slide = fps * seconds_per_slide

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (1080, 1080))

    cv_slides = [cv2.cvtColor(np.array(s), cv2.COLOR_RGB2BGR) for s in slides]

    for idx, curr_img in enumerate(cv_slides):
        next_img = cv_slides[(idx + 1) % len(cv_slides)] if idx < len(cv_slides) - 1 else None

        # Hold on slide with animated progress bar
        for f in range(total_frames_per_slide - transition_frames):
            frame = curr_img.copy()
            # Draw dynamic progress line on bottom
            progress = (f + 1) / total_frames_per_slide
            bar_len = int(progress * (1020 - 60))
            cv2.line(frame, (60, 1010), (60 + bar_len, 1010), (248, 189, 56), 4)
            out.write(frame)

        # Cross-fade transition to next slide if not last
        if next_img is not None:
            for t in range(transition_frames):
                alpha = t / transition_frames
                blended = cv2.addWeighted(curr_img, 1.0 - alpha, next_img, alpha, 0)
                out.write(blended)
        else:
            # Hold last slide
            for _ in range(transition_frames):
                out.write(curr_img)

    out.release()
    print(f"   Saved {video_path} ({video_path.stat().st_size} bytes)")
    print("\nAll LinkedIn announcement assets generated successfully!")

if __name__ == "__main__":
    generate_all_assets()
