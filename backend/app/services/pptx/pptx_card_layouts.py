"""Card, hero, KPI, and action-oriented slide layouts for PowerPoint presentations."""

from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE

from .pptx_styles import add_styled_text_runs


def _render_title_hero_slide(slide, slide_data, colors):
    left_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(6.8), Inches(4.7))
    left_card.fill.solid()
    left_card.fill.fore_color.rgb = colors["card_bg"]
    left_card.line.color.rgb = colors["card_border"]
    left_card.line.width = Pt(1)

    tf = left_card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.3)
    tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.3)
    tf.margin_bottom = Inches(0.3)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "")
    p0.font.size = Pt(14)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(12)

    narrative = slide_data.get("narrative", "")
    if narrative:
        p_narr = tf.add_paragraph()
        add_styled_text_runs(p_narr, narrative, font_size=11, default_color=colors["primary"])
        p_narr.space_after = Pt(12)

    bullets = slide_data.get("bullets", [])
    for b in bullets:
        p_b = tf.add_paragraph()
        p_b.space_after = Pt(8)
        run_dot = p_b.add_run()
        run_dot.text = "• "
        run_dot.font.color.rgb = colors["brand"]
        run_dot.font.size = Pt(11)
        run_dot.font.bold = True
        add_styled_text_runs(p_b, b, font_size=11, default_color=colors["secondary"])

    metrics = slide_data.get("metrics", [])
    if metrics:
        top_offset = 1.8
        card_h = 1.02
        spacing = 0.2
        for i, m in enumerate(metrics[:4]):
            m_card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(8.0), Inches(top_offset + i * (card_h + spacing)),
                Inches(4.5), Inches(card_h)
            )
            m_card.fill.solid()
            m_card.fill.fore_color.rgb = colors["card_bg"]
            m_card.line.color.rgb = colors["card_border"]
            m_card.line.width = Pt(1)

            mtf = m_card.text_frame
            mtf.word_wrap = True
            mtf.margin_left = Inches(0.25)
            mtf.margin_top = Inches(0.15)

            p_val = mtf.paragraphs[0]
            p_val.text = str(m.get("value", ""))
            p_val.font.size = Pt(20)
            p_val.font.bold = True
            p_val.font.color.rgb = colors["brand"]

            p_lbl = mtf.add_paragraph()
            p_lbl.text = f"{m.get('label', '')} · {m.get('subtext', '')}"
            p_lbl.font.size = Pt(10)
            p_lbl.font.color.rgb = colors["secondary"]


def _render_kpi_summary_slide(slide, slide_data, colors):
    narrative_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.7), Inches(11.7), Inches(0.9))
    tf_n = narrative_box.text_frame
    tf_n.word_wrap = True
    p_sub = tf_n.paragraphs[0]
    p_sub.text = slide_data.get("subtitle", "")
    p_sub.font.size = Pt(13)
    p_sub.font.bold = True
    p_sub.font.color.rgb = colors["accent"]
    p_sub.space_after = Pt(4)

    if slide_data.get("narrative"):
        p_desc = tf_n.add_paragraph()
        add_styled_text_runs(p_desc, slide_data["narrative"], font_size=11, default_color=colors["primary"])

    metrics = slide_data.get("metrics", [])
    num_metrics = min(4, len(metrics))
    if num_metrics > 0:
        total_w = 11.7
        spacing = 0.25
        card_w = (total_w - (num_metrics - 1) * spacing) / num_metrics
        for i, m in enumerate(metrics[:num_metrics]):
            x = 0.8 + i * (card_w + spacing)
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.8), Inches(card_w), Inches(2.2))
            card.fill.solid()
            card.fill.fore_color.rgb = colors["card_bg"]
            card.line.color.rgb = colors["card_border"]
            card.line.width = Pt(1)

            ctf = card.text_frame
            ctf.word_wrap = True
            ctf.margin_left = Inches(0.2)
            ctf.margin_right = Inches(0.2)
            ctf.margin_top = Inches(0.2)

            p_lbl = ctf.paragraphs[0]
            p_lbl.text = str(m.get("label", "")).upper()
            p_lbl.font.size = Pt(9)
            p_lbl.font.bold = True
            p_lbl.font.color.rgb = colors["brand"]
            p_lbl.space_after = Pt(6)

            p_val = ctf.add_paragraph()
            p_val.text = str(m.get("value", ""))
            p_val.font.size = Pt(22)
            p_val.font.bold = True
            p_val.font.color.rgb = colors["primary"]
            p_val.space_after = Pt(6)

            p_sub = ctf.add_paragraph()
            p_sub.text = str(m.get("subtext", ""))
            p_sub.font.size = Pt(9)
            p_sub.font.color.rgb = colors["secondary"]

    bullets = slide_data.get("bullets", [])
    if bullets:
        bot_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.2), Inches(11.7), Inches(1.4))
        bot_card.fill.solid()
        bot_card.fill.fore_color.rgb = colors["card_bg"]
        bot_card.line.color.rgb = colors["card_border"]
        bot_card.line.width = Pt(1)

        btf = bot_card.text_frame
        btf.word_wrap = True
        btf.margin_left = Inches(0.25)
        btf.margin_top = Inches(0.15)
        p_hd = btf.paragraphs[0]
        p_hd.text = "KEY TAKEAWAYS & EMPIRICAL THRESHOLDS"
        p_hd.font.size = Pt(9)
        p_hd.font.bold = True
        p_hd.font.color.rgb = colors["accent"]
        p_hd.space_after = Pt(4)

        for b in bullets[:2]:
            pb = btf.add_paragraph()
            pb.space_after = Pt(4)
            run_dot = pb.add_run()
            run_dot.text = "• "
            run_dot.font.color.rgb = colors["brand"]
            add_styled_text_runs(pb, b, font_size=10, default_color=colors["secondary"])


def _render_comparison_split_slide(slide, slide_data, colors):
    left_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(6.5), Inches(4.8))
    left_card.fill.solid()
    left_card.fill.fore_color.rgb = colors["card_bg"]
    left_card.line.color.rgb = colors["card_border"]
    left_card.line.width = Pt(1)

    tf = left_card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.3)
    tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "Strategic Action Plan")
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(8)

    narrative = slide_data.get("narrative", "")
    if narrative:
        pn = tf.add_paragraph()
        add_styled_text_runs(pn, narrative, font_size=11, default_color=colors["primary"])
        pn.space_after = Pt(12)

    bullets = slide_data.get("bullets", [])
    for b in bullets:
        pb = tf.add_paragraph()
        pb.space_after = Pt(8)
        rd = pb.add_run()
        rd.text = "• "
        rd.font.color.rgb = colors["brand"]
        rd.font.bold = True
        add_styled_text_runs(pb, b, font_size=10, default_color=colors["secondary"])

    metrics = slide_data.get("metrics", [])
    if not metrics:
        metrics = [
            {"label": "Priority 1", "value": "Operational Alignment", "subtext": "Immediate focus"},
            {"label": "Priority 2", "value": "Variance Mitigation", "subtext": "Quarterly milestone"},
            {"label": "Priority 3", "value": "Continuous Tracking", "subtext": "Automated governance"}
        ]
    top_offset = 1.8
    card_h = 1.45
    spacing = 0.2
    for i, m in enumerate(metrics[:3]):
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(7.6), Inches(top_offset + i * (card_h + spacing)),
            Inches(4.9), Inches(card_h)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = colors["card_bg"]
        card.line.color.rgb = colors["card_border"]
        card.line.width = Pt(1)

        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_left = Inches(0.25)
        ctf.margin_top = Inches(0.18)

        pl = ctf.paragraphs[0]
        pl.text = str(m.get("label", f"Priority {i+1}")).upper()
        pl.font.size = Pt(10)
        pl.font.bold = True
        pl.font.color.rgb = colors["accent"]
        pl.space_after = Pt(4)

        pv = ctf.add_paragraph()
        pv.text = str(m.get("value", ""))
        pv.font.size = Pt(16)
        pv.font.bold = True
        pv.font.color.rgb = colors["brand"]
        pv.space_after = Pt(3)

        ps = ctf.add_paragraph()
        ps.text = str(m.get("subtext", ""))
        ps.font.size = Pt(10)
        ps.font.color.rgb = colors["secondary"]


def _render_action_plan_slide(slide, slide_data, colors):
    narr_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(11.7), Inches(0.75))
    tf_n = narr_box.text_frame
    tf_n.word_wrap = True
    p0 = tf_n.paragraphs[0]
    p0.text = slide_data.get("subtitle", "Strategic Operational Initiatives").upper()
    p0.font.size = Pt(11)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(3)

    if slide_data.get("narrative"):
        pn = tf_n.add_paragraph()
        add_styled_text_runs(pn, slide_data["narrative"], font_size=10, default_color=colors["secondary"])

    initiatives = slide_data.get("initiatives", [])
    if not initiatives and slide_data.get("structured_proposals"):
        initiatives = [
            {
                "priority": p.get("priority", "MEDIUM"),
                "title": p.get("proposed_response", f"Proposal {i+1}"),
                "finding": p.get("motivating_finding", ""),
                "owner": p.get("owner_role", "Unassigned - Operational Lead"),
                "metric": p.get("success_metric", "Defined SLA Target"),
                "dependency": p.get("dependencies", "Leadership Alignment")
            }
            for i, p in enumerate(slide_data["structured_proposals"][:3])
        ]
    elif not initiatives and slide_data.get("metrics"):
        initiatives = [
            {
                "priority": "HIGH",
                "title": m.get("value", f"Initiative {i+1}"),
                "finding": m.get("label", "Operational Focus Area"),
                "owner": "Unassigned - Operations Lead",
                "metric": m.get("subtext", "Defined SLA Target"),
                "dependency": "Leadership Alignment"
            }
            for i, m in enumerate(slide_data["metrics"][:3])
        ]

    card_w = 3.7
    spacing = 0.3
    for i, init in enumerate(initiatives[:3]):
        x = 0.8 + i * (card_w + spacing)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.55), Inches(card_w), Inches(4.1))
        card.fill.solid()
        card.fill.fore_color.rgb = colors["card_bg"]
        card.line.color.rgb = colors["card_border"]
        card.line.width = Pt(1)

        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_left = Inches(0.22)
        ctf.margin_right = Inches(0.22)
        ctf.margin_top = Inches(0.2)

        p_pri = ctf.paragraphs[0]
        p_pri.text = f"[{str(init.get('priority', 'MEDIUM')).upper()} PRIORITY]"
        p_pri.font.size = Pt(9)
        p_pri.font.bold = True
        p_pri.font.color.rgb = colors["accent"]
        p_pri.space_after = Pt(6)

        p_tit = ctf.add_paragraph()
        p_tit.text = str(init.get("title", f"Proposal {i+1}"))
        p_tit.font.size = Pt(13)
        p_tit.font.bold = True
        p_tit.font.color.rgb = colors["primary"]
        p_tit.space_after = Pt(8)

        p_fnd = ctf.add_paragraph()
        p_fnd.text = "Motivating Finding:"
        p_fnd.font.size = Pt(8.5)
        p_fnd.font.bold = True
        p_fnd.font.color.rgb = colors["brand"]
        p_fnd_v = ctf.add_paragraph()
        add_styled_text_runs(p_fnd_v, str(init.get("finding", "")), font_size=9.5, default_color=colors["secondary"])
        p_fnd_v.space_after = Pt(6)

        p_own = ctf.add_paragraph()
        p_own.text = f"Assigned Role: {init.get('owner', 'Unassigned - Operations Lead')}"
        p_own.font.size = Pt(9)
        p_own.font.bold = True
        p_own.font.color.rgb = colors["accent"]
        p_own.space_after = Pt(4)

        p_suc = ctf.add_paragraph()
        p_suc.text = f"Target Metric: {init.get('metric', 'Target Benchmark')}"
        p_suc.font.size = Pt(8.5)
        p_suc.font.color.rgb = colors["secondary"]


def _render_generic_slide(slide, slide_data, colors):
    """Fallback renderer for custom or unmapped layout types."""
    _render_comparison_split_slide(slide, slide_data, colors)
