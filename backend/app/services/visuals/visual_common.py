"""Common utilities, formatting palettes, and insight generators for visual intelligence."""

import re

PALETTE = [
    '#10b981', '#6366f1', '#06b6d4', '#f59e0b', '#ec4899',
    '#8b5cf6', '#14b8a6', '#f97316', '#3b82f6', '#84cc16'
]


def is_name_or_text_column(col_name: str) -> bool:
    """Detects if a column is a person name, notes, comments, or free-form text."""
    c = str(col_name).lower().replace('_', '').replace(' ', '')
    if any(t in c for t in ('name', 'employeename', 'candidate', 'person', 'note', 'comment', 'description', 'text', 'email', 'url', 'address')):
        return True
    return False


def clean_file_label(filename: str) -> str:
    """Formats file names into clean badges."""
    s = str(filename)
    if s.lower().endswith('.csv'):
        s = s[:-4]
    elif s.lower().endswith('.xlsx') or s.lower().endswith('.xls'):
        s = s.rsplit('.', 1)[0]
    if len(s) > 32:
        return s[:29] + '…'
    return s


def generate_comparative_insight(cat_col: str, m1: str, m2: str, u1: str, u2: str, items: list[dict]) -> str:
    """Generates an executive AI insight interpreting a cross-sheet comparative grouped bar chart."""
    if not items:
        return f"Cross-sheet comparative analysis between **{m1}** and **{m2}** across departments."

    top_m1 = max(items, key=lambda x: x.get('val1', 0))
    top_m2 = max(items, key=lambda x: x.get('val2', 0))

    is_absent = any(k in m2.lower() for k in ('absent', 'leave', 'sick'))
    is_perf = any(k in m1.lower() for k in ('performance', 'rating', 'score'))
    is_ot = any(k in m1.lower() for k in ('overtime', 'hours'))

    if is_perf and is_absent:
        return (
            f"**Cross-Sheet Impact**: **{top_m1['label']}** benchmarks peak performance at "
            f"**{top_m1['val1']} {u1}** alongside **{top_m1['val2']} {u2}** absent. Conversely, **{top_m2['label']}** "
            f"logs the highest absence impact (**{top_m2['val2']} {u2}**), correlating with performance at "
            f"**{top_m2['val1']} {u1}**. Target leadership coaching on high-absence clusters to protect department velocity."
        )
    elif is_ot and is_absent:
        return (
            f"**Workload vs Absenteeism**: **{top_m1['label']}** carries peak overtime load at "
            f"**{top_m1['val1']} {u1}** with **{top_m1['val2']} {u2}** absent. Elevated overtime can signal compensatory "
            f"workload covering for absent teammates. Evaluate staffing balance to avert operational burnout."
        )

    return (
        f"**Cross-Sheet Synthesis**: Across {len(items)} {cat_col.lower()}s, **{top_m1['label']}** records peak "
        f"**{m1}** of **{top_m1['val1']} {u1}** (paired with {top_m1['val2']} {u2} {m2}), while **{top_m2['label']}** "
        f"shows the highest **{m2}** (**{top_m2['val2']} {u2}**). Leadership should balance operational priorities across both vectors."
    )


def extract_sheet_temporal_profile(sheet_rows: list[dict]) -> tuple[list[str], list[float], str] | None:
    """Detects if a sheet has Date + multi-person check-ins (like Kaggle attendance) and aggregates daily metrics."""
    if not sheet_rows:
        return None

    sample = sheet_rows[0]
    date_key = None
    for k in sample.keys():
        if str(k).lower().replace('_', '').replace(' ', '') in ('date', 'timestamp', 'datetime', 'day'):
            date_key = k
            break

    if not date_key:
        return None

    person_keys = [k for k in sample.keys() if k.startswith('Person_') or k.startswith('Emp_') or k.startswith('Staff_')]
    if len(person_keys) < 5:
        return None

    dates = []
    daily_values = []

    # Calculate average daily hours from timestamps e.g. "08:43-16:42"
    for r in sheet_rows:
        dt = r.get(date_key)
        if not dt:
            continue
        durations = []
        for pk in person_keys:
            val = str(r.get(pk, '')).strip()
            if val and val.lower() not in ('', 'none', 'absent', 'nan'):
                m = re.match(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', val)
                if m:
                    h1, m1, h2, m2 = map(int, m.groups())
                    hrs = (h2 * 60 + m2 - (h1 * 60 + m1)) / 60.0
                    if 0 < hrs < 24:
                        durations.append(hrs)
        if durations:
            dates.append(str(dt))
            daily_values.append(round(sum(durations) / len(durations), 2))

    if len(daily_values) >= 10:
        return dates, daily_values, 'hrs'

    return None
