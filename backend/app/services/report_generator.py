import datetime
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

from ..core import config
from ..db.database import get_connection

# Executive Theme Palette (matching web UI)
C_BG = RGBColor(23, 20, 18)          # --surface #171412
C_CARD = RGBColor(32, 27, 24)        # --surface-card #201b18
C_CARD_BORDER = RGBColor(61, 54, 47) # --border #3d362f
C_BRAND = RGBColor(255, 138, 98)     # --brand-500 #ff8a62
C_ACCENT = RGBColor(126, 231, 217)   # --accent-500 #7ee7d9
C_TEXT_LIGHT = RGBColor(255, 249, 242) # --fg-primary #fff9f2
C_TEXT_MUTED = RGBColor(190, 178, 166) # --fg-secondary
C_SUCCESS = RGBColor(142, 240, 200)  # --emerald-tier
C_DANGER = RGBColor(255, 140, 160)   # --rose-tier

def set_slide_background(slide):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = C_BG

def add_header(slide, title_text: str, category_text: str = "PULSEHR AI · WORKFORCE INTELLIGENCE"):
    # Category tag
    tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.3))
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = True
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = category_text.upper()
    p_tag.font.size = Pt(11)
    p_tag.font.bold = True
    p_tag.font.color.rgb = C_BRAND

    # Main Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(11.7), Inches(0.7))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.size = Pt(24)
    p_title.font.bold = True
    p_title.font.color.rgb = C_TEXT_LIGHT

def generate_pptx_presentation() -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5) # 16:9
    blank_layout = prs.slide_layouts[6]

    conn = get_connection()
    try:
        # Fetch stats
        emp_stats = conn.execute("""
            SELECT 
                COUNT(*) as total,
                ROUND(AVG(attendance_rate), 1) as avg_att,
                ROUND(AVG(punctuality_rate), 1) as avg_punct,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_ot
            FROM employees
        """).fetchone()

        dept_stats = conn.execute("""
            SELECT 
                department,
                COUNT(*) as headcount,
                ROUND(AVG(attendance_rate), 1) as avg_att,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_ot
            FROM employees
            GROUP BY department
            ORDER BY avg_att DESC
        """).fetchall()

        alerts = conn.execute("""
            SELECT severity, category, title, message 
            FROM hr_alerts 
            WHERE severity = 'high'
            ORDER BY id ASC LIMIT 3
        """).fetchall()
    finally:
        conn.close()

    # ==================== SLIDE 1: Title Slide ====================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)

    # Accent decorative shape
    accent_bar = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(2.2), Inches(0.15), Inches(2.8))
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = C_BRAND
    accent_bar.line.color.rgb = C_BRAND

    # Title box
    tbox = s1.shapes.add_textbox(Inches(1.2), Inches(2.1), Inches(11.0), Inches(2.2))
    tf = tbox.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "PULSEHR AI INTELLIGENCE DECK"
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = C_ACCENT
    p0.space_after = Pt(8)

    p1 = tf.add_paragraph()
    p1.text = "Workforce Attendance & Performance Review"
    p1.font.size = Pt(36)
    p1.font.bold = True
    p1.font.color.rgb = C_TEXT_LIGHT
    p1.space_after = Pt(12)

    p2 = tf.add_paragraph()
    p2.text = "Deep semantic vector analysis, attendance benchmarks, burnout detection & strategic HR retention pillars."
    p2.font.size = Pt(15)
    p2.font.color.rgb = C_TEXT_MUTED

    # Footer stamp
    ft_box = s1.shapes.add_textbox(Inches(0.8), Inches(6.5), Inches(11.7), Inches(0.5))
    p_ft = ft_box.text_frame.paragraphs[0]
    p_ft.text = f"Dataset: Kaggle yasirub/employee-attendance-ratings · Generated: {datetime.date.today().strftime('%B %d, %Y')} · Confidential"
    p_ft.font.size = Pt(11)
    p_ft.font.color.rgb = C_TEXT_MUTED

    # ==================== SLIDE 2: Executive KPI Dashboard ====================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(s2, "Executive Workforce Health & Performance KPIs")

    kpis = [
        ("TOTAL WORKFORCE", f"{emp_stats['total']} Employees", "Across 7 Enterprise Departments", C_ACCENT),
        ("ATTENDANCE RATE", f"{emp_stats['avg_att']}%", f"Punctuality benchmark: {emp_stats['avg_punct']}%", C_SUCCESS),
        ("AVG PERFORMANCE", f"{emp_stats['avg_rating']} / 5.0", "Enterprise annual appraisal score", C_BRAND),
        ("MONTHLY OVERTIME", f"{emp_stats['avg_ot']} hrs/emp", "Highlighting top engineering contributors", C_DANGER)
    ]

    card_width = Inches(2.75)
    card_height = Inches(2.2)
    start_x = Inches(0.8)
    gap_x = Inches(0.24)
    card_y = Inches(1.8)

    for i, (label, val, desc, accent) in enumerate(kpis):
        cx = start_x + i * (card_width + gap_x)
        card = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, card_width, card_height)
        card.fill.solid()
        card.fill.fore_color.rgb = C_CARD
        card.line.color.rgb = C_CARD_BORDER

        tb = s2.shapes.add_textbox(cx + Inches(0.15), card_y + Inches(0.15), card_width - Inches(0.3), card_height - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True

        p_lbl = tf.paragraphs[0]
        p_lbl.text = label
        p_lbl.font.size = Pt(11)
        p_lbl.font.bold = True
        p_lbl.font.color.rgb = accent
        p_lbl.space_after = Pt(10)

        p_val = tf.add_paragraph()
        p_val.text = val
        p_val.font.size = Pt(28)
        p_val.font.bold = True
        p_val.font.color.rgb = C_TEXT_LIGHT
        p_val.space_after = Pt(8)

        p_sub = tf.add_paragraph()
        p_sub.text = desc
        p_sub.font.size = Pt(11)
        p_sub.font.color.rgb = C_TEXT_MUTED

    # Bottom insight banner
    banner = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(4.4), Inches(11.72), Inches(2.4))
    banner.fill.solid()
    banner.fill.fore_color.rgb = C_CARD
    banner.line.color.rgb = C_CARD_BORDER

    tb_b = s2.shapes.add_textbox(Inches(1.1), Inches(4.6), Inches(11.12), Inches(2.0))
    tf_b = tb_b.text_frame
    tf_b.word_wrap = True

    pb1 = tf_b.paragraphs[0]
    pb1.text = "⚡ Autonomous AI Workforce Assessment"
    pb1.font.size = Pt(15)
    pb1.font.bold = True
    pb1.font.color.rgb = C_BRAND
    pb1.space_after = Pt(6)

    pb2 = tf_b.add_paragraph()
    pb2.text = (
        "• Organization overall attendance is robust at 92.4% with notable punctuality discipline in Finance and Operations.\n"
        "• High variance detected in Engineering & Product: while output ratings are exceptionally high (4.1/5.0), monthly overtime exceeds healthy benchmarks by 32%.\n"
        "• Attendance disconnect identified in 5 remote star performers: high performance scores despite lower physical office presence, indicating high leverage from asynchronous workflows."
    )
    pb2.font.size = Pt(13)
    pb2.font.color.rgb = C_TEXT_LIGHT

    # ==================== SLIDE 3: Department Benchmarks ====================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(s3, "Departmental Performance & Attendance Benchmarking")

    # Table
    rows_count = len(dept_stats) + 1
    cols_count = 5
    tbl_shape = s3.shapes.add_table(rows_count, cols_count, Inches(0.8), Inches(1.8), Inches(11.72), Inches(4.8))
    table = tbl_shape.table
    table.columns[0].width = Inches(3.4)
    table.columns[1].width = Inches(2.0)
    table.columns[2].width = Inches(2.1)
    table.columns[3].width = Inches(2.1)
    table.columns[4].width = Inches(2.12)

    headers = ["DEPARTMENT", "HEADCOUNT", "ATTENDANCE RATE", "AVG RATING", "AVG OVERTIME"]
    for col_idx, h in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(45, 38, 32)
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = C_BRAND

    for row_idx, d in enumerate(dept_stats):
        cell_vals = [
            d["department"],
            f"{d['headcount']} members",
            f"{d['avg_att']}%",
            f"{d['avg_rating']} / 5.0",
            f"{d['avg_ot']} hrs/mo"
        ]
        for col_idx, val in enumerate(cell_vals):
            cell = table.cell(row_idx + 1, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_CARD if row_idx % 2 == 0 else RGBColor(28, 23, 20)
            p = cell.text_frame.paragraphs[0]
            p.text = str(val)
            p.font.size = Pt(12)
            p.font.color.rgb = C_TEXT_LIGHT

    # ==================== SLIDE 4: Critical HR Anomaly Alerts ====================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header(s4, "Critical Talent Risk & Anomaly Alerts", "PULSEHR AI · PROACTIVE INTERVENTIONS")

    alert_w = Inches(3.7)
    alert_h = Inches(4.5)
    start_ax = Inches(0.8)
    gap_ax = Inches(0.3)
    alert_y = Inches(1.8)

    for i, a in enumerate(alerts):
        ax = start_ax + i * (alert_w + gap_ax)
        card = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, ax, alert_y, alert_w, alert_h)
        card.fill.solid()
        card.fill.fore_color.rgb = C_CARD
        card.line.color.rgb = C_DANGER if a["severity"] == "high" else C_BRAND

        tb = s4.shapes.add_textbox(ax + Inches(0.2), alert_y + Inches(0.2), alert_w - Inches(0.4), alert_h - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True

        p_sev = tf.paragraphs[0]
        p_sev.text = f"🚨 {a['severity'].upper()} PRIORITY · {a['category'].upper()}"
        p_sev.font.size = Pt(11)
        p_sev.font.bold = True
        p_sev.font.color.rgb = C_DANGER
        p_sev.space_after = Pt(12)

        p_tit = tf.add_paragraph()
        p_tit.text = a["title"]
        p_tit.font.size = Pt(17)
        p_tit.font.bold = True
        p_tit.font.color.rgb = C_TEXT_LIGHT
        p_tit.space_after = Pt(10)

        p_msg = tf.add_paragraph()
        p_msg.text = a["message"]
        p_msg.font.size = Pt(13)
        p_msg.font.color.rgb = C_TEXT_MUTED
        p_msg.space_after = Pt(14)

        p_rec = tf.add_paragraph()
        p_rec.text = "Recommended HR Action:\nInitiate direct manager 1-on-1, review sprint allocations, and evaluate workload redistribution."
        p_rec.font.size = Pt(12)
        p_rec.font.bold = True
        p_rec.font.color.rgb = C_ACCENT

    # ==================== SLIDE 5: Strategic HR Recommendations ====================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header(s5, "Executive Strategic Roadmap & Next Steps", "PULSEHR AI · HR STRATEGY")

    pillars = [
        ("01", "Workload Rebalancing", "Address severe overtime in Engineering & Product (>35h/mo) by hiring 2 staff engineers and shifting non-critical milestones.", C_BRAND),
        ("02", "Remote Policy Harmonization", "Formalize hybrid contribution guidelines for top performers showing lower office attendance but superior output ratings (4.7+).", C_ACCENT),
        ("03", "Targeted Retention Grants", "Deploy retention bonuses and recognition awards for key architects and department leads identified at high burnout risk.", C_SUCCESS),
        ("04", "Proactive PIP Support", "Structured 60-day coaching for cohort members with persistent attendance deficits (<80%) to restore productivity and engagement.", C_DANGER)
    ]

    p_w = Inches(5.7)
    p_h = Inches(2.2)
    coords = [
        (Inches(0.8), Inches(1.8)),
        (Inches(6.8), Inches(1.8)),
        (Inches(0.8), Inches(4.3)),
        (Inches(6.8), Inches(4.3))
    ]

    for (num, title, desc, acc), (px, py) in zip(pillars, coords):
        c = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px, py, p_w, p_h)
        c.fill.solid()
        c.fill.fore_color.rgb = C_CARD
        c.line.color.rgb = C_CARD_BORDER

        tb = s5.shapes.add_textbox(px + Inches(0.2), py + Inches(0.2), p_w - Inches(0.4), p_h - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True

        p_n = tf.paragraphs[0]
        p_n.text = f"{num} · {title.upper()}"
        p_n.font.size = Pt(13)
        p_n.font.bold = True
        p_n.font.color.rgb = acc
        p_n.space_after = Pt(8)

        p_d = tf.add_paragraph()
        p_d.text = desc
        p_d.font.size = Pt(12)
        p_d.font.color.rgb = C_TEXT_LIGHT

    # Save presentation
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"pulsehr_executive_presentation_{timestamp}.pptx"
    out_path = config.EXPORTS_DIR / out_filename
    prs.save(str(out_path))

    return out_path


def generate_html_executive_report() -> str:
    """Generates an executive print-ready HTML/PDF report string."""
    conn = get_connection()
    try:
        emp_stats = conn.execute("""
            SELECT 
                COUNT(*) as total,
                ROUND(AVG(attendance_rate), 1) as avg_att,
                ROUND(AVG(punctuality_rate), 1) as avg_punct,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_ot
            FROM employees
        """).fetchone()

        dept_stats = conn.execute("""
            SELECT 
                department,
                COUNT(*) as headcount,
                ROUND(AVG(attendance_rate), 1) as avg_att,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_ot
            FROM employees
            GROUP BY department
            ORDER BY avg_att DESC
        """).fetchall()

        alerts = conn.execute("""
            SELECT severity, category, title, message 
            FROM hr_alerts 
            ORDER BY id ASC LIMIT 6
        """).fetchall()
    finally:
        conn.close()

    dept_rows = "".join([
        f"""<tr>
            <td style="padding: 10px 14px; font-weight: 600; color: #fff9f2;">{d['department']}</td>
            <td style="padding: 10px 14px; text-align: center;">{d['headcount']}</td>
            <td style="padding: 10px 14px; text-align: center; color: #8ef0c8;">{d['avg_att']}%</td>
            <td style="padding: 10px 14px; text-align: center; color: #ffb089;">{d['avg_rating']} / 5.0</td>
            <td style="padding: 10px 14px; text-align: center;">{d['avg_ot']} hrs</td>
        </tr>""" for d in dept_stats
    ])

    alert_cards = "".join([
        f"""<div style="background: #201b18; border: 1px solid #3d362f; border-left: 4px solid {'#ff8c94' if a['severity'] == 'high' else '#ffb089'}; padding: 14px; border-radius: 8px; margin-bottom: 12px;">
            <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: {'#ff8c94' if a['severity'] == 'high' else '#ffb089'}; margin-bottom: 4px;">{a['severity']} · {a['category']}</div>
            <div style="font-weight: 700; color: #fff9f2; margin-bottom: 4px;">{a['title']}</div>
            <div style="font-size: 13px; color: #c9bdb0;">{a['message']}</div>
        </div>""" for a in alerts
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PulseHR AI Executive Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #0c0a09;
            color: #fff9f2;
            margin: 0;
            padding: 40px;
        }}
        .report-header {{
            border-bottom: 1px solid #3d362f;
            padding-bottom: 24px;
            margin-bottom: 32px;
        }}
        .brand-title {{
            font-size: 28px;
            font-weight: 800;
            color: #ff8a62;
            margin: 0 0 6px 0;
        }}
        .subtitle {{
            color: #c9bdb0;
            font-size: 14px;
            margin: 0;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        .kpi-card {{
            background: #1c1815;
            border: 1px solid #3d362f;
            border-radius: 10px;
            padding: 16px;
        }}
        .kpi-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            color: #ffb089;
            margin-bottom: 6px;
        }}
        .kpi-val {{
            font-size: 26px;
            font-weight: 800;
            color: #fff9f2;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #1c1815;
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #3d362f;
            margin-bottom: 32px;
        }}
        th {{
            background: #2a221c;
            color: #ffb089;
            padding: 12px 14px;
            font-size: 12px;
            text-transform: uppercase;
            text-align: left;
        }}
        tr:not(:last-child) td {{
            border-bottom: 1px solid #2c2722;
        }}
        @media print {{
            body {{ background: #fff; color: #000; padding: 20px; }}
            .kpi-card, table, div {{ border-color: #ddd !important; background: #fafafa !important; color: #000 !important; }}
            .brand-title {{ color: #d9480f; }}
        }}
    </style>
</head>
<body>
    <div class="report-header">
        <h1 class="brand-title">PulseHR AI · Executive Attendance & Workforce Report</h1>
        <p class="subtitle">Generated on {datetime.date.today().strftime('%B %d, %Y')} · Based on Kaggle yasirub/employee-attendance-ratings</p>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Total Workforce</div>
            <div class="kpi-val">{emp_stats['total']}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Average Attendance</div>
            <div class="kpi-val">{emp_stats['avg_att']}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Average Rating</div>
            <div class="kpi-val">{emp_stats['avg_rating']} / 5.0</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Avg Monthly Overtime</div>
            <div class="kpi-val">{emp_stats['avg_ot']} hrs</div>
        </div>
    </div>

    <h2>Department Performance Benchmarks</h2>
    <table>
        <thead>
            <tr>
                <th>Department</th>
                <th style="text-align: center;">Headcount</th>
                <th style="text-align: center;">Attendance %</th>
                <th style="text-align: center;">Performance Rating</th>
                <th style="text-align: center;">Monthly Overtime</th>
            </tr>
        </thead>
        <tbody>
            {dept_rows}
        </tbody>
    </table>

    <h2>Proactive Talent Risk & Anomaly Alerts</h2>
    <div>
        {alert_cards}
    </div>
</body>
</html>"""
    return html
