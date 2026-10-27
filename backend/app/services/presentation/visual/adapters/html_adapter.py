"""HTML Slide Generator Adapter for Phase 4.

Transforms canonical VisualSpecification models into self-contained, beautifully rendered HTML slides.
Adheres strictly to presentation design tokens and consumes ResolvedTypographySpec from TypographyResolver.
"""

from __future__ import annotations

import html
from typing import Any
from ..design_tokens import SlideDesignTokens
from ..visual_models import VisualSpecification
from ...typography import TypographyResolver, SemanticTypographyRole


class HTMLAdapter:
    """Renders VisualSpecification into standalone, self-contained HTML slides consuming TypographyResolver."""

    @classmethod
    def to_html_slide(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        slide_width: int = 1280,
        slide_height: int = 720,
        use_ai: bool = True
    ) -> str:
        """Renders a single slide into an isolated HTML string."""
        theme_vars = tokens.to_scoped_css_variables()
        var_styles = "; ".join(f"{k}: {v}" for k, v in theme_vars.items())
        slide_id = f"slide-{spec.sequence_number}"
        theme_mode = "dark" if "dark" in tokens.background.lower() or "111827" in tokens.background.lower() else "light"

        # Check if this slide is a dedicated Presentation Cover Slide
        is_cover = bool(
            spec.metadata.get("is_cover")
            or (spec.layout.family.value == "TITLE_HERO" and spec.layout.variant == "title_cover")
            or (spec.sequence_number == 1 and not spec.kpis and not spec.chart_spec and not spec.table_data)
        )
        if is_cover:
            return cls._render_cover_slide(
                spec=spec,
                tokens=tokens,
                slide_width=slide_width,
                slide_height=slide_height,
                use_ai=use_ai,
                var_styles=var_styles,
                slide_id=slide_id,
                theme_mode=theme_mode,
            )

        # 1. Headline (TITLE)
        head_spec = TypographyResolver.resolve_block_typography(
            block_id=f"{slide_id}-headline",
            text=spec.headline or "",
            semantic_role=SemanticTypographyRole.TITLE,
            font_family=tokens.font_heading,
            theme_mode=theme_mode,
            use_ai=use_ai,
            background_hex=tokens.background
        )
        head_size_px = int(head_spec.font_size_pt * 1.333)
        head_weight = 700 if head_spec.font_weight == "bold" else (600 if head_spec.font_weight == "600" else 400)

        # 2. Subtitle (SUBTITLE)
        sub_html = ""
        if spec.subtitle:
            sub_spec = TypographyResolver.resolve_block_typography(
                block_id=f"{slide_id}-subtitle",
                text=spec.subtitle,
                semantic_role=SemanticTypographyRole.SUBTITLE,
                font_family=tokens.font_body,
                theme_mode=theme_mode,
                use_ai=use_ai,
                background_hex=tokens.background
            )
            sub_size_px = int(sub_spec.font_size_pt * 1.333)
            sub_html = f'<p style="font-size: {sub_size_px}px; color: {sub_spec.color_hex}; margin: 0; line-height: {sub_spec.line_height_multiplier};">{html.escape(spec.subtitle)}</p>'

        # Render sections with shared typography
        kpi_html = cls._render_kpis(spec.kpis, tokens, slide_id, theme_mode, use_ai)
        insights_html = cls._render_insights(spec.insights, tokens, slide_id, theme_mode, use_ai)
        visual_html = cls._render_primary_visual(spec, tokens, slide_id, theme_mode, use_ai)
        table_html = cls._render_table(spec.table_data, tokens, slide_id, theme_mode, use_ai)
        footer_html = cls._render_footer(spec, tokens, slide_id, theme_mode, use_ai)

        html_content = f"""
<div class="presentation-runtime" id="{slide_id}" style="width: {slide_width}px; height: {slide_height}px; position: relative; overflow: hidden; background: {tokens.background}; color: {tokens.primary_text}; font-family: {tokens.font_body}; box-sizing: border-box; padding: {tokens.slide_padding}; {var_styles}; display: flex; flex-direction: column; justify-content: space-between;">
  <!-- Slide Header -->
  <header style="margin-bottom: {tokens.card_gap};">
    <div style="font-size: {tokens.font_size_caption}; text-transform: uppercase; letter-spacing: 0.1em; color: {tokens.accent_primary}; font-weight: 600; margin-bottom: 4px;">
      {html.escape((spec.visual_story.primary_message if spec.visual_story else None) or 'Presentation Overview')}
    </div>
    <h2 style="font-family: {tokens.font_heading}; font-size: {head_size_px}px; font-weight: {head_weight}; color: {head_spec.color_hex}; margin: 0 0 6px 0; line-height: {head_spec.line_height_multiplier};">
      {html.escape(spec.headline or '')}
    </h2>
    {sub_html}
  </header>

  <!-- Slide Body Content -->
  <main style="flex: 1; display: flex; gap: {tokens.card_gap}; min-height: 0; overflow: hidden;">
    <div style="flex: 1; display: flex; flex-direction: column; gap: {tokens.card_gap}; min-width: 0;">
      {kpi_html}
      {visual_html}
      {table_html}
    </div>
    {insights_html}
  </main>

  <!-- Slide Footer -->
  {footer_html}
</div>
"""
        return html_content.strip()

    @classmethod
    def _render_cover_slide(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        slide_width: int,
        slide_height: int,
        use_ai: bool,
        var_styles: str,
        slide_id: str,
        theme_mode: str,
    ) -> str:
        meta = spec.metadata or {}
        pres_title = spec.headline or meta.get("presentation_title") or "Presentation Overview"
        pres_subtitle = spec.subtitle or meta.get("presentation_subtitle") or ""
        presenter = meta.get("presenter_name") or "[Presenter Name]"
        org = meta.get("organization_name") or "[Organization / Institution]"
        role = meta.get("presenter_role")
        date_str = meta.get("presentation_date") or "[Date]"
        badge_text = spec.visual_story.primary_message or meta.get("category") or "PRESENTATION OVERVIEW"

        # Resolve Title Typography (SemanticTypographyRole.DECK_TITLE / TITLE)
        title_spec = TypographyResolver.resolve_block_typography(
            block_id=f"{slide_id}-cover-title",
            text=pres_title,
            semantic_role=SemanticTypographyRole.DECK_TITLE,
            font_family=tokens.font_heading,
            theme_mode=theme_mode,
            use_ai=use_ai,
            background_hex=tokens.background,
        )
        title_size_px = max(36, int(title_spec.font_size_pt * 1.333))

        # Resolve Subtitle Typography
        sub_html = ""
        if pres_subtitle:
            sub_spec = TypographyResolver.resolve_block_typography(
                block_id=f"{slide_id}-cover-subtitle",
                text=pres_subtitle,
                semantic_role=SemanticTypographyRole.SUBTITLE,
                font_family=tokens.font_body,
                theme_mode=theme_mode,
                use_ai=use_ai,
                background_hex=tokens.background,
            )
            sub_size_px = max(18, int(sub_spec.font_size_pt * 1.333))
            sub_html = f'<p style="font-size: {sub_size_px}px; color: {sub_spec.color_hex}; margin: 16px 0 0 0; line-height: 1.35; font-weight: 500;">{html.escape(pres_subtitle)}</p>'

        card_bg = tokens.surface or tokens.background
        # Resolve metadata labels & values typography against card background
        label_spec = TypographyResolver.resolve_block_typography(
            block_id=f"{slide_id}-cover-label",
            text="Presented by Organization Date",
            semantic_role=SemanticTypographyRole.SOURCE,
            font_family=tokens.font_body,
            theme_mode=theme_mode,
            use_ai=use_ai,
            background_hex=card_bg,
        )
        val_spec = TypographyResolver.resolve_block_typography(
            block_id=f"{slide_id}-cover-val",
            text=f"{presenter} {org} {date_str}",
            semantic_role=SemanticTypographyRole.BODY,
            font_family=tokens.font_body,
            theme_mode=theme_mode,
            use_ai=use_ai,
            background_hex=card_bg,
        )

        role_html = ""
        if role:
            role_html = f"""
        <div>
          <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: {label_spec.color_hex}; font-weight: 600; margin-bottom: 4px;">Department / Role</div>
          <div style="font-size: 14px; font-weight: 600; color: {val_spec.color_hex};">{html.escape(role)}</div>
        </div>"""

        return f"""
<div class="presentation-runtime presentation-cover-slide" id="{slide_id}" style="width: {slide_width}px; height: {slide_height}px; position: relative; overflow: hidden; background: {tokens.background}; color: {tokens.primary_text}; font-family: {tokens.font_body}; box-sizing: border-box; padding: 64px 88px; {var_styles}; display: flex; flex-direction: column; justify-content: space-between;">
  <!-- Top Framing Badge -->
  <div>
    <div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: 9999px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: {tokens.accent_primary};">
      <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: {tokens.accent_primary};"></span>
      {html.escape(badge_text)}
    </div>
  </div>

  <!-- Hero Content Section -->
  <div style="margin: auto 0; max-width: 980px;">
    <h1 style="font-family: {tokens.font_heading}; font-size: {title_size_px}px; font-weight: 800; color: {title_spec.color_hex}; margin: 0; line-height: 1.15; letter-spacing: -0.02em;">
      {html.escape(pres_title or '')}
    </h1>
    {sub_html}
    <div style="width: 80px; height: 4px; background: {tokens.accent_primary}; margin: 28px 0 36px 0; border-radius: 2px;"></div>

    <!-- Metadata Card -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; padding: 20px 24px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.radius}; max-width: 760px;">
      <div>
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: {label_spec.color_hex}; font-weight: 600; margin-bottom: 4px;">Presented by</div>
        <div style="font-size: 14px; font-weight: 600; color: {val_spec.color_hex};">{html.escape(presenter or '')}</div>
      </div>
      <div>
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: {label_spec.color_hex}; font-weight: 600; margin-bottom: 4px;">Organization</div>
        <div style="font-size: 14px; font-weight: 600; color: {val_spec.color_hex};">{html.escape(org or '')}</div>
      </div>
      {role_html}
      <div>
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: {label_spec.color_hex}; font-weight: 600; margin-bottom: 4px;">Date</div>
        <div style="font-size: 14px; font-weight: 600; color: {val_spec.color_hex};">{html.escape(date_str or '')}</div>
      </div>
    </div>
  </div>

  <!-- Bottom Framing Bar -->
  <footer style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: {label_spec.color_hex}; letter-spacing: 0.05em; text-transform: uppercase;">
    <div>Analytical Briefing</div>
    <div>Slide 1</div>
  </footer>
</div>
""".strip()

    @classmethod
    def _render_kpis(
        cls,
        kpis: list[dict[str, Any]],
        tokens: SlideDesignTokens,
        slide_id: str = "slide-1",
        theme_mode: str = "dark",
        use_ai: bool = False
    ) -> str:
        if not kpis:
            return ""
        items = []
        for idx, k in enumerate(kpis):
            label_text = str(k.get("label", "Metric"))
            val_text = str(k.get("value", "0"))
            sub_text = str(k.get("subtext", ""))

            val_spec = TypographyResolver.resolve_block_typography(
                block_id=f"{slide_id}-kpi-val-{idx}",
                text=val_text,
                semantic_role=SemanticTypographyRole.KPI_VALUE,
                font_family=tokens.font_heading,
                theme_mode=theme_mode,
                use_ai=use_ai,
                background_hex=tokens.surface
            )
            lbl_spec = TypographyResolver.resolve_block_typography(
                block_id=f"{slide_id}-kpi-lbl-{idx}",
                text=label_text,
                semantic_role=SemanticTypographyRole.KPI_LABEL,
                font_family=tokens.font_body,
                theme_mode=theme_mode,
                use_ai=use_ai,
                background_hex=tokens.surface
            )

            val_px = int(val_spec.font_size_pt * 1.333)
            lbl_px = int(lbl_spec.font_size_pt * 1.333)

            item_html = f"""
            <div style="flex: 1; min-width: 140px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 12px 16px; box-shadow: {tokens.card_shadow};">
              <div style="font-size: {lbl_px}px; color: {lbl_spec.color_hex}; text-transform: uppercase; font-weight: {lbl_spec.font_weight};">{html.escape(label_text)}</div>
              <div style="font-family: {tokens.font_heading}; font-size: {val_px}px; font-weight: {val_spec.font_weight}; color: {tokens.accent_primary}; margin: 4px 0;">{html.escape(val_text)}</div>
              {f'<div style="font-size: 11px; color: {tokens.muted_text};">{html.escape(sub_text)}</div>' if sub_text else ''}
            </div>
            """
            items.append(item_html)

        return f'<div style="display: flex; gap: {tokens.card_gap}; flex-wrap: wrap;">{"".join(items)}</div>'

    @classmethod
    def _render_insights(
        cls,
        insights: list[str],
        tokens: SlideDesignTokens,
        slide_id: str = "slide-1",
        theme_mode: str = "dark",
        use_ai: bool = False
    ) -> str:
        if not insights:
            return ""
        items = []
        for idx, ins in enumerate(insights):
            ins_spec = TypographyResolver.resolve_block_typography(
                block_id=f"{slide_id}-insight-{idx}",
                text=ins,
                semantic_role=SemanticTypographyRole.PRIMARY_INSIGHT,
                font_family=tokens.font_body,
                theme_mode=theme_mode,
                use_ai=use_ai,
                background_hex=tokens.surface
            )
            ins_px = int(ins_spec.font_size_pt * 1.333)
            ins_weight = 600 if ins_spec.font_weight in ("bold", "600") else 400

            items.append(f"""
            <li style="margin-bottom: 10px; line-height: {ins_spec.line_height_multiplier}; color: {ins_spec.color_hex}; font-size: {ins_px}px; font-weight: {ins_weight};">
              {html.escape(ins)}
            </li>
            """)

        return f"""
        <aside style="width: 320px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 16px; display: flex; flex-direction: column; box-shadow: {tokens.card_shadow};">
          <div style="font-size: {tokens.font_size_caption}; text-transform: uppercase; font-weight: 700; color: {tokens.accent_primary}; margin-bottom: 12px; letter-spacing: 0.05em;">Key Takeaways</div>
          <ul style="margin: 0; padding-left: 18px; flex: 1; overflow-y: auto;">
            {"".join(items)}
          </ul>
        </aside>
        """

    @classmethod
    def _render_primary_visual(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        slide_id: str = "slide-1",
        theme_mode: str = "dark",
        use_ai: bool = False
    ) -> str:
        if spec.chart_spec:
            cs = spec.chart_spec
            c_spec = TypographyResolver.resolve_block_typography(
                block_id=f"{slide_id}-chart-title",
                text=cs.title or (cs.family.value if hasattr(cs.family, 'value') else str(cs.family)),
                semantic_role=SemanticTypographyRole.CHART_TITLE,
                font_family=tokens.font_heading,
                theme_mode=theme_mode,
                use_ai=use_ai,
                background_hex=tokens.surface
            )
            return cls._render_svg_chart(cs, tokens, slide_id, theme_mode, c_spec)
        elif spec.matrix_spec:
            ms = spec.matrix_spec
            quads = []
            for q in ms.quadrants:
                quads.append(f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px dashed {tokens.border}; border-radius: 6px; padding: 10px;">
                  <div style="font-weight: 700; color: {tokens.accent_primary}; font-size: 13px;">{html.escape(q.label)}</div>
                  <div style="font-size: 11px; color: {tokens.secondary_text}; margin-top: 4px;">{html.escape(q.description)}</div>
                </div>
                """)
            return f"""
            <div style="flex: 1; min-height: 220px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; box-shadow: {tokens.card_shadow};">
              {"".join(quads)}
            </div>
            """
        elif spec.diagram_spec:
            ds = spec.diagram_spec
            nodes = []
            for n in ds.nodes:
                nodes.append(f"""
                <div style="padding: 10px 14px; background: {tokens.surface}; border: 1px solid {tokens.accent_primary}; border-radius: 6px; text-align: center; min-width: 100px;">
                  <div style="font-weight: 600; font-size: 13px; color: {tokens.primary_text};">{html.escape(n.label)}</div>
                  {f'<div style="font-size: 11px; color: {tokens.secondary_text};">{html.escape(n.sublabel)}</div>' if n.sublabel else ''}
                </div>
                """)
            return f"""
            <div style="flex: 1; min-height: 200px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 16px; display: flex; align-items: center; justify-content: space-around; gap: 10px; box-shadow: {tokens.card_shadow};">
              {"".join(nodes)}
            </div>
            """
        return ""

    @classmethod
    def _render_svg_chart(
        cls,
        cs: Any,
        tokens: SlideDesignTokens,
        slide_id: str,
        theme_mode: str,
        c_spec: Any
    ) -> str:
        """Renders an accessible, vector SVG chart with axes, category labels, values, and theme styling."""
        categories = getattr(cs, "categories", []) or []
        series = getattr(cs, "series", []) or []
        c_px = int(c_spec.font_size_pt * 1.333) if c_spec else 18
        title_text = cs.title or (cs.family.value if hasattr(cs.family, 'value') else str(getattr(cs, 'family', 'Chart')))

        if not series:
            return f"""
            <div style="flex: 1; min-height: 220px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 16px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
              <div style="font-size: {c_px}px; color: {c_spec.color_hex if c_spec else tokens.primary_text}; font-weight: 700;">{html.escape(title_text)}</div>
              <div style="font-size: 12px; color: {tokens.muted_text}; margin-top: 8px;">No series data available</div>
            </div>
            """

        first_series = series[0]
        data_pts = getattr(first_series, "data", []) or []
        numeric_vals: list[float] = []
        for d in data_pts:
            if isinstance(d, (int, float)):
                numeric_vals.append(float(d))
            elif isinstance(d, dict) and "value" in d:
                try:
                    numeric_vals.append(float(d["value"]))
                except (ValueError, TypeError):
                    numeric_vals.append(0.0)
            elif isinstance(d, (list, tuple)) and len(d) > 1:
                try:
                    numeric_vals.append(float(d[1]))
                except (ValueError, TypeError):
                    numeric_vals.append(0.0)
            else:
                try:
                    numeric_vals.append(float(d))
                except (ValueError, TypeError):
                    numeric_vals.append(0.0)

        if not numeric_vals:
            numeric_vals = [10.0, 20.0, 30.0]

        max_val = max(numeric_vals) if numeric_vals else 100.0
        if max_val <= 0:
            max_val = 1.0

        width = 640
        height = 240
        pad_left = 55
        pad_right = 30
        pad_top = 30
        pad_bottom = 36
        plot_w = width - pad_left - pad_right
        plot_h = height - pad_top - pad_bottom

        n = len(numeric_vals)
        cat_labels = [str(c) for c in categories] if categories else [f"P{i+1}" for i in range(n)]
        while len(cat_labels) < n:
            cat_labels.append(f"P{len(cat_labels)+1}")

        bars_or_lines = []
        family_str = str(getattr(cs.family, "value", cs.family)).lower()
        is_line = "line" in family_str or "scatter" in family_str

        if is_line:
            pts = []
            for i, val in enumerate(numeric_vals):
                x = pad_left + (i * plot_w / (max(1, n - 1))) if n > 1 else pad_left + plot_w / 2
                y = pad_top + plot_h - (val / max_val * plot_h)
                pts.append((x, y))

            poly_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            area_pts = f"{pts[0][0]:.1f},{pad_top+plot_h} {poly_pts} {pts[-1][0]:.1f},{pad_top+plot_h}"
            bars_or_lines.append(f'<polygon points="{area_pts}" fill="{tokens.accent_primary}" fill-opacity="0.14" />')
            bars_or_lines.append(f'<polyline points="{poly_pts}" fill="none" stroke="{tokens.accent_primary}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />')

            for i, (x, y) in enumerate(pts):
                val_str = f"{numeric_vals[i]:.1f}".rstrip('0').rstrip('.')
                bars_or_lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{tokens.accent_primary}" stroke="{tokens.surface}" stroke-width="2" />')
                bars_or_lines.append(f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="{tokens.primary_text}">{val_str}</text>')
                bars_or_lines.append(f'<text x="{x:.1f}" y="{pad_top+plot_h+20:.1f}" text-anchor="middle" font-size="11" fill="{tokens.secondary_text}">{html.escape(cat_labels[i])}</text>')
        else:
            bar_w = min(48, max(16, int(plot_w / n * 0.55)))
            slot_w = plot_w / n
            for i, val in enumerate(numeric_vals):
                cx = pad_left + i * slot_w + slot_w / 2
                x = cx - bar_w / 2
                h = max(4.0, (val / max_val) * plot_h)
                y = pad_top + plot_h - h
                val_str = f"{val:.1f}".rstrip('0').rstrip('.')
                bars_or_lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" rx="4" fill="{tokens.accent_primary}" />')
                bars_or_lines.append(f'<text x="{cx:.1f}" y="{y-8:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="{tokens.primary_text}">{val_str}</text>')
                bars_or_lines.append(f'<text x="{cx:.1f}" y="{pad_top+plot_h+20:.1f}" text-anchor="middle" font-size="11" fill="{tokens.secondary_text}">{html.escape(cat_labels[i])}</text>')

        grid_lines = []
        for step in [0.0, 0.5, 1.0]:
            gy = pad_top + plot_h - step * plot_h
            val_step = step * max_val
            val_step_str = f"{val_step:.1f}".rstrip('0').rstrip('.')
            grid_lines.append(f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width-pad_right}" y2="{gy:.1f}" stroke="{tokens.border}" stroke-width="1" stroke-dasharray="3,3" />')
            grid_lines.append(f'<text x="{pad_left-8}" y="{gy+4:.1f}" text-anchor="end" font-size="10" fill="{tokens.muted_text}">{val_step_str}</text>')

        svg_content = f"""
        <svg viewBox="0 0 {width} {height}" style="width: 100%; height: auto; max-height: 280px; display: block;" role="img" aria-label="{html.escape(title_text)}">
          {"".join(grid_lines)}
          {"".join(bars_or_lines)}
        </svg>
        """
        series_label = getattr(first_series, "name", "Primary Series") or "Primary Series"
        return f"""
        <div style="flex: 1; min-height: 240px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 18px 24px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: {tokens.card_shadow};">
          <div style="font-weight: {c_spec.font_weight if c_spec else '700'}; font-size: {c_px}px; color: {c_spec.color_hex if c_spec else tokens.primary_text}; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span>{html.escape(title_text)}</span>
            <span style="font-size: 11px; font-weight: 500; color: {tokens.secondary_text}; background: rgba(255,255,255,0.06); padding: 3px 8px; border-radius: 4px;">{html.escape(series_label)}</span>
          </div>
          {svg_content}
        </div>
        """

    @classmethod
    def _render_table(
        cls,
        table_data: dict[str, Any] | None,
        tokens: SlideDesignTokens,
        slide_id: str = "slide-1",
        theme_mode: str = "dark",
        use_ai: bool = False
    ) -> str:
        if not table_data or not table_data.get("rows"):
            return ""
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])

        th_spec = TypographyResolver.resolve_block_typography(
            block_id=f"{slide_id}-table-th",
            text=" ".join(str(h) for h in headers),
            semantic_role=SemanticTypographyRole.TABLE_HEADER,
            font_family=tokens.font_body,
            theme_mode=theme_mode,
            use_ai=use_ai,
            background_hex=tokens.surface
        )
        td_spec = TypographyResolver.resolve_block_typography(
            block_id=f"{slide_id}-table-td",
            text=" ".join(str(c) for r in rows[:2] for c in r) if rows else "Table Cell",
            semantic_role=SemanticTypographyRole.TABLE_CELL,
            font_family=tokens.font_body,
            theme_mode=theme_mode,
            use_ai=use_ai,
            background_hex=tokens.surface
        )

        th_px = int(th_spec.font_size_pt * 1.333)
        td_px = int(td_spec.font_size_pt * 1.333)

        th_html = "".join(f'<th style="padding: 8px 12px; border-bottom: 2px solid {tokens.border}; text-align: left; font-size: {th_px}px; color: {th_spec.color_hex}; font-weight: {th_spec.font_weight};">{html.escape(str(h))}</th>' for h in headers)
        tr_html = []
        for r in rows[:6]:
            tds = "".join(f'<td style="padding: 8px 12px; border-bottom: 1px solid {tokens.border}; font-size: {td_px}px; color: {td_spec.color_hex};">{html.escape(str(cell))}</td>' for cell in r)
            tr_html.append(f"<tr>{tds}</tr>")

        return f"""
        <div style="overflow-x: auto; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 12px; box-shadow: {tokens.card_shadow};">
          <table style="width: 100%; border-collapse: collapse;">
            <thead><tr>{th_html}</tr></thead>
            <tbody>{"".join(tr_html)}</tbody>
          </table>
        </div>
        """

    @classmethod
    def _render_footer(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        slide_id: str = "slide-1",
        theme_mode: str = "dark",
        use_ai: bool = False
    ) -> str:
        footer = spec.source_footer
        src_spec = TypographyResolver.resolve_block_typography(
            block_id=f"{slide_id}-source",
            text=footer.source_citation or "Internal Analytics",
            semantic_role=SemanticTypographyRole.SOURCE,
            font_family=tokens.font_body,
            theme_mode=theme_mode,
            use_ai=use_ai,
            background_hex=tokens.background
        )
        src_px = int(src_spec.font_size_pt * 1.333)

        return f"""
        <footer style="margin-top: {tokens.card_gap}; padding-top: 8px; border-top: 1px solid {tokens.border}; display: flex; justify-content: space-between; align-items: center; font-size: {src_px}px; color: {src_spec.color_hex};">
          <div>
            <span>Source: {html.escape(footer.source_citation or 'Verified Data')}</span>
            {f'<span style="margin-left: 12px; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">{html.escape(footer.evidence_citation or "")}</span>' if footer.evidence_citation else ''}
          </div>
          <div>{html.escape(str(footer.slide_counter_text or spec.sequence_number or ''))}</div>
        </footer>
        """

    @classmethod
    def to_standalone_presentation_html(
        cls,
        specs: list[VisualSpecification],
        tokens: SlideDesignTokens,
        title: str = "Presentation",
        deck_id: str | None = None,
        use_ai: bool = False
    ) -> str:
        escaped_title = html.escape(title or 'Presentation')
        theme_mode = "dark" if "dark" in tokens.background.lower() or "111827" in tokens.background.lower() else "light"
        theme_vars = tokens.to_scoped_css_variables()
        var_styles = "; ".join(f"{k}: {v}" for k, v in theme_vars.items())

        slides_html_list = []
        for idx, spec in enumerate(specs):
            slide_html = cls.to_html_slide(
                spec=spec,
                tokens=tokens,
                slide_width=1920,
                slide_height=1080,
                use_ai=use_ai
            )
            is_active = idx == 0
            slide_section = f"""
    <section class="slide {'active visible' if is_active else ''}" id="slide-{idx+1}" data-slide-index="{idx}" role="group" aria-roledescription="slide" aria-label="Slide {idx+1} of {len(specs)}">
      {slide_html}
    </section>"""
            slides_html_list.append(slide_section)

        all_slides_html = "\n".join(slides_html_list)
        total_slides = len(specs)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} · HighView Presentation</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      {var_styles};
      --stage-bg: #05070A;
      --slide-bg: {tokens.background};
      --text-color: {tokens.primary_text};
      --accent: {tokens.accent_primary};
    }}

    * {{ box-sizing: border-box; }}

    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
      background: var(--stage-bg);
      font-family: {tokens.font_body};
      -webkit-font-smoothing: antialiased;
      user-select: text;
    }}

    .deck-viewport {{
      position: fixed;
      inset: 0;
      overflow: hidden;
      background: var(--stage-bg);
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .deck-stage {{
      position: absolute;
      left: 0;
      top: 0;
      width: 1920px;
      height: 1080px;
      overflow: hidden;
      transform-origin: 0 0;
      background: var(--slide-bg);
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.85);
      border-radius: 4px;
    }}

    .slide {{
      position: absolute;
      inset: 0;
      width: 1920px;
      height: 1080px;
      overflow: hidden;
      display: block;
      visibility: hidden;
      opacity: 0;
      pointer-events: none;
      background: var(--slide-bg);
      transition: opacity 0.22s ease, visibility 0.22s ease;
    }}

    .slide.active,
    .slide.visible {{
      visibility: visible;
      opacity: 1;
      pointer-events: auto;
      z-index: 1;
    }}

    /* Floating Navigation Controls */
    .deck-hud {{
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 10px;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 9999px;
      padding: 6px 14px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
      z-index: 100;
      user-select: none;
    }}

    .deck-hud-btn {{
      background: transparent;
      border: none;
      color: #F8FAFC;
      cursor: pointer;
      padding: 6px 10px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s ease, opacity 0.15s ease;
    }}

    .deck-hud-btn:hover:not(:disabled) {{
      background: rgba(255, 255, 255, 0.15);
    }}

    .deck-hud-btn:disabled {{
      opacity: 0.35;
      cursor: not-allowed;
    }}

    .deck-hud-counter {{
      font-size: 13px;
      font-weight: 600;
      color: #94A3B8;
      padding: 0 8px;
      letter-spacing: 0.04em;
    }}

    .deck-hud-divider {{
      width: 1px;
      height: 16px;
      background: rgba(255, 255, 255, 0.15);
    }}

    /* Print / PDF Export Styling */
    @media print {{
      @page {{
        size: 1920px 1080px;
        margin: 0;
      }}
      html, body {{
        width: 1920px !important;
        height: auto !important;
        overflow: visible !important;
        background: transparent !important;
      }}
      .deck-viewport, .deck-stage {{
        position: static !important;
        transform: none !important;
        width: 1920px !important;
        height: auto !important;
        overflow: visible !important;
        box-shadow: none !important;
        border-radius: 0 !important;
      }}
      .slide {{
        position: relative !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        width: 1920px !important;
        height: 1080px !important;
        page-break-after: always !important;
        break-after: page !important;
      }}
      .deck-hud {{
        display: none !important;
      }}
    }}
  </style>
</head>
<body>
  <div class="deck-viewport" id="viewport">
    <div class="deck-stage" id="deckStage" role="region" aria-roledescription="presentation stage" aria-label="{escaped_title}">
      {all_slides_html}
    </div>
  </div>

  <!-- Bottom Floating HUD Navigation -->
  <nav class="deck-hud" aria-label="Slide presentation navigation">
    <button type="button" class="deck-hud-btn" id="btnPrev" title="Previous Slide (Left Arrow, Space)" aria-label="Previous Slide">
      &#x25C0;
    </button>
    <span class="deck-hud-counter" id="slideCounter" aria-live="polite">
      Slide 1 of {total_slides}
    </span>
    <button type="button" class="deck-hud-btn" id="btnNext" title="Next Slide (Right Arrow)" aria-label="Next Slide">
      &#x25B6;
    </button>
    <div class="deck-hud-divider"></div>
    <button type="button" class="deck-hud-btn" id="btnFullscreen" title="Toggle Fullscreen (F)" aria-label="Fullscreen">
      &#x26F6;
    </button>
    <button type="button" class="deck-hud-btn" id="btnPrint" title="Print / Save to PDF" aria-label="Print presentation">
      &#x2399;
    </button>
  </nav>

  <script>
    (function() {{
      const totalSlides = {total_slides};
      let currentIndex = 0;
      const stage = document.getElementById("deckStage");
      const slides = document.querySelectorAll(".slide");
      const counter = document.getElementById("slideCounter");
      const btnPrev = document.getElementById("btnPrev");
      const btnNext = document.getElementById("btnNext");
      const btnFullscreen = document.getElementById("btnFullscreen");
      const btnPrint = document.getElementById("btnPrint");

      function updateScale() {{
        if (!stage) return;
        const cw = window.innerWidth;
        const ch = window.innerHeight;
        const factor = Math.min(cw / 1920, ch / 1080);
        const x = Math.max(0, (cw - 1920 * factor) / 2);
        const y = Math.max(0, (ch - 1080 * factor) / 2);
        stage.style.transform = `translate(${{x}}px, ${{y}}px) scale(${{factor}})`;
      }}

      function goToSlide(idx) {{
        if (idx < 0) idx = 0;
        if (idx >= totalSlides) idx = totalSlides - 1;
        currentIndex = idx;

        slides.forEach((s, i) => {{
          if (i === currentIndex) {{
            s.classList.add("active", "visible");
            s.setAttribute("aria-hidden", "false");
          }} else {{
            s.classList.remove("active", "visible");
            s.setAttribute("aria-hidden", "true");
          }}
        }});

        if (counter) {{
          counter.textContent = `Slide ${{currentIndex + 1}} of ${{totalSlides}}`;
        }}
        if (btnPrev) btnPrev.disabled = currentIndex === 0;
        if (btnNext) btnNext.disabled = currentIndex === totalSlides - 1;
      }}

      // Keyboard Controls
      window.addEventListener("keydown", (e) => {{
        if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
        if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {{
          e.preventDefault();
          goToSlide(currentIndex + 1);
        }} else if (e.key === "ArrowLeft" || e.key === "PageUp") {{
          e.preventDefault();
          goToSlide(currentIndex - 1);
        }} else if (e.key === "Home") {{
          e.preventDefault();
          goToSlide(0);
        }} else if (e.key === "End") {{
          e.preventDefault();
          goToSlide(totalSlides - 1);
        }} else if (e.key === "f" || e.key === "F") {{
          toggleFullscreen();
        }}
      }});

      // HUD Button Listeners
      if (btnPrev) btnPrev.addEventListener("click", () => goToSlide(currentIndex - 1));
      if (btnNext) btnNext.addEventListener("click", () => goToSlide(currentIndex + 1));
      if (btnFullscreen) btnFullscreen.addEventListener("click", toggleFullscreen);
      if (btnPrint) btnPrint.addEventListener("click", () => window.print());

      function toggleFullscreen() {{
        if (!document.fullscreenElement) {{
          document.documentElement.requestFullscreen().catch(() => {{}});
        }} else {{
          if (document.exitFullscreen) document.exitFullscreen().catch(() => {{}});
        }}
      }}

      // Touch / Swipe Support
      let touchStartX = 0;
      window.addEventListener("touchstart", (e) => {{
        if (e.touches && e.touches[0]) touchStartX = e.touches[0].clientX;
      }}, {{ passive: true }});
      window.addEventListener("touchend", (e) => {{
        if (e.changedTouches && e.changedTouches[0]) {{
          const diff = e.changedTouches[0].clientX - touchStartX;
          if (diff > 50) goToSlide(currentIndex - 1);
          else if (diff < -50) goToSlide(currentIndex + 1);
        }}
      }}, {{ passive: true }});

      window.addEventListener("resize", updateScale);
      document.addEventListener("fullscreenchange", () => setTimeout(updateScale, 100));

      updateScale();
      goToSlide(0);
    }})();
  </script>
</body>
</html>"""
