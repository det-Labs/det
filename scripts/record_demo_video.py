"""Record Real Browser Demo Video of det demonstrating:
1. Adding a Source
2. A Destination & Live Data Preview
3. Adding Multiple Steps in a DAG
4. Reading from Multiple Sources using Pure SQL (No Jinja)
5. Routing to Multiple Destinations (Delta Lake, Parquet, CSV)
6. In-Engine Vectorized Execution (DataFusion)
7. Glimpse of Monitoring (Telemetry, Step latencies)
8. Glimpse of Documentation (Living HTML, Embedded DAG)
9. Closing Branded Outro

With a custom synthesized futuristic tech electronic soundtrack.
Output: media/linkedin/det_demo_video.mp4 (Full HD 1080p, 30fps, Stereo Audio)
"""

import math
from pathlib import Path
import subprocess
import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

from synth_tech_music import generate_futuristic_track

OUTPUT_DIR = Path(__file__).parent.parent / "media" / "linkedin"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EDGE_EXE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
FONT_BOLD_PATH = "C:\\Windows\\Fonts\\segoeuib.ttf"
FONT_REGULAR_PATH = "C:\\Windows\\Fonts\\segoeui.ttf"
FONT_CODE_PATH = "C:\\Windows\\Fonts\\consola.ttf"

def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def draw_hud_badge(frame_bgr: np.ndarray, tag: str, title: str, subtitle: str, pos: tuple[int, int] = (60, 920)) -> np.ndarray:
    """Draw a frosted glass HUD highlight badge over a video frame."""
    bx, by = pos
    bw, bh = 880, 115

    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (15, 23, 42), -1)
    cv2.addWeighted(overlay, 0.90, frame_bgr, 0.10, 0, frame_bgr)

    # Glowing Cyan / Blue Border
    cv2.rectangle(frame_bgr, (bx, by), (bx + bw, by + bh), (235, 99, 37), 2)
    # Accent top-left line
    cv2.line(frame_bgr, (bx, by), (bx + 180, by), (248, 189, 56), 4)

    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    f_tag = get_font(FONT_BOLD_PATH, 16)
    f_title = get_font(FONT_BOLD_PATH, 24)
    f_sub = get_font(FONT_REGULAR_PATH, 17)

    draw.text((bx + 24, by + 14), tag.upper(), font=f_tag, fill=(56, 189, 248))
    draw.text((bx + 24, by + 42), title, font=f_title, fill=(248, 250, 252))
    draw.text((bx + 24, by + 78), subtitle, font=f_sub, fill=(148, 163, 184))

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def draw_cursor(frame_bgr: np.ndarray, cur_x: int, cur_y: int, click_progress: float = 0.0):
    """Draw a modern mouse cursor with click ripple."""
    h, w, _ = frame_bgr.shape
    if not (0 <= cur_x < w and 0 <= cur_y < h):
        return

    if 0.0 < click_progress < 1.0:
        radius = int(8 + click_progress * 28)
        alpha = max(0.0, 1.0 - click_progress)
        color = (int(56 * alpha), int(189 * alpha), int(248 * alpha))
        cv2.circle(frame_bgr, (cur_x, cur_y), radius, color, 2)

    pts = np.array([
        [cur_x, cur_y],
        [cur_x + 18, cur_y + 18],
        [cur_x + 10, cur_y + 19],
        [cur_x + 15, cur_y + 29],
        [cur_x + 11, cur_y + 31],
        [cur_x + 6, cur_y + 21],
        [cur_x, cur_y + 26]
    ], np.int32)
    cv2.fillPoly(frame_bgr, [pts + 2], (10, 15, 29))
    cv2.fillPoly(frame_bgr, [pts], (248, 250, 252))
    cv2.polylines(frame_bgr, [pts], True, (15, 23, 42), 1)

def build_closing_card() -> np.ndarray:
    """Generate high-tech branded closing card at 1920x1080."""
    img = Image.new("RGB", (1920, 1080), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Accent line
    draw.rectangle([0, 0, 1920, 8], fill=(37, 99, 235))

    # Glowing Logo Pill
    draw.rounded_rectangle([880, 150, 1040, 230], radius=18, fill=(37, 99, 235))
    f_pill = get_font(FONT_BOLD_PATH, 48)
    draw.text((915, 162), "det", font=f_pill, fill=(248, 250, 252))

    # Title
    f_title = get_font(FONT_BOLD_PATH, 56)
    title_text = "Fast, Local-First SQL ETL Workspace"
    bbox = draw.textbbox((0, 0), title_text, font=f_title)
    w = bbox[2] - bbox[0]
    draw.text(((1920 - w) // 2, 265), title_text, font=f_title, fill=(248, 250, 252))

    # Subtitle
    f_sub = get_font(FONT_REGULAR_PATH, 26)
    sub_text = "Powered by Apache DataFusion & Apache Arrow • Open Source & MIT Licensed"
    bbox = draw.textbbox((0, 0), sub_text, font=f_sub)
    w = bbox[2] - bbox[0]
    draw.text(((1920 - w) // 2, 345), sub_text, font=f_sub, fill=(56, 189, 248))

    # Terminal Quickstart Card
    cx, cy = 460, 420
    cw, ch = 1000, 270
    draw.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=16, fill=(10, 15, 29), outline=(51, 65, 85), width=2)
    # Window controls
    draw.ellipse([cx + 25, cy + 20, cx + 40, cy + 35], fill=(248, 113, 113))
    draw.ellipse([cx + 50, cy + 20, cx + 65, cy + 35], fill=(251, 191, 36))
    draw.ellipse([cx + 75, cy + 20, cx + 90, cy + 35], fill=(52, 211, 153))

    f_cmd = get_font(FONT_CODE_PATH, 27)
    commands = [
        ("$ pip install det-core", (248, 250, 252)),
        ("$ det sample-data    # Unpack NovaMart sample warehouse", (52, 211, 153)),
        ("$ det gui            # Launch the Web IDE in your browser", (56, 189, 248)),
    ]
    for i, (cmd, col) in enumerate(commands):
        draw.text((cx + 35, cy + 65 + i * 58), cmd, font=f_cmd, fill=col)

    # 3 CTA Badges
    badges = [
        ("🌐 Live Web Demo (Zero-Install)", "det-labs.github.io/det/demo.html"),
        ("⭐ GitHub Repository", "github.com/det-Labs/det"),
        ("📚 Documentation & Wiki", "github.com/det-Labs/det/wiki"),
    ]
    for i, (btitle, burl) in enumerate(badges):
        bx = 210 + i * 510
        by = 740
        bw, bh = 480, 110
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=14, fill=(30, 41, 59), outline=(51, 65, 85), width=2)
        f_bt = get_font(FONT_BOLD_PATH, 20)
        draw.text((bx + 24, by + 22), btitle, font=f_bt, fill=(248, 250, 252))
        f_bu = get_font(FONT_CODE_PATH, 18)
        draw.text((bx + 24, by + 58), burl, font=f_bu, fill=(56, 189, 248))

    f_foot = get_font(FONT_REGULAR_PATH, 20)
    foot_text = "Maintained by Saurabh Rai & det-Labs • Released under MIT License"
    bbox = draw.textbbox((0, 0), foot_text, font=f_foot)
    w = bbox[2] - bbox[0]
    draw.text(((1920 - w) // 2, 915), foot_text, font=f_foot, fill=(148, 163, 184))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def capture_ui_storyboard() -> list[dict]:
    """Capture real browser snapshots covering the user's exact requirements."""
    ui_path = (Path(__file__).parent.parent / "src" / "det" / "ui" / "index.html").resolve()
    print("Launching Microsoft Edge to record browser demo scenes...")

    story = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=EDGE_EXE, headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        # Auto-accept dialogs if any appear
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(ui_path.as_uri())
        page.wait_for_timeout(1000)

        # -------------------------------------------------------------
        # Scene 1: Adding a Source Connection
        # -------------------------------------------------------------
        folder_rows = page.locator(".folder-row")
        if folder_rows.count() > 0:
            folder_rows.first.hover()
            page.wait_for_timeout(200)

        add_btn = page.locator("button.tree-action[data-action='add-connection']")
        if add_btn.count() > 0:
            add_btn.first.click(force=True)
            page.wait_for_timeout(400)
            name_input = page.locator("#editor-form input[name='name']")
            if name_input.count() > 0:
                name_input.fill("raw_clickstream_events")
            page.wait_for_timeout(400)

        shot1 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot1,
            "dur": 5.0,
            "tag": "1. Catalog • Adding a Source Connection",
            "title": "Declare Data Sources with Strict Schemas",
            "sub": "Support for S3/Local CSV, Parquet, Delta Lake, JSON, NDJSON, and Excel.",
            "c_start": (200, 240),
            "c_end": (960, 480), # inside modal form
            "click_at": 0.5,
        })

        # Close dialog
        cancel_btn = page.locator("#dialog-cancel")
        if cancel_btn.count() > 0 and cancel_btn.is_visible():
            cancel_btn.click(force=True)
        page.evaluate("() => { const d = document.querySelector('#editor-dialog'); if (d && d.open) d.close(); }")
        page.wait_for_timeout(400)

        # -------------------------------------------------------------
        # Scene 2: Selecting Destination & Live Tabular Preview
        # -------------------------------------------------------------
        conns = page.locator(".connection-select")
        if conns.count() > 0:
            conns.first.click(force=True) # Click first connection (raw_customers)
            page.wait_for_timeout(400)
            preview_btn = page.locator(".detail-tab", has_text="Preview")
            if preview_btn.count() > 0:
                preview_btn.click(force=True)
                page.wait_for_timeout(600)

        shot2 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot2,
            "dur": 5.0,
            "tag": "2. Live Source Data Preview",
            "title": "Instant Tabular Previews & Type Contracts",
            "sub": "Inspect real records and column data types before building pipelines.",
            "c_start": (150, 240),
            "c_end": (650, 190), # Preview tab
            "click_at": 0.35,
        })

        # -------------------------------------------------------------
        # Scene 3: ETL Module • Adding Multiple Steps
        # -------------------------------------------------------------
        page.locator("button.module-tab[data-module='ETL']").click(force=True)
        page.wait_for_timeout(800)

        # Select mart_customer_rfm_loyalty pipeline
        rfm_pipe = page.locator(".pipeline-select", has_text="mart_customer_rfm_loyalty")
        if rfm_pipe.count() > 0:
            rfm_pipe.first.click(force=True)
            page.wait_for_timeout(700)
        else:
            first_pipe = page.locator(".pipeline-select").first
            if first_pipe.count() > 0:
                first_pipe.click(force=True)
                page.wait_for_timeout(700)

        shot3 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot3,
            "dur": 5.5,
            "tag": "3. Multi-Step DAG Pipelines",
            "title": "Visual DAG Canvas & Step Orchestration",
            "sub": "Chain multiple transformation steps into an interactive dependency graph.",
            "c_start": (280, 50),
            "c_end": (450, 240), # Step tab
            "click_at": 0.4,
        })

        # -------------------------------------------------------------
        # Scene 4: Reading from Multiple Sources using Pure SQL (No Jinja)
        # -------------------------------------------------------------
        multi_source_sql = (
            "-- Joining Delta Lake Orders + Excel Financial Targets + CSV Customers\n"
            "SELECT \n"
            "    c.customer_id, \n"
            "    c.first_name,\n"
            "    q.monthly_target_usd,         -- From Excel (.xlsx) sheet\n"
            "    SUM(o.net_amount) AS spend,   -- From Delta Lake ACID table\n"
            "    CASE WHEN SUM(o.net_amount) > 1000 THEN 'Platinum' ELSE 'Gold' END AS tier\n"
            "FROM raw_customers c             -- CSV master catalog\n"
            "JOIN raw_store_targets q          -- Multi-sheet Excel workbook\n"
            "  ON c.city = q.region\n"
            "JOIN fct_orders o                 -- Delta Lake transaction store\n"
            "  ON c.customer_id = o.customer_id\n"
            "GROUP BY c.customer_id, c.first_name, q.monthly_target_usd;"
        )
        sql_input = page.locator("#etl-sql-textarea")
        if sql_input.count() > 0:
            sql_input.fill(multi_source_sql)
            page.wait_for_timeout(400)
            page.evaluate("() => { const el = document.querySelector('#etl-sql-textarea'); if (el) { el.dispatchEvent(new Event('input')); } }")

        shot4 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot4,
            "dur": 7.0,
            "tag": "4. Pure ANSI SQL • Zero Jinja",
            "title": "Read & Join Multiple Heterogeneous Sources",
            "sub": "Join Excel + Delta Lake + CSV directly in standard SQL without templating.",
            "c_start": (450, 240),
            "c_end": (900, 620), # Hovering inside SQL editor
            "click_at": 0.5,
        })

        # -------------------------------------------------------------
        # Scene 5: Multiple Destinations Configured
        # -------------------------------------------------------------
        page.evaluate("""() => {
            if (window.activePipeline && window.activePipeline.steps && window.activePipeline.steps[0]) {
                window.activePipeline.steps[0].destinations = [
                    'dw_rfm_segments_csv',
                    'curated_lakehouse_parquet',
                    's3_audit_delta'
                ];
                if (typeof renderDestinations === 'function') renderDestinations();
            }
        }""")
        page.wait_for_timeout(400)

        shot5 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot5,
            "dur": 4.5,
            "tag": "5. Multi-Destination Publishing",
            "title": "Route Step Output to Multiple Storage Sinks",
            "sub": "Simultaneously write to Delta Lake, Parquet Lakehouse, and CSV reports.",
            "c_start": (900, 620),
            "c_end": (580, 480), # Destinations chip area
            "click_at": 0.4,
        })

        # -------------------------------------------------------------
        # Scene 6: In-Engine Execution (Sub-second DataFusion Compute)
        # -------------------------------------------------------------
        run_btn = page.locator("#etl-run-button")
        if run_btn.count() > 0:
            run_btn.click(force=True)
            page.wait_for_timeout(800)

        shot6 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot6,
            "dur": 5.5,
            "tag": "6. In-Engine Vectorized Compute",
            "title": "Sub-Second In-Memory Execution (DataFusion)",
            "sub": "Multi-threaded Rust query engine running locally with zero cloud egress tax.",
            "c_start": (580, 480),
            "c_end": (1680, 115), # Over Run button
            "click_at": 0.25,
        })

        # -------------------------------------------------------------
        # Scene 7: Glimpse of Monitoring & Telemetry
        # -------------------------------------------------------------
        page.locator("button.module-tab[data-module='Monitoring']").click(force=True)
        page.wait_for_timeout(800)

        run_rows = page.locator("#monitoring-runs-tbody tr[data-run-id]")
        if run_rows.count() > 0:
            run_rows.first.click(force=True)
            page.wait_for_timeout(600)

        shot7 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot7,
            "dur": 5.0,
            "tag": "7. Glimpse • Monitoring & Telemetry",
            "title": "Execution Audit Logs & Step Latency Breakdown",
            "sub": "100% health rate, step-by-step latency tracking (ms), and volume metrics.",
            "c_start": (360, 50), # Monitoring nav tab
            "c_end": (960, 360), # Over runs table
            "click_at": 0.5,
        })

        # -------------------------------------------------------------
        # Scene 8: Glimpse of Documentation
        # -------------------------------------------------------------
        page.locator("button.module-tab[data-module='Documentation']").click(force=True)
        page.wait_for_timeout(800)

        doc_items = page.locator("#docs-tree [data-doc-path]")
        if doc_items.count() > 0:
            doc_items.first.click(force=True)
            page.wait_for_timeout(700)

        shot8 = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        story.append({
            "img": shot8,
            "dur": 5.0,
            "tag": "8. Glimpse • Living Documentation",
            "title": "Auto-Generated HTML Portals with Lineage DAGs",
            "sub": "Single-file interactive documentation exported with data contracts.",
            "c_start": (450, 50), # Documentation nav tab
            "c_end": (960, 480), # Docs view
            "click_at": 0.5,
        })

        browser.close()

    return story

def render_final_demo_video():
    """Compose video frames with animated cursor, HUD badges, and multiplex with music."""
    total_video_dur = 47.5 # Under 1 minute
    soundtrack_wav = OUTPUT_DIR / "demo_soundtrack.wav"
    output_mp4 = OUTPUT_DIR / "det_demo_video.mp4"

    # 1. Synthesize Soundtrack to exact 48s duration
    print(f"1. Synthesizing {total_video_dur}s futuristic tech soundtrack...")
    generate_futuristic_track(soundtrack_wav, duration_sec=total_video_dur)

    # 2. Capture Real UI Scenes
    story = capture_ui_storyboard()

    # 3. Animate Frames and Stream directly to FFmpeg
    fps = 30
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1920x1080",
        "-pix_fmt", "bgr24",
        "-r", "30",
        "-i", "pipe:0",
        "-i", str(soundtrack_wav),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_mp4),
    ]

    print("3. Launching FFmpeg and streaming frames...")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    total_frames_written = 0
    for s_idx, scene in enumerate(story):
        base_img = scene["img"]
        dur = scene["dur"]
        total_f = int(dur * fps)
        c_sx, c_sy = scene["c_start"]
        c_ex, c_ey = scene["c_end"]
        click_f = int(scene["click_at"] * total_f)

        print(f"   Scene {s_idx + 1}/{len(story)}: {scene['tag']} ({total_f} frames)...", flush=True)
        for f in range(total_f):
            t_frac = f / total_f
            ease = 0.5 - 0.5 * math.cos(math.pi * min(1.0, t_frac * 1.35))
            cur_x = int(c_sx + (c_ex - c_sx) * ease)
            cur_y = int(c_sy + (c_ey - c_sy) * ease)

            click_prog = (f - click_f) / 10.0 if f >= click_f else 0.0

            frame = base_img.copy()
            draw_cursor(frame, cur_x, cur_y, click_progress=click_prog)
            frame = draw_hud_badge(frame, scene["tag"], scene["title"], scene["sub"])
            proc.stdin.write(frame.tobytes())
            total_frames_written += 1

    # Closing CTA Scene
    print("   Scene 9/9: Outro Call to Action card (150 frames)...", flush=True)
    closing_card = build_closing_card()
    closing_bytes = closing_card.tobytes()
    closing_frames = int(5.0 * fps)
    for _ in range(closing_frames):
        proc.stdin.write(closing_bytes)
        total_frames_written += 1

    proc.stdin.close()
    proc.wait()

    if proc.returncode == 0:
        file_size = output_mp4.stat().st_size
        print(f"\n🎉 Demo video generated successfully!")
        print(f"File: {output_mp4} ({file_size / (1024*1024):.2f} MB, {total_frames_written/fps:.1f}s)")
    else:
        print(f"FFmpeg exited with return code {proc.returncode}")

if __name__ == "__main__":
    render_final_demo_video()
