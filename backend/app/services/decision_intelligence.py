"""Domain-adaptive, descriptive decision evidence. No generated code or inferred causation.

Raw sheets remain authoritative. Derived results carry source columns, valid-row counts,
method and limitations. Workspace results never silently join or add unrelated sheets.
"""
import hashlib
import itertools
import json
import re

import numpy as np
import pandas as pd

VERSION = 'decision-brief-1'
MIN_PAIR = 12
MAX_MEASURES = 24
MAX_MATRIX = 8


def label(value):
    text = str(value).replace('_', ' ').strip()
    period = re.fullmatch(r'([A-Za-z]+) (year unspecified|[0-9]{4}) · (recorded attendance|leave)', text)
    if period:
        month, year, metric = period.groups()
        return f'{month} {metric.replace("recorded ", "")}' + (f' ({year})' if year != 'year unspecified' else '')
    return text


def identity(column):
    c = re.sub(r'[^a-z0-9]', '', str(column).lower())
    return c in {'name', 'fullname', 'firstname', 'lastname', 'employeename', 'email', 'phone', 'index', 'sno', 'serialnumber'} or c.endswith(('id', 'code', 'key')) or c.startswith('unnamed')


def domain_for(columns):
    text = ' '.join(columns).lower()
    families = [
        ('Marketing', ('campaign', 'impression', 'click', 'conversion', 'ad spend'), 'Marketing lead'),
        ('IT operations', ('ticket', 'incident', 'resolution', 'latency', 'uptime', 'severity'), 'IT service owner'),
        ('People operations', ('attendance', 'employee', 'leave', 'department', 'salary', 'attrition'), 'HR business partner'),
        ('Sales', ('revenue', 'sales', 'store', 'deal', 'pipeline', 'profit'), 'Sales lead'),
    ]
    scored = [(sum(k in text for k in keys), name, owner) for name, keys, owner in families]
    best = max(scored, key=lambda x: x[0])
    return (best[1], best[2]) if best[0] else ('Business operations', 'Business owner')


def numbers(series):
    # Keep missing and malformed cells unknown; preserve the source's percent scale.
    clean = series.astype('string').str.strip().str.replace(r'[,\$£€%]', '', regex=True)
    return pd.to_numeric(clean, errors='coerce').replace([np.inf, -np.inf], np.nan)


def value(v):
    return round(float(v), 5) if pd.notna(v) and np.isfinite(v) else None


def period_header(c):
    return bool(re.search(r'\d+(?:st|nd|rd|th)?\s*(?:to|-)\s*\d+', c, re.I))


def _sheet_brief(records, columns, source):
    df = pd.DataFrame(records, columns=columns)
    domain, owner = domain_for(columns)
    limitations = []
    findings = []
    numeric = {}
    dimensions = []
    dates = []
    fields = []
    sid = source['sheet_id']

    for c in columns:
        raw = df[c]
        role = 'unresolved'
        if identity(c):
            role = 'identity'
        elif re.search(r'\b(date|timestamp|datetime)\b', label(c), re.I):
            role = 'date'
            # Numeric timestamps and ambiguous numeric date formats require a mapping.
            if not pd.api.types.is_numeric_dtype(raw):
                text = raw.astype('string')
                iso = text.str.match(r'^\d{4}-\d{2}-\d{2}(?:[ T].*)?$', na=False)
                parsed = pd.to_datetime(text.where(iso), errors='coerce', utc=True)
                if parsed.notna().sum() >= 3:
                    dates.append((c, parsed))
                if int(parsed.notna().sum()) != int(raw.notna().sum()):
                    limitations.append(f'{c}: only unambiguous ISO dates were used; other date formats need a mapping.')
        elif re.search(r'department|dept|team|division|region|channel|campaign|category|status|product|store|location|severity|flag|^is[_ ]', c, re.I):
            role = 'dimension'
            if 1 < raw.nunique() <= 200:
                dimensions.append(c)
        else:
            parsed = numbers(raw)
            if parsed.notna().sum() >= max(3, len(df) * .6):
                role = 'period_measure' if period_header(c) else 'measure'
                if re.search(r'final attendance|net attendance', c, re.I):
                    role = 'unresolved_measure'
                    limitations.append(f'{c}: excluded until the business formula is confirmed.')
                elif role == 'measure':
                    numeric[c] = parsed
            elif 1 < raw.nunique() <= min(40, max(2, len(df) // 2)):
                role = 'dimension'
                dimensions.append(c)
        fields.append({'column': c, 'role': role})

    # Wide calendar columns become month totals only for fully observed periods.
    # Source total columns remain separate; no assumption that two totals are additive.
    wide = {}
    for f in fields:
        if f['role'] != 'period_measure':
            continue
        c = f['column']
        match = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:to|-)\s*(\d+)(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(\d{4}))?', c)
        if not match:
            continue
        start, end, month, year = match.groups()
        months = {'january':31,'february':28,'march':31,'april':30,'may':31,'june':30,'july':31,'august':31,'september':30,'october':31,'november':30,'december':31}
        if month.lower() not in months or not 1 <= int(start) <= int(end) <= months[month.lower()]:
            limitations.append(f'{c}: calendar range requires validation.')
            continue
        if domain != 'People operations':
            limitations.append(f'{c}: period values need an aggregation definition before monthly rollup.')
            continue
        kind = 'Leave' if re.search(r'leave|absence|absent', c + ' ' + source['sheet'], re.I) else 'Recorded attendance'
        key = (month.title(), year or 'year unspecified', kind)
        wide.setdefault(key, []).append((int(start), int(end), c))
    for (month, year, kind), periods in wide.items():
        ordered = sorted(periods)
        if any(b[0] <= a[1] for a, b in zip(ordered, ordered[1:])):
            limitations.append(f'{month} {year}: overlapping periods excluded from monthly rollup.')
            continue
        names = [p[2] for p in ordered]
        frame = pd.DataFrame({c: numbers(df[c]) for c in names})
        for start, end, c in ordered:
            frame.loc[(frame[c] < 0) | (frame[c] > end-start+1), c] = np.nan
        metric = f'{month} {year} · {kind.lower()}'
        numeric[metric] = frame.sum(axis=1, min_count=len(names))
        fields.append({'column': metric, 'role': 'derived_period_total', 'source_columns': names})
        limitations.append(f'{metric}: sum of {len(names)} non-overlapping day ranges per complete row; calendar days are not scheduled-workday denominators.')

    # Do not arbitrarily deduplicate: disclose identity repetition and use record-level units.
    for c in columns:
        if identity(c) and re.sub(r'[^a-z]', '', c.lower()).endswith('id'):
            known = df[c].dropna().astype(str)
            duplicates = int(known.duplicated(keep=False).sum())
            if duplicates:
                limitations.append(f'{c}: {duplicates} rows have repeated identifiers. Results describe records, not unique people or entities; confirm record grain before acting.')

    ordered_metrics = sorted(numeric, key=lambda c: (0 if ' · ' in c else 1, columns.index(c) if c in columns else 0))
    if len(ordered_metrics) > MAX_MEASURES:
        limitations.append(f'Analysis bounded to {MAX_MEASURES} of {len(ordered_metrics)} numeric measures; remaining fields remain available in the explorer.')
    # Equivalent source totals and period sums should not produce repeated findings.
    distinct_metrics = []
    for c in ordered_metrics:
        equivalent = next((m for m in distinct_metrics if numeric[c].equals(numeric[m])), None)
        if equivalent is None:
            distinct_metrics.append(c)
        else:
            limitations.append(f'{c}: same values and missingness as {equivalent}; redundant analysis omitted, raw field preserved.')
    metrics = distinct_metrics[:MAX_MEASURES]
    matrix_metrics = [c for c in ordered_metrics if ' · ' not in c][:MAX_MATRIX]
    if len(metrics) > MAX_MATRIX:
        limitations.append(f'Relationship matrix bounded to {len(matrix_metrics)} source measures; derived period totals excluded to avoid redundant correlations.')
    comparisons = []
    trends = []

    def add(kind, title, observation, implication, action, metric, detail, score):
        fid = hashlib.sha256(f'{sid}:{kind}:{metric}:{title}'.encode()).hexdigest()[:12]
        findings.append({'id': fid, 'kind': kind, 'title': title, 'observation': observation,
                         'implication': implication, 'action': action, 'owner': owner,
                         'metric': metric, 'source': source, 'method': detail['method'],
                         'detail': detail, 'priority_score': round(score, 4),
                         'evidence_status': 'Descriptive evidence', 'review': 'Proposed: review at the next operating meeting'})

    for c in metrics:
        s = numeric[c]
        valid = s.dropna()
        if len(valid) < 3:
            continue
        missing = int(s.isna().sum())
        if missing:
            add('quality', f'{label(c)} has incomplete coverage', f'{missing} of {len(df)} records have missing or invalid values.',
                'Missing observations can change comparisons; unknown values are excluded, never treated as zero.',
                f'Confirm missing {label(c)} entries with the source owner before setting targets.', c,
                {'method': 'Finite numeric values only; missing and malformed entries excluded.', 'used_rows': len(valid), 'total_rows': len(df)}, missing / len(df))
        for dim in dimensions[:3]:
            temp = pd.DataFrame({'group': df[dim].fillna('(missing)').astype(str), 'v': s})
            groups = []
            baseline = value(valid.mean())
            for group, part in temp.groupby('group', sort=True):
                v = part.v.dropna()
                groups.append({'group': group, 'value': value(v.mean()), 'median': value(v.median()), 'used_rows': len(v),
                               'missing_rows': int(part.v.isna().sum()), 'gap': value(v.mean()-baseline), 'small_sample': len(v)<5})
            groups.sort(key=lambda g: (g['value'] is None, g['value'] if g['value'] is not None else 0, g['group']))
            detail = {'method': 'Unweighted mean of valid source records by group; gap = group mean minus scoped record mean. No performance direction assumed.',
                      'dimension': dim, 'groups': groups, 'baseline': baseline, 'used_rows': len(valid), 'total_rows': len(df)}
            comparisons.append({'metric': c, **detail})
            eligible = [g for g in groups if g['used_rows'] >= 5 and g['group'] != '(missing)']
            if len(eligible) < 2 or valid.std() == 0:
                continue
            for extreme in (eligible[0], eligible[-1]):
                effect = abs(extreme['gap']) / float(valid.std())
                if effect < .35:
                    continue
                direction = 'above' if extreme['gap'] > 0 else 'below'
                add('comparison', f'{extreme["group"]}: {label(c)} is {direction} baseline',
                    f'{extreme["value"]:,.2f} versus {baseline:,.2f} across this sheet ({abs(extreme["gap"]):,.2f} {direction}); {extreme["used_rows"]} valid records in the group.',
                    'This identifies a segment to investigate. Different workload, exposure or record mix may explain the gap; it is not an overall performance ranking.',
                    f'Review {label(c)} with the {extreme["group"]} owner and compare like-for-like workload before choosing an intervention.', c, {**detail, 'focus_group': extreme['group']}, min(effect, 3))
        if dates and ' · ' not in c:
            date_col, parsed = dates[0]
            temp = pd.DataFrame({'month': parsed.dt.strftime('%Y-%m'), 'v': s})
            points = [{'period': str(m), 'value': value(g.v.mean()), 'used_rows': int(g.v.count())}
                      for m, g in temp.dropna(subset=['month']).groupby('month') if g.v.count()]
            trends.append({'metric': c, 'date_column': date_col, 'points': points, 'method': 'Monthly unweighted mean per valid source record; not a monthly total.', 'coverage_note': 'First/last months may be partial; changes in record mix or exposure may affect means.'})
            if len(points) >= 2 and min(p['used_rows'] for p in points[-2:]) >= 5:
                prev, last = points[-2:]
                change = last['value']-prev['value']
                if change and valid.std() > 0:
                    add('movement', f'{label(c)} changed in {last["period"]}',
                        f'Mean per record moved from {prev["value"]:,.2f} ({prev["period"]}) to {last["value"]:,.2f} ({last["period"]}).',
                        'Check coverage and group composition before treating this as a sustained change.',
                        f'Review the latest records with {owner.lower()} and validate comparable reporting windows.', c,
                        {'method': trends[-1]['method'], 'points': points, 'used_rows': sum(p['used_rows'] for p in points)}, min(abs(change)/float(valid.std()), 2))

    pairs = []
    for a, b in itertools.combinations(matrix_metrics, 2):
        pair = pd.DataFrame({'a': numeric[a], 'b': numeric[b]}).dropna()
        exclusion = None
        # Avoid known total/component accounting identities, not just identical labels.
        tokens_a = set(re.findall(r'[a-z]+', a.lower())) - {'total', 'average', 'mean'}
        tokens_b = set(re.findall(r'[a-z]+', b.lower())) - {'total', 'average', 'mean'}
        if any(re.search(r'\b(net|final|balance)\b', c, re.I) for c in (a,b)) or (any('total' in c.lower() for c in (a,b)) and tokens_a & tokens_b):
            exclusion = 'Total/component relationship may be mechanical; formula confirmation required.'
        elif len(pair) < MIN_PAIR or pair.a.nunique() < 3 or pair.b.nunique() < 3:
            exclusion = f'Needs at least {MIN_PAIR} paired records and three distinct values per measure.'
        rho = None if exclusion else value(pair.a.rank().corr(pair.b.rank()))
        entry = {'x': a, 'y': b, 'coefficient': rho, 'paired_rows': len(pair), 'excluded_reason': exclusion}
        within = []
        if rho is not None and dimensions:
            dimension = dimensions[0]
            scoped = pair.assign(group=df.loc[pair.index, dimension])
            for group, part in scoped.groupby('group'):
                if len(part) >= MIN_PAIR and part.a.nunique() >= 3 and part.b.nunique() >= 3:
                    within.append({'group': str(group), 'coefficient': value(part.a.rank().corr(part.b.rank())), 'paired_rows': len(part)})
            entry['within_dimension'] = dimension
            entry['within_groups'] = within
        pairs.append(entry)
        reversal = len(within) >= 2 and abs(rho or 0) >= .4 and all(p['coefficient'] is not None and p['coefficient'] * rho < 0 for p in within)
        if reversal:
            add('association', f'Group mix reverses the {label(a)} / {label(b)} relationship',
                f'Overall rank correlation is {rho:+.2f}, but its sign reverses in all {len(within)} eligible {label(dimensions[0])} groups.',
                'The pooled relationship can mislead a decision. Group composition may explain the apparent pattern; no causal explanation is established.',
                f'Compare {label(a)} and {label(b)} within {label(dimensions[0])} before setting a shared target.', f'{a} / {b}',
                {'method': 'Compare pooled Spearman coefficient with within-group coefficients; each group requires at least 12 paired records. Descriptive sign reversal only.', 'coefficient': rho, 'paired_rows': len(pair), 'within_groups': within, 'x': a, 'y': b}, 2.5)
        elif rho is not None and abs(rho) >= .65:
            add('association', f'{label(a)} and {label(b)} move together',
                f'Spearman rank correlation {rho:+.2f} across {len(pair)} paired records.',
                'An exploratory association, not a cause or a validated predictor. Shared trends, group mix and multiple comparisons can create this pattern.',
                f'Check this relationship within comparable segments before testing a change to {label(a)} or {label(b)}.', f'{a} / {b}',
                {'method': 'Pearson correlation of average ranks on pairwise complete observations (Spearman). No significance or causal claim.', 'paired_rows': len(pair), 'coefficient': rho, 'x': a, 'y': b}, abs(rho)*.8)

    if not dates:
        limitations.append('No supported row-level date column. Historical change is unavailable; period-header rollups, when present, describe supplied periods only.')
    if len(dimensions) > 3:
        limitations.append(f'Group comparisons cover the first 3 of {len(dimensions)} eligible dimensions.')
    if not metrics:
        limitations.append('No sufficiently populated numeric measures could be resolved. Inspect field roles and supply measure definitions; no synthetic KPIs were created.')
    limitations.append('Units remain in the source scale. Percentages are not converted; group means are not exposure-adjusted rates. No automatic cross-sheet joins are applied.')
    # Select diverse business questions instead of repeating one chart for every group.
    findings.sort(key=lambda f: (-f['priority_score'], f['id']))
    selected = []
    seen = set()
    for f in findings:
        key = (f['kind'], f['metric'], f['title'] if f['kind'] == 'comparison' else '')
        if key not in seen:
            selected.append(f)
            seen.add(key)
    return {'source': source, 'domain': domain, 'owner': owner, 'row_count': len(df), 'fields': fields,
            'findings': selected[:8], 'comparisons': comparisons, 'trends': trends,
            'matrix': {'metrics': matrix_metrics, 'pairs': pairs, 'minimum_pairs': MIN_PAIR},
            'limitations': list(dict.fromkeys(limitations)), 'measures_analyzed': len(metrics)}


def build_decision_brief(conn, sheet_id=None, sheet_ids=None):
    sql = 'SELECT s.id,s.name,s.columns_json,d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id'
    args = ()
    if sheet_ids is not None:
        ids = sorted(set(int(i) for i in sheet_ids))
        sql += (' WHERE s.id IN (' + ','.join('?' for _ in ids) + ')') if ids else ' WHERE 0'
        args = tuple(ids)
    elif sheet_id is not None:
        sql += ' WHERE s.id=?'
        args = (sheet_id,)
    sheets = conn.execute(sql + ' ORDER BY s.id', args).fetchall()
    profiles = []
    digest = hashlib.sha256(VERSION.encode())
    for sheet in sheets:
        records = [json.loads(r[0]) for r in conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],))]
        cols = json.loads(sheet['columns_json'])
        digest.update(json.dumps([sheet['id'], sheet['name'], cols, records], sort_keys=True, ensure_ascii=False).encode())
        source = {'sheet_id': sheet['id'], 'sheet': sheet['name'], 'file': sheet['original_name']}
        profiles.append(_sheet_brief(records, cols, source))
    findings = sorted([f for p in profiles for f in p['findings']], key=lambda f: (-f['priority_score'], f['id']))
    # One initial finding per sheet before further ranked findings, so large sheets do not crowd out others.
    first = [p['findings'][0] for p in profiles if p['findings']]
    chosen = []
    signatures = set()
    for f in first + [f for f in findings if f not in first]:
        signature = (f['kind'], f['title'], f['observation'])
        if signature not in signatures:
            chosen.append(f)
            signatures.add(signature)
    # Repeated uploads stay distinct sources; only identical headline claims are collapsed.

    return {'version': VERSION, 'snapshot': digest.hexdigest()[:16], 'sheet_id': sheet_id,
            'profiles': profiles, 'findings': chosen[:6], 'finding_count': len(findings),
            'prioritization': 'Descriptive effect size with source diversity; not financial impact or policy risk.',
            'ai_status': 'Statistical analysis · AI prioritization available',
            'empty': not profiles}
