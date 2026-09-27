"""HTML Slide Generator Adapter for Phase 4.

Transforms canonical VisualSpecification models into self-contained, beautifully rendered HTML slides.
Adheres strictly to presentation design tokens and scoped CSS rules.
"""

from __future__ import annotations

import html
from typing import Any
from ..design_tokens import SlideDesignTokens
from ..visual_models import VisualSpecification


class HTMLAdapter:
    """Renders VisualSpecification into standalone, self-contained HTML slides."""

    @classmethod
    def to_html_slide(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens,
        slide_width: int = 1280,
        slide_height: int = 720
    ) -> str:
        """Renders a single slide into an isolated HTML string."""
        theme_vars = tokens.to_scoped_css_variables()
        var_styles = "; ".join(f"{k}: {v}" for k, v in theme_vars.items())

        # Render sections
        kpi_html = cls._render_kpis(spec.kpis, tokens)
        insights_html = cls._render_insights(spec.insights, tokens)
        visual_html = cls._render_primary_visual(spec, tokens)
        table_html = cls._render_table(spec.table_data, tokens)
        footer_html = cls._render_footer(spec, tokens)

        slide_id = f"slide-{spec.sequence_number}"

        html_content = f"""
<div class="presentation-runtime" id="{slide_id}" style="width: {slide_width}px; height: {slide_height}px; position: relative; overflow: hidden; background: {tokens.background}; color: {tokens.primary_text}; font-family: {tokens.font_body}; box-sizing: border-box; padding: {tokens.slide_padding}; {var_styles}; display: flex; flex-direction: column; justify-content: space-between;">
  <!-- Slide Header -->
  <header style="margin-bottom: {tokens.card_gap};">
    <div style="font-size: {tokens.font_size_caption}; text-transform: uppercase; letter-spacing: 0.1em; color: {tokens.accent_primary}; font-weight: 600; margin-bottom: 4px;">
      {html.escape(spec.visual_story.primary_message or 'Executive Briefing')}
    </div>
    <h2 style="font-family: {tokens.font_heading}; font-size: {tokens.font_size_headline}; font-weight: 700; color: {tokens.primary_text}; margin: 0 0 6px 0; line-height: 1.2;">
      {html.escape(spec.headline)}
    </h2>
    {f'<p style="font-size: {tokens.font_size_subtitle}; color: {tokens.secondary_text}; margin: 0; line-height: 1.4;">{html.escape(spec.subtitle)}</p>' if spec.subtitle else ''}
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
    def _render_kpis(cls, kpis: list[dict[str, Any]], tokens: SlideDesignTokens) -> str:
        if not kpis:
            return ""
        items = []
        for k in kpis:
            label = html.escape(str(k.get("label", "Metric")))
            val = html.escape(str(k.get("value", "0")))
            sub = html.escape(str(k.get("subtext", "")))
            item_html = f"""
            <div style="flex: 1; min-width: 140px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 12px 16px; box-shadow: {tokens.card_shadow};">
              <div style="font-size: {tokens.font_size_caption}; color: {tokens.secondary_text}; text-transform: uppercase; font-weight: 600;">{label}</div>
              <div style="font-family: {tokens.font_heading}; font-size: {tokens.font_size_kpi}; font-weight: 700; color: {tokens.accent_primary}; margin: 4px 0;">{val}</div>
              {f'<div style="font-size: 11px; color: {tokens.muted_text};">{sub}</div>' if sub else ''}
            </div>
            """
            items.append(item_html)

        return f'<div style="display: flex; gap: {tokens.card_gap}; flex-wrap: wrap;">{"".join(items)}</div>'

    @classmethod
    def _render_insights(cls, insights: list[str], tokens: SlideDesignTokens) -> str:
        if not insights:
            return ""
        items = []
        for ins in insights:
            items.append(f"""
            <li style="margin-bottom: 10px; line-height: 1.4; color: {tokens.primary_text}; font-size: {tokens.font_size_body};">
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
    def _render_primary_visual(cls, spec: VisualSpecification, tokens: SlideDesignTokens) -> str:
        if spec.chart_spec:
            cs = spec.chart_spec
            series_summary = ", ".join(f"{s.name} ({len(s.data)} pts)" for s in cs.series)
            return f"""
            <div style="flex: 1; min-height: 220px; background: {tokens.surface}; border: 1px solid {tokens.border}; border-radius: {tokens.card_border_radius}; padding: 16px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: {tokens.card_shadow};">
              <div style="font-weight: 600; font-size: {tokens.font_size_body}; color: {tokens.primary_text}; margin-bottom: 8px;">[Chart: {html.escape(cs.title or cs.family.value)}]</div>
              <div style="font-size: {tokens.font_size_caption}; color: {tokens.secondary_text};">{html.escape(series_summary)}</div>
              <div style="margin-top: 8px; font-size: 11px; color: {tokens.muted_text}; font-style: italic;">Rendered via ECharts engine ({cs.family.value})</div>
            </div>
            """
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
    def _render_table(cls, table_data: dict[str, Any] | None, tokens: SlideDesignTokens) -> str:
        if not table_data or not table_data.get("rows"):
            return ""
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])

        th_html = "".join(f'<th style="padding: 8px 12px; border-bottom: 2px solid {tokens.border}; text-align: left; font-size: 12px; color: {tokens.secondary_text}; font-weight: 600;">{html.escape(str(h))}</th>' for h in headers)
        tr_html = []
        for r in rows[:6]:
            tds = "".join(f'<td style="padding: 8px 12px; border-bottom: 1px solid {tokens.border}; font-size: 12px; color: {tokens.primary_text};">{html.escape(str(cell))}</td>' for cell in r)
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
    def _render_footer(cls, spec: VisualSpecification, tokens: SlideDesignTokens) -> str:
        footer = spec.source_footer
        return f"""
        <footer style="margin-top: {tokens.card_gap}; padding-top: 8px; border-top: 1px solid {tokens.border}; display: flex; justify-content: space-between; align-items: center; font-size: {tokens.font_size_caption}; color: {tokens.muted_text};">
          <div>
            <span>Source: {html.escape(footer.source_citation)}</span>
            {f'<span style="margin-left: 12px; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">{html.escape(footer.evidence_citation)}</span>' if footer.evidence_citation else ''}
          </div>
          <div>{html.escape(footer.slide_counter_text or f'{spec.sequence_number}')}</div>
        </footer>
        """
