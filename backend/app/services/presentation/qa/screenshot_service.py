"""Screenshot Generation Service for Phase 5.

Captures precise 1920x1080 screenshots of rendered slides using Headless Chromium / Chrome,
with a deterministic PIL canvas fallback to guarantee zero system downtime.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ....core import config
from ..visual.adapters.html_adapter import HTMLAdapter
from ..visual.design_tokens import SlideDesignTokens
from ..visual.visual_models import VisualSpecification

logger = logging.getLogger(__name__)


class ScreenshotService:
    """Renders VisualSpecification into pixel-exact 1920x1080 screenshots for visual auditing."""

    CHROME_CANDIDATES = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome"),
    ]

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or getattr(config, "PRESENTATION_VISUAL_QA_DIR", Path("data/exports/qa"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._chrome_path = self._locate_chrome_binary()

    def _locate_chrome_binary(self) -> str | None:
        """Finds an executable Chrome / Chromium binary."""
        for candidate in self.CHROME_CANDIDATES:
            if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def capture_slide_screenshot(
        self,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        deck_id: str = "deck_default",
        suffix: str = "rendered"
    ) -> str:
        """Captures a 1920x1080 screenshot of the slide and returns the PNG file path."""
        deck_dir = self.output_dir / deck_id
        deck_dir.mkdir(parents=True, exist_ok=True)

        seq_num = spec.sequence_number
        html_file = deck_dir / f"slide_{seq_num:03d}_{suffix}.html"
        png_file = deck_dir / f"slide_{seq_num:03d}_{suffix}.png"

        # 1. Render slide HTML at 1920x1080 canvas
        html_content = HTMLAdapter.to_html_slide(
            spec=spec,
            tokens=tokens,
            slide_width=1920,
            slide_height=1080
        )

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 2. Attempt Headless Chrome capture
        captured = False
        if self._chrome_path:
            try:
                cmd = [
                    self._chrome_path,
                    "--headless=new",
                    f"--screenshot={png_file.resolve()}",
                    "--window-size=1920,1080",
                    "--hide-scrollbars",
                    "--disable-gpu",
                    f"file://{html_file.resolve()}"
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)
                if png_file.exists() and os.path.getsize(png_file) > 500:
                    captured = True
            except Exception as e:
                logger.warning(f"Headless Chrome capture failed for slide {seq_num}: {e}. Using deterministic PIL fallback.")

        # 3. Deterministic PIL Fallback (Ensures 1920x1080 image is always produced)
        if not captured:
            self._render_pil_fallback(spec, tokens, png_file)

        return str(png_file.resolve())

    def _render_pil_fallback(
        self,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        target_path: Path
    ) -> None:
        """Renders a structured 1920x1080 slide image using Pillow."""
        width, height = 1920, 1080
        bg_color = tokens.background if tokens.background.startswith("#") else "#0F172A"
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Header zone
        accent_color = tokens.accent if tokens.accent.startswith("#") else "#FF5722"
        text_primary = tokens.primary_text if tokens.primary_text.startswith("#") else "#F8FAFC"
        text_secondary = tokens.secondary_text if tokens.secondary_text.startswith("#") else "#94A3B8"
        surface_color = tokens.surface if tokens.surface.startswith("#") else "#1E293B"

        # Category kicker
        draw.text((60, 50), (spec.visual_story.primary_message or "EXECUTIVE REVIEW").upper()[:40], fill=accent_color)
        # Headline
        draw.text((60, 85), spec.headline[:75], fill=text_primary)
        if spec.subtitle:
            draw.text((60, 140), spec.subtitle[:95], fill=text_secondary)

        # Body Layout: KPIs
        if spec.kpis:
            kpi_x = 60
            for k in spec.kpis[:4]:
                draw.rectangle([kpi_x, 190, kpi_x + 280, 280], fill=surface_color, outline=accent_color, width=1)
                draw.text((kpi_x + 15, 205), str(k.get("label", "Metric"))[:20], fill=text_secondary)
                draw.text((kpi_x + 15, 230), str(k.get("value", "0"))[:15], fill=accent_color)
                kpi_x += 300

        # Body Layout: Main Visual Box
        draw.rectangle([60, 310, 1300, 960], fill=surface_color, outline="#334155", width=1)
        v_title = spec.chart_spec.title if spec.chart_spec else (spec.primary_visual.visual_family)
        draw.text((80, 330), f"Primary Visual: {v_title}", fill=text_primary)

        # Body Layout: Insight Aside
        draw.rectangle([1340, 310, 1860, 960], fill=surface_color, outline="#334155", width=1)
        draw.text((1360, 330), "KEY TAKEAWAYS", fill=accent_color)
        ins_y = 380
        for item in spec.insights[:4]:
            draw.text((1375, ins_y), f"• {item[:45]}", fill=text_primary)
            ins_y += 50

        # Footer
        footer_text = f"Source: {spec.source_footer.source_citation or 'Audited System'} | {spec.source_footer.evidence_citation} | Slide {spec.sequence_number}"
        draw.text((60, 1000), footer_text, fill=text_secondary)

        img.save(target_path, "PNG")

    def cleanup_deck_screenshots(self, deck_id: str) -> None:
        """Deletes screenshot files for a deck if cleanup is enabled."""
        if getattr(config, "PRESENTATION_VISUAL_QA_KEEP_SCREENSHOTS", False):
            return
        deck_dir = self.output_dir / deck_id
        if deck_dir.exists():
            shutil.rmtree(deck_dir, ignore_errors=True)
