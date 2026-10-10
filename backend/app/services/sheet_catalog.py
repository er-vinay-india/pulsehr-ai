"""Complete, source-preserving sheets and explainable cross-sheet relationships."""
import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
import numpy as np
import pandas as pd

from ..core import config
from ..db.database import get_connection
from .display_formatters import format_display_label, category_display_labels

logger = logging.getLogger(__name__)
ALIASES = {
    'employeeid': 'employee_id', 'empid': 'employee_id', 'employeecode': 'employee_id', 'empcode': 'employee_id',
    'employeename': 'employee_name', 'staffname': 'employee_name', 'fullname': 'employee_name',
    'department': 'department', 'dept': 'department', 'departmentname': 'department',
    'departmentid': 'department_id', 'deptid': 'department_id',
    'email': 'email', 'emailaddress': 'email', 'workemail': 'email',
}


def canonical(column):
    key = re.sub(r'[^\w]', '', column.casefold()).replace('_', '')
    return ALIASES.get(key, key)


NULL_STRINGS = {'', 'none', 'null', 'nan', 'na', 'n/a', '-', 'undefined', 'nil', '#n/a', '#null!', 'n.a.', 'n.a', 'nm'}


def is_null_value(value):
    if value is None:
        return True
    s = str(value).strip().casefold()
    return s in NULL_STRINGS


def value_key(value):
    # Preserve punctuation and leading zeroes; do not turn 001 into 1.
    if value is None or is_null_value(value):
        return ''
    return ' '.join(str(value).strip().casefold().split())


def model_embeddings(texts):
    """One embedding space only. An offline model never produces fake vectors."""
    if not texts:
        return []
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(f'{config.OLLAMA_BASE_URL}/api/embed', json={
                'model': config.OLLAMA_EMBED_MODEL, 'input': texts, 'truncate': True})
            response.raise_for_status()
            vectors = response.json()['embeddings']
            if len(vectors) == len(texts) and all(len(v) == config.EMBEDDING_DIM and all(math.isfinite(x) for x in v) for v in vectors):
                return vectors
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        logger.info('Embeddings unavailable; exact links and keyword search remain active')
    return []


def sniff_delimiter_and_header(sample_text: str, default_sep: str = ',') -> tuple[str, int]:
    """Sniffs delimiter and detects any leading preamble / metadata rows before table header."""
    lines = [line for line in sample_text.splitlines() if line.strip()]
    if not lines:
        return default_sep, 0

    # 1. Delimiter Sniffing
    detected_sep = default_sep
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_text[:16384], delimiters=[',', ';', '\t', '|'])
        if dialect and dialect.delimiter:
            detected_sep = dialect.delimiter
    except Exception:
        # Fallback heuristic: count common delimiters in first lines
        delims = [',', ';', '\t', '|']
        counts = {d: sum(line.count(d) for line in lines[:10]) for d in delims}
        max_delim = max(counts, key=counts.get)
        if counts[max_delim] > 0:
            detected_sep = max_delim

    # 2. Preamble / Title Row Detection
    # If the first 1-3 lines have very few delimiters compared to body rows, skip them
    header_idx = 0
    if len(lines) >= 3:
        delim_counts = [line.count(detected_sep) for line in lines[:10]]
        max_cols = max(delim_counts)
        if max_cols >= 2:
            for idx, count in enumerate(delim_counts):
                if count >= max_cols * 0.7:
                    header_idx = idx
                    break

    return detected_sep, header_idx


def read_sheets(path, *, prune_empty=True):
    path = Path(path) if isinstance(path, str) else path
    suffix = path.suffix.lower()
    if suffix in ('.csv', '.tsv', '.txt'):
        frames = None
        if prune_empty:
            try:
                from .adaptive_table_reconstruction import AdaptiveTableReconstructionEngine
                recon_res = AdaptiveTableReconstructionEngine.reconstruct(path)
                df = recon_res.reconstructed_df
                df.attrs['reconstruction_metadata'] = {
                    'complexity': recon_res.complexity.model_dump(),
                    'sentinels': [s.model_dump() for s in recon_res.sentinels],
                    'provenance': [p.model_dump() for p in recon_res.provenance],
                    'metadata_extracted': recon_res.metadata_extracted,
                }
                frames = {'Sheet1': df}
            except Exception as exc:
                logger.warning(f"AdaptiveTableReconstructionEngine fallback on {path}: {exc}")
                frames = None

        if frames is None:
            default_sep = '\t' if suffix == '.tsv' else ','
            for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'latin1'):
                try:
                    with open(path, 'r', encoding=encoding, errors='replace') as f:
                        sample = f.read(65536)
                    sep, skip = sniff_delimiter_and_header(sample, default_sep=default_sep)
                    df = pd.read_csv(
                        path,
                        sep=sep,
                        skiprows=skip if (skip > 0 and prune_empty) else None,
                        dtype=str,
                        encoding=encoding,
                        keep_default_na=False,
                        skip_blank_lines=prune_empty,
                    )
                    frames = {'Sheet1': df}
                    break
                except (UnicodeDecodeError, Exception):
                    continue
            if frames is None:
                frames = {'Sheet1': pd.read_csv(path, dtype=str, encoding='latin1', keep_default_na=False, skip_blank_lines=prune_empty)}
    elif suffix in ('.xlsx', '.xls'):
        frames = None
        if prune_empty:
            try:
                from .adaptive_table_reconstruction import AdaptiveTableReconstructionEngine
                engine = 'xlrd' if suffix == '.xls' else None
                excel_book = pd.ExcelFile(path, engine=engine) if engine else pd.ExcelFile(path)
                frames = {}
                for name in excel_book.sheet_names:
                    recon_res = AdaptiveTableReconstructionEngine.reconstruct(path, sheet_name=name)
                    df = recon_res.reconstructed_df
                    df.attrs['reconstruction_metadata'] = {
                        'complexity': recon_res.complexity.model_dump(),
                        'sentinels': [s.model_dump() for s in recon_res.sentinels],
                        'provenance': [p.model_dump() for p in recon_res.provenance],
                        'metadata_extracted': recon_res.metadata_extracted,
                    }
                    frames[name] = df
            except Exception as exc:
                logger.warning(f"AdaptiveTableReconstructionEngine Excel fallback on {path}: {exc}")
                frames = None

        if frames is None:
            if suffix == '.xls':
                try:
                    with pd.ExcelFile(path, engine='xlrd') as book:
                        frames = {name: pd.read_excel(book, sheet_name=name, dtype=str, keep_default_na=False) for name in book.sheet_names}
                except ImportError:
                    raise ValueError("Missing 'xlrd' library required for older .xls spreadsheets. Please install xlrd>=2.0.1.")
                except Exception as e:
                    raise ValueError(f"Failed to parse Excel .xls spreadsheet: {e}")
            else:
                try:
                    with pd.ExcelFile(path) as book:
                        frames = {name: pd.read_excel(book, sheet_name=name, dtype=str, keep_default_na=False) for name in book.sheet_names}
                except Exception as e:
                    raise ValueError(f"Failed to parse Excel spreadsheet: {e}")
    if sum(len(f) for f in frames.values()) > 20000:
        raise ValueError('Upload at most 20,000 rows per file. Split larger files before uploading.')

    # Data-quality audits need original empty fields/records before ingestion
    # removes empty columns. Ordinary ingestion keeps its existing behavior.
    if not prune_empty:
        return frames

    pruned_frames = {}
    for sheet_name, frame in frames.items():
        frame.columns = [str(c).strip() for c in frame.columns]
        # Prune completely empty columns and trailing unnamed blank columns
        valid_cols = []
        for col in frame.columns:
            non_empty = sum(1 for val in frame[col] if not is_null_value(val))
            is_unnamed_empty = str(col).lower().startswith('unnamed:') and non_empty == 0
            if non_empty == 0 or is_unnamed_empty:
                logger.info(f"Pruned completely null/empty column '{col}' from sheet '{sheet_name}'")
                continue
            valid_cols.append(col)

        # If all columns were somehow empty, retain original columns to avoid empty DataFrame crash
        retained_frame = frame[valid_cols] if valid_cols else frame
        if len(retained_frame.columns) > 200 or retained_frame.columns.duplicated().any() or any(not c for c in retained_frame.columns):
            raise ValueError('Use unique, nonempty column names and at most 200 columns per sheet.')
        pruned_frames[sheet_name] = retained_frame

    return pruned_frames


def numeric_values(raw, column):
    """Parses numeric series, recognizing percentages, currencies, thousands commas, and accounting negatives."""
    values = raw.replace(r'^\s*$', pd.NA, regex=True)
    present = values.dropna().astype(str).str.strip()
    unit = None
    if not len(present):
        return pd.to_numeric(values, errors='coerce'), None

    # Check for percentage: e.g. "18.5%", "+18.5%", "-18.5%"
    if present.str.fullmatch(r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*%').all():
        cleaned = values.astype('string').str.strip().str.replace(',', '', regex=False).str.rstrip('%').str.strip()
        return pd.to_numeric(cleaned, errors='coerce'), '%'

    # Check for rating fraction: e.g. "4/5", "85/100"
    if 'rating' in canonical(column) and len(present):
        fractions = present.str.extract(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*/\s*(\d+(?:\.\d*)?)$')
        if fractions.notna().all().all() and fractions[1].nunique() == 1:
            values = values.astype('string').str.split('/').str[0].str.strip()
            unit = 'out of ' + fractions[1].iloc[0]
            return pd.to_numeric(values, errors='coerce'), unit

    # Check for currencies: e.g. "$1,250.00", "€450", "£90.50", "($100.00)"
    curr_match = present.str.extract(r'^[+-]?\s*([$€£¥₹]|USD|EUR|GBP|INR)?\s*\(?\s*([$€£¥₹]|USD|EUR|GBP|INR)?\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*\)?\s*([$€£¥₹]|USD|EUR|GBP|INR)?$')
    currencies_found = [c for c in (curr_match[0].dropna().tolist() + curr_match[1].dropna().tolist() + curr_match[3].dropna().tolist()) if c]
    if currencies_found:
        most_common_curr = max(set(currencies_found), key=currencies_found.count).strip()
        cleaned_curr = values.astype('string').str.strip()
        is_acct_neg = cleaned_curr.str.match(r'^\s*\(.*\)\s*$')
        cleaned_curr = cleaned_curr.str.replace(r'[$€£¥₹]|USD|EUR|GBP|INR', '', regex=True)
        cleaned_curr = cleaned_curr.str.replace(',', '', regex=False)
        cleaned_curr = cleaned_curr.str.replace(r'[()]', '', regex=True).str.strip()
        num_series = pd.to_numeric(cleaned_curr, errors='coerce')
        if num_series.notna().all():
            num_series = num_series.where(~is_acct_neg, -num_series)
            return num_series, most_common_curr

    # Check for thousands commas without currency: e.g. "1,250.00", "10,000"
    if present.str.fullmatch(r'^[+-]?(?:\d{1,3}(?:,\d{3})+)(?:\.\d+)?$').all():
        cleaned = values.astype('string').str.replace(',', '', regex=False).str.strip()
        return pd.to_numeric(cleaned, errors='coerce'), None

    # Check for accounting negative without currency: e.g. "(1,250.00)", "(50)"
    if present.str.fullmatch(r'^\s*\(\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*\)\s*$').all():
        cleaned = values.astype('string').str.replace(',', '', regex=False).str.replace(r'[()]', '', regex=True).str.strip()
        num_series = -pd.to_numeric(cleaned, errors='coerce')
        return num_series, None

    return pd.to_numeric(values, errors='coerce'), unit


def compute_decision_hints(profiles, records):
    """Derives ingestion-time decision hints regarding optimal visual presentation."""
    total_records = len(records)
    total_cols = len(profiles)

    # Clean numeric measures with < 40% missing
    primary_metrics = [
        p['column'] for p in profiles
        if p.get('numeric') and p.get('null_percentage', 0) < 40 and not p.get('is_mostly_null')
    ]

    # Clean categorical dimensions with 2-50 unique values and < 40% missing
    primary_dimensions = [
        p['column'] for p in profiles
        if not p.get('numeric') and 2 <= p.get('distinct', 0) <= 50 and p.get('null_percentage', 0) < 40
    ]

    # Timeline presence check
    has_timeline = any(
        re.search(r'(date|timestamp|datetime|month|year|period)', p['canonical'], re.I) and p.get('null_percentage', 0) < 50
        for p in profiles
    )

    # Overall Data Quality Score (0 to 100)
    avg_null_pct = sum(p.get('null_percentage', 0) for p in profiles) / max(1, total_cols)
    data_quality_score = max(0, min(100, round(100 - avg_null_pct)))

    # Recommended visual components based on empirical data shape
    recommended_components = ['signal_card']
    if data_quality_score >= 50:
        recommended_components.append('gauge')
    if primary_metrics and primary_dimensions:
        recommended_components.append('comparison_bar')
    if has_timeline and primary_metrics:
        recommended_components.append('area_trend')
    if primary_dimensions and any(p.get('distinct', 0) <= 6 for p in profiles if p['column'] in primary_dimensions):
        recommended_components.append('donut_breakdown')
    if len(primary_metrics) >= 2:
        recommended_components.append('heatmap')

    return {
        'recommended_components': recommended_components,
        'primary_metrics': primary_metrics[:6],
        'primary_dimensions': primary_dimensions[:5],
        'has_timeline': has_timeline,
        'data_quality_score': data_quality_score,
        'total_records': total_records,
        'clean_column_count': len([p for p in profiles if not p.get('is_mostly_null')])
    }


def infer_hierarchical_headers(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Infers hierarchical header geometry (1, 2, or 3-tier headers) while preserving
    exact source fidelity. Maps raw multi-level headers (e.g. 'Revenue' -> 'Q1' -> 'Actual')
    to normalized snake_case columns (e.g. 'revenue_q1_actual') and returns a structured geometry
    mapping so the original multi-level hierarchy is 100% recoverable.
    
    Also distinguishes outer margin padding from interior blank rows/separators.
    """
    if frame is None or len(frame.columns) == 0:
        return frame, {"has_hierarchical_header": False, "levels_count": 1, "mappings": {}}

    # Case 1: MultiIndex columns (loaded via Excel multi-header or tuple columns)
    if isinstance(frame.columns, pd.MultiIndex):
        n_levels = frame.columns.nlevels
        mappings = {}
        new_cols = []
        for idx, col_tuple in enumerate(frame.columns):
            levels = [str(x).strip() for x in col_tuple if str(x).strip() and not str(x).lower().startswith('unnamed:')]
            if not levels:
                levels = [f"col_{idx}"]
            norm_name = re.sub(r'[^a-zA-Z0-9]+', '_', "_".join(levels)).strip('_').lower()
            if not norm_name:
                norm_name = f"col_{idx}"
            display_hierarchy = " → ".join(levels)
            mappings[norm_name] = {
                "levels": levels,
                "display_hierarchy": display_hierarchy,
                "raw_header_text": display_hierarchy,
                "col_index": idx
            }
            new_cols.append(norm_name)
        new_frame = frame.copy()
        new_frame.columns = new_cols
        return new_frame, {
            "has_hierarchical_header": True,
            "levels_count": n_levels,
            "mappings": mappings,
            "table_regions": [{"region_id": "table_1", "start_row": 0, "end_row": len(new_frame)}]
        }

    # Case 2: Inspect top rows for multi-tier header patterns
    if len(frame) >= 3:
        is_range_cols = all(isinstance(c, (int, np.integer)) for c in frame.columns)
        has_unnamed_in_cols = any(str(c).lower().startswith('unnamed:') for c in frame.columns)

        row0 = frame.iloc[0].astype(str).str.strip()
        row0_non_empty = sum(1 for v in row0 if v and not is_null_value(v))
        row0_is_text = all(not re.match(r'^-?\d+(?:\.\d+)?$', v) for v in row0 if v and not is_null_value(v))

        row1 = frame.iloc[1].astype(str).str.strip()
        row1_non_empty = sum(1 for v in row1 if v and not is_null_value(v))
        row1_is_text = all(not re.match(r'^-?\d+(?:\.\d+)?$', v) for v in row1 if v and not is_null_value(v))

        # Subcase 2a: Integer range columns and first 2 rows are stacked text headers
        if is_range_cols and row0_is_text and row1_is_text and row0_non_empty >= 2 and row1_non_empty >= 2:
            top_level = []
            curr_top = ""
            for v in row0:
                v_str = str(v).strip()
                if v_str and not is_null_value(v_str):
                    curr_top = v_str
                top_level.append(curr_top or "")
            
            mappings = {}
            new_cols = []
            for idx in range(len(frame.columns)):
                lvl0 = top_level[idx]
                lvl1 = str(row1.iloc[idx]).strip() if not is_null_value(row1.iloc[idx]) else ""
                parts = [p for p in [lvl0, lvl1] if p] or [f"col_{idx}"]
                norm_name = re.sub(r'[^a-zA-Z0-9]+', '_', "_".join(parts)).strip('_').lower() or f"col_{idx}"
                base_name = norm_name
                uniq_count = 1
                while norm_name in new_cols:
                    uniq_count += 1
                    norm_name = f"{base_name}_{uniq_count}"
                display_hierarchy = " → ".join(parts)
                mappings[norm_name] = {
                    "levels": parts,
                    "display_hierarchy": display_hierarchy,
                    "raw_header_text": display_hierarchy,
                    "col_index": idx
                }
                new_cols.append(norm_name)
            new_frame = frame.iloc[2:].reset_index(drop=True).copy()
            new_frame.columns = new_cols
            return new_frame, {
                "has_hierarchical_header": True,
                "levels_count": 2,
                "mappings": mappings,
                "table_regions": [{"region_id": "table_1", "start_row": 0, "end_row": len(new_frame)}]
            }

        # Subcase 2b: frame.columns has top level headers and row 0 has sub-headers
        if row0_is_text and (has_unnamed_in_cols or (row0_non_empty >= 2 and row0_non_empty < len(frame.columns) * 0.95)):
            is_3_tier = False
            if len(frame) >= 4 and row1_is_text and row1_non_empty >= 2:
                row2 = frame.iloc[2].astype(str).str.strip()
                row2_is_text = all(not re.match(r'^-?\d+(?:\.\d+)?$', v) for v in row2 if v and not is_null_value(v))
                if row2_is_text and sum(1 for v in row2 if v and not is_null_value(v)) >= 2:
                    is_3_tier = True

            # Forward-fill top-level headers across horizontal spans
            top_level = []
            curr_top = ""
            for c in frame.columns:
                c_str = str(c).strip()
                if c_str and not c_str.lower().startswith('unnamed:'):
                    curr_top = c_str
                top_level.append(curr_top or "")

            mappings = {}
            new_cols = []
            n_levels = 3 if is_3_tier else 2
            
            for idx in range(len(frame.columns)):
                lvl0 = top_level[idx]
                lvl1 = str(row0.iloc[idx]).strip() if not is_null_value(row0.iloc[idx]) else ""
                lvl2 = str(frame.iloc[1].iloc[idx]).strip() if is_3_tier and not is_null_value(frame.iloc[1].iloc[idx]) else ""
                
                parts = [p for p in ([lvl0, lvl1, lvl2] if is_3_tier else [lvl0, lvl1]) if p]
                if not parts:
                    parts = [f"col_{idx}"]
                
                norm_name = re.sub(r'[^a-zA-Z0-9]+', '_', "_".join(parts)).strip('_').lower()
                if not norm_name:
                    norm_name = f"col_{idx}"
                base_name = norm_name
                uniq_count = 1
                while norm_name in new_cols:
                    uniq_count += 1
                    norm_name = f"{base_name}_{uniq_count}"
                    
                display_hierarchy = " → ".join(parts)
                mappings[norm_name] = {
                    "levels": parts,
                    "display_hierarchy": display_hierarchy,
                    "raw_header_text": display_hierarchy,
                    "col_index": idx
                }
                new_cols.append(norm_name)

            slice_start = 2 if is_3_tier else 1
            new_frame = frame.iloc[slice_start:].reset_index(drop=True).copy()
            new_frame.columns = new_cols
            return new_frame, {
                "has_hierarchical_header": True,
                "levels_count": n_levels,
                "mappings": mappings,
                "table_regions": [{"region_id": "table_1", "start_row": 0, "end_row": len(new_frame)}]
            }

    # Case 3: Flat single-level header
    mappings = {}
    for idx, c in enumerate(frame.columns):
        c_str = str(c).strip()
        mappings[c_str] = {
            "levels": [c_str],
            "display_hierarchy": c_str,
            "raw_header_text": c_str,
            "col_index": idx
        }
    return frame, {
        "has_hierarchical_header": False,
        "levels_count": 1,
        "mappings": mappings,
        "table_regions": [{"region_id": "table_1", "start_row": 0, "end_row": len(frame)}]
    }


def decompose_header_semantics(
    column: str,
    header_mapping: Optional[Dict[str, Any]] = None,
    unit: Optional[str] = None
) -> Dict[str, Any]:
    """Decomposes a table header into structured semantic sub-components:
    - physical_header_path: original raw multi-tier header path or column name
    - normalized_display_label: clean, human-readable display label
    - metric_identity: core metric/dimension name without dates, units, or status qualifiers
    - qualifiers: operational or status modifiers (e.g. 'Already approved', 'Annual Average', 'Actual')
    - dates: temporal expressions or calendar dates extracted from header text
    - units: physical or financial units of measure
    """
    if header_mapping and header_mapping.get('levels'):
        physical_path = [str(lvl).strip() for lvl in header_mapping['levels'] if str(lvl).strip()]
    elif header_mapping and header_mapping.get('raw_header_text'):
        physical_path = [str(header_mapping['raw_header_text']).strip()]
    else:
        physical_path = [str(column).strip()]

    full_text = ' '.join(physical_path) if physical_path else str(column).strip()

    # Dates: match compound dates first, then isolated years / quarters / months
    date_patterns = [
        r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b',
        r'\b\d{4}[./-]\d{1,2}[./-]\d{1,2}\b',
        r'\b(?:19|20)\d{2}\b',
        r'\b(?:Q[1-4]|H[1-2])\b',
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember))\b'
    ]
    dates = []
    for pat in date_patterns:
        for m in re.finditer(pat, full_text, flags=re.IGNORECASE):
            val = m.group(0).strip()
            if val and not any(val in d for d in dates):
                dates.append(val)

    # Units
    units = []
    if unit:
        units.append(str(unit).strip())
    unit_regex = r'(?:µg/m³|ug/m3|mg/m3|mg/l|ppm|ppb|f[t-]?e|%|\$|€|£|₹|USD|EUR|GBP|INR)'
    for m in re.finditer(unit_regex, full_text, flags=re.IGNORECASE):
        u = m.group(0).strip()
        if u and not any(u.lower() == existing.lower() for existing in units):
            units.append(u)

    # Qualifiers sorted by length descending to match longest phrases first
    qualifier_candidates = sorted([
        'already approved on', 'already approved', 'approved on', 'approved',
        'annual average', 'monthly average', 'daily average',
        'prior year', 'year to date', 'quarter to date',
        'target', 'actual', 'budget', 'forecast', 'provisional',
        'preliminary', 'revised', 'baseline', 'variance'
    ], key=len, reverse=True)

    qualifiers = []
    for q in qualifier_candidates:
        if re.search(r'\b' + re.escape(q) + r'\b', full_text, flags=re.IGNORECASE):
            if not any(q.lower() in existing.lower() for existing in qualifiers):
                matched = next((m.group(0) for m in re.finditer(r'\b' + re.escape(q) + r'\b', full_text, flags=re.IGNORECASE)), q)
                qualifiers.append(matched)

    # Metric identity
    cleaned = full_text
    for d in dates:
        cleaned = re.sub(r'\b' + re.escape(d) + r'\b', '', cleaned, flags=re.IGNORECASE)
    for q in qualifiers:
        cleaned = re.sub(r'\b' + re.escape(q) + r'\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\([^)]*\)', '', cleaned)
    cleaned = re.sub(r'\b(?:on|as of|for|in|at)\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[_\s]+', ' ', cleaned).strip(' -_/:,')
    if not cleaned:
        cleaned = str(column).strip()

    norm_display = format_display_label(cleaned)

    return {
        'physical_header_path': physical_path,
        'normalized_display_label': norm_display,
        'metric_identity': cleaned,
        'qualifiers': qualifiers,
        'dates': dates,
        'units': units
    }


def prepare_sheets(frames, source, embed=True):
    from .data_engine.semantic_classifier import SemanticClassifier
    prepared = []
    for name, frame in frames.items():
        recon_meta = getattr(frame, 'attrs', {}).get('reconstruction_metadata')
        frame = frame.copy()
        frame, header_geometry = infer_hierarchical_headers(frame)
        if recon_meta:
            header_geometry['reconstruction'] = recon_meta
        
        # 1. Automatic Datetime Normalization to ISO-8601 (YYYY-MM-DD)
        temporal_meta = {}
        for column in frame.columns:
            is_dt, _, _ = SemanticClassifier._is_date(frame[column], str(column))
            if is_dt:
                parsed_dt, is_df, info = SemanticClassifier.detect_and_parse_datetime_series(frame[column])
                if parsed_dt is not None and info:
                    # Normalize in-place to unambiguous ISO strings YYYY-MM-DD
                    frame[column] = parsed_dt.dt.strftime('%Y-%m-%d').fillna('')
                    temporal_meta[column] = info
                    logger.info(f"Normalized column '{column}' in '{name}' to ISO-8601: {info.get('summary')}")

        records = json.loads(frame.to_json(orient='records', date_format='iso'))
        profiles = []
        for column in frame.columns:
            values = [row[column] for row in records if value_key(row[column])]
            numeric, unit = numeric_values(pd.Series(values, dtype=object), column)
            null_pct = round(((len(records) - len(values)) / max(1, len(records))) * 100, 1)
            profile = {
                'column': column,
                'canonical': canonical(column),
                'display_name': format_display_label(column),
                'category_labels': category_display_labels(column, values) if len(set(map(str, values))) <= 100 else {},
                'nonempty': len(values),
                'missing': len(records) - len(values),
                'null_percentage': null_pct,
                'distinct': len({value_key(v) for v in values}),
                'is_mostly_null': null_pct >= 85.0,
                'semantic_components': decompose_header_semantics(
                    column,
                    header_mapping=header_geometry.get('mappings', {}).get(column),
                    unit=unit
                )
            }
            # Attach temporal metadata if applicable
            if column in temporal_meta:
                t_info = temporal_meta[column]
                profile['temporal_cadence'] = t_info.get('temporal_cadence')
                profile['cadence_interval_days'] = t_info.get('cadence_interval_days')
                profile['cadence_anchor'] = t_info.get('cadence_anchor')
                profile['min_date'] = t_info.get('min_date')
                profile['max_date'] = t_info.get('max_date')
                profile['temporal_summary'] = t_info.get('summary')

            # IDs, booleans, row ordinals, and numeric-looking codes are not measures.
            is_ordinal = bool(re.match(r'^(sr|s|seq|row)[\._\s]?no\.?', str(column), re.I)) or canonical(column) in (
                'sr_no', 's_no', 'srno', 'sno', 'serial_no', 'row_num', 'row_no', 'row_id', 'seq_no'
            )
            identifier = canonical(column).endswith('id') or canonical(column).endswith('_id') or 'code' in canonical(column) or is_ordinal
            if is_ordinal:
                profile['semantic_role'] = 'IDENTIFIER'
            if len(values) and not identifier and numeric.notna().all() and np.isfinite(numeric.astype(float)).all():
                profile['numeric'] = {k: float(getattr(numeric.astype(float), k)()) for k in ('min', 'max', 'mean', 'sum')}
                profile['unit'] = unit
                if unit or any(term in canonical(column) for term in ('rate', 'rating', 'percent')):
                    profile['numeric'].pop('sum', None)
            profiles.append(profile)

        hints = compute_decision_hints(profiles, records)
        if temporal_meta:
            primary_t_info = next(iter(temporal_meta.values()))
            hints['temporal_cadence'] = primary_t_info.get('temporal_cadence')
            hints['temporal_summary'] = primary_t_info.get('summary')
            hints['min_date'] = primary_t_info.get('min_date')
            hints['max_date'] = primary_t_info.get('max_date')

        # 2. Hierarchical Chunking: Macro-Temporal Chunks + Row Chunks
        macro_chunks = []
        if temporal_meta:
            for t_col, t_info in temporal_meta.items():
                macro_chunks.append(
                    f"Source: {source}; Sheet: {name}; Column '{t_col}' Temporal Granularity: {t_info.get('summary')}"
                )
                # Compute monthly rollups for macro-retrieval
                try:
                    dt_series = pd.to_datetime(frame[t_col], errors='coerce')
                    valid_mask = dt_series.notna()
                    if valid_mask.sum() >= 4:
                        frame_temp = frame[valid_mask].copy()
                        frame_temp['__month_dt'] = dt_series[valid_mask].dt.to_period('M')
                        frame_temp['__month_name'] = dt_series[valid_mask].dt.strftime('%B %Y')
                        
                        # Find primary numeric columns
                        num_cols = [p['column'] for p in profiles if p.get('numeric') and not p.get('is_mostly_null')]
                        pri_num = num_cols[0] if num_cols else None
                        id_col = next((p['column'] for p in profiles if canonical(p['column']).endswith('id') or 'store' in canonical(p['column'])), None)

                        for _, m_grp in frame_temp.groupby('__month_dt'):
                            m_label = m_grp['__month_name'].iloc[0]
                            m_dates = sorted(m_grp[t_col].unique())
                            if not m_dates:
                                continue
                            
                            cycle_desc = []
                            for d_val, d_grp in m_grp.groupby(t_col):
                                if pri_num:
                                    d_num = pd.to_numeric(d_grp[pri_num].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').sum()
                                    cycle_desc.append(f"{d_val} (total {pri_num}: {d_num:,.2f})")
                                else:
                                    cycle_desc.append(f"{d_val} ({len(d_grp)} rows)")
                            
                            cycles_str = "; ".join(cycle_desc[:6])
                            m_summary = f"Source: {source}; Sheet: {name}; Period: {m_label} ({m_dates[0]} to {m_dates[-1]}). Discrete cycles ({len(m_dates)} dates): {cycles_str}."
                            if pri_num:
                                total_val = pd.to_numeric(m_grp[pri_num].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').sum()
                                avg_val = pd.to_numeric(m_grp[pri_num].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').mean()
                                entity_count = m_grp[id_col].nunique() if id_col else len(m_grp)
                                m_summary += f" Monthly total {pri_num}: {total_val:,.2f}, average: {avg_val:,.2f} across {entity_count} entities."
                            macro_chunks.append(m_summary)
                except Exception as m_exc:
                    logger.debug(f"Could not build monthly macro chunks: {m_exc}")

        row_chunks = [f"Source: {source}; Sheet: {name}; Row: {i + 1}. " + '; '.join(f'{k}: {v}' for k, v in row.items() if value_key(v)) for i, row in enumerate(records)]
        all_chunks = macro_chunks + row_chunks

        vectors = model_embeddings([f"Column {p['column']} ({p['canonical']})" for p in profiles]) if embed else []
        for profile, vector in zip(profiles, vectors):
            profile['vector'] = vector
            profile['embedding_model'] = config.OLLAMA_EMBED_MODEL

        chunk_vectors = []
        if vectors:  # A failed column batch avoids repeatedly contacting an offline model.
            for start in range(0, len(all_chunks), 64):
                batch = model_embeddings(all_chunks[start:start+64])
                if not batch:
                    break
                chunk_vectors.extend(batch)

        prepared.append({
            'name': name,
            'columns': list(frame.columns),
            'profiles': profiles,
            'records': records,
            'macro_chunks_count': len(macro_chunks),
            'chunks': all_chunks,
            'vectors': chunk_vectors,
            'header_geometry': header_geometry,
            'decision_hints': hints
        })
    return prepared


def insert_sheets(conn, dataset_id, prepared, display_name=None):
    from .rag_service import pack_vector
    for sheet in prepared:
        sheet_disp = display_name or sheet.get('display_name') or sheet['name']
        geom_json = json.dumps(sheet.get('header_geometry') or {})
        sid = conn.execute(
            'INSERT INTO sheets(dataset_id,name,display_name,columns_json,profile_json,row_count,header_geometry_json) VALUES (?,?,?,?,?,?,?)',
            (dataset_id, sheet['name'], sheet_disp, json.dumps(sheet['columns']), json.dumps(sheet['profiles']), len(sheet['records']), geom_json)
        ).lastrowid

        records = sheet.get('records', [])
        chunks = sheet.get('chunks', [])
        vectors = sheet.get('vectors', [])
        total_records = len(records)
        num_macro = sheet.get('macro_chunks_count', 0)

        # High-performance chunked batch insertion (1,000 rows per transaction chunk)
        batch_size = 1000
        for b_start in range(0, total_records, batch_size):
            b_end = min(b_start + batch_size, total_records)

            rows_batch = [
                (sid, i, json.dumps(records[i]))
                for i in range(b_start, b_end)
            ]
            conn.executemany('INSERT INTO sheet_rows(sheet_id,row_index,data_json) VALUES (?,?,?)', rows_batch)

            cells_batch = [
                (sid, i, col, value_key(val))
                for i in range(b_start, b_end)
                for col, val in records[i].items()
                if value_key(val)
            ]
            if cells_batch:
                conn.executemany('INSERT INTO sheet_cells(sheet_id,row_index,column_name,value_key) VALUES (?,?,?,?)', cells_batch)

        # Insert all chunks (macro summary chunks first with row_index=-1, then row chunks)
        for c_idx, chunk_txt in enumerate(chunks):
            is_macro = c_idx < num_macro
            row_idx = -1 if is_macro else (c_idx - num_macro)
            metadata = {
                'dataset_id': dataset_id,
                'sheet_id': sid,
                'sheet_name': sheet['name'],
                'row_index': row_idx,
                'is_macro_summary': is_macro
            }
            if c_idx < len(vectors) and vectors[c_idx]:
                metadata['embedding_model'] = config.OLLAMA_EMBED_MODEL

            chunk_id = conn.execute(
                'INSERT INTO tabular_chunks(dataset_id,sheet_name,row_index,chunk_text,metadata_json) VALUES (?,?,?,?,?)',
                (dataset_id, sheet['name'], row_idx, chunk_txt, json.dumps(metadata))
            ).lastrowid

            if c_idx < len(vectors) and vectors[c_idx]:
                conn.execute(
                    'INSERT INTO tabular_vectors(id,embedding) VALUES (?,?)',
                    (chunk_id, pack_vector(vectors[c_idx]))
                )


def prepare_existing_column_vectors():
    conn = get_connection()
    try:
        sheets = [(r['id'], json.loads(r['profile_json'])) for r in conn.execute('SELECT id,profile_json FROM sheets')]
    finally:
        conn.close()
    missing = [(sid, profile) for sid, profiles in sheets for profile in profiles if not profile.get('vector')]
    vectors = model_embeddings([
        f"Column {p.get('column') or p.get('name') or p.get('column_name') or ''} ({p.get('canonical') or p.get('column') or ''})"
        for _, p in missing
    ])
    for (_, profile), vector in zip(missing, vectors):
        profile['vector'] = vector
        profile['embedding_model'] = config.OLLAMA_EMBED_MODEL
    return sheets if vectors else []


def sync_catalog_metadata(conn):
    if not conn.execute("SELECT 1 FROM app_metadata WHERE key='sheet_profiles_v2'").fetchone():
        for sheet in conn.execute('SELECT * FROM sheets').fetchall():
            records = [json.loads(r['data_json']) for r in conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet['id'],))]
            frame = pd.DataFrame(records, columns=json.loads(sheet['columns_json']))
            profiles = prepare_sheets({sheet['name']: frame}, '', embed=False)[0]['profiles']
            previous = {p['column']: p for p in json.loads(sheet['profile_json'])}
            for profile in profiles:
                old = previous.get(profile['column'], {})
                if old.get('vector'):
                    profile.update(vector=old['vector'], embedding_model=old['embedding_model'])
            conn.execute('UPDATE sheets SET profile_json=? WHERE id=?', (json.dumps(profiles), sheet['id']))
        conn.execute("INSERT INTO app_metadata VALUES ('sheet_profiles_v2','complete')")
    for dataset in conn.execute('SELECT id FROM dataset_uploads').fetchall():
        sheets = conn.execute('SELECT columns_json,row_count FROM sheets WHERE dataset_id=? ORDER BY id', (dataset['id'],)).fetchall()
        if sheets:
            conn.execute('UPDATE dataset_uploads SET sheet_count=?,row_count=?,col_count=?,columns_json=? WHERE id=?',
                         (len(sheets), sum(s['row_count'] for s in sheets), len(json.loads(sheets[0]['columns_json'])), sheets[0]['columns_json'], dataset['id']))


def rebuild_relationships(conn):
    sheets = conn.execute('SELECT * FROM sheets ORDER BY id').fetchall()
    conn.execute('DELETE FROM sheet_relationships')
    counts = {}
    for row in conn.execute('SELECT sheet_id,column_name,value_key,COUNT(*) AS n FROM sheet_cells GROUP BY sheet_id,column_name,value_key'):
        counts.setdefault((row['sheet_id'], row['column_name']), {})[row['value_key']] = row['n']
    for idx, left in enumerate(sheets):
        for right in sheets[idx+1:]:
            for lp in json.loads(left['profile_json']):
                for rp in json.loads(right['profile_json']):
                    lc = lp.get('column') or lp.get('name') or lp.get('original_name') or ''
                    rc = rp.get('column') or rp.get('name') or rp.get('original_name') or ''
                    if not lc or not rc:
                        continue
                    lp_canon = lp.get('canonical') or canonical(lc)
                    rp_canon = rp.get('canonical') or canonical(rc)
                    exact = lp_canon == rp_canon
                    similarity = None
                    if not exact and lp.get('embedding_model') == rp.get('embedding_model') and lp.get('vector') and rp.get('vector'):
                        a, b = np.array(lp['vector']), np.array(rp['vector'])
                        denom = np.linalg.norm(a) * np.linalg.norm(b)
                        similarity = float(a @ b / denom) if denom else 0
                    if not exact and (similarity is None or similarity < .85):
                        continue
                    lv, rv = counts.get((left['id'], lc), {}), counts.get((right['id'], rc), {})
                    overlap = lv.keys() & rv.keys()
                    if not overlap:
                        continue
                    lu, ru = all(v == 1 for v in lv.values()), all(v == 1 for v in rv.values())
                    cardinality = ('one' if lu else 'many') + '-to-' + ('one' if ru else 'many')
                    keylike = lp_canon not in ('id', 'paid', 'valid') and (lp_canon in ('employee_id', 'employee_name', 'department', 'department_id', 'email') or lp_canon.endswith('id') or lp_canon.endswith('code'))
                    status = 'linked' if exact and keylike and (lu or ru) else 'suggested'
                    method = ('exact' if lc.casefold() == rc.casefold() else 'alias') if exact else 'vector'

                    # Join cardinality & grain validation
                    left_grain = "unique_entity" if lu else "event_or_cohort"
                    right_grain = "unique_entity" if ru else "event_or_cohort"
                    matching_pairs = sum(lv[k]*rv[k] for k in overlap)
                    fanout_factor = round(matching_pairs / max(1, len(overlap)), 2)

                    if status == 'linked':
                        reason = f'Validated {cardinality} grain ({left_grain} to {right_grain}); exact equality join.'
                    elif not lu and not ru:
                        reason = f'Many-to-many grain ({left_grain} to {right_grain}) with fan-out ratio {fanout_factor}x. Grain aggregation recommended before join.'
                    else:
                        reason = f'Candidate relationship ({cardinality}): review before use. Similarity or shared values alone do not establish identity.'

                    conn.execute('''INSERT INTO sheet_relationships(left_sheet,right_sheet,left_column,right_column,method,status,cardinality,matching_keys,matching_pairs,similarity,reason)
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (left['id'], right['id'], lc, rc, method, status, cardinality, len(overlap), matching_pairs, similarity, reason))


def catalogue(conn):
    output = []
    for row in conn.execute('SELECT s.*, d.original_name, d.display_name AS dataset_display_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id'):
        entry = dict(row)
        entry['display_name'] = entry.get('display_name') or entry.get('dataset_display_name') or entry.get('original_name') or entry.get('name')
        entry['columns'] = json.loads(entry.pop('columns_json'))
        entry['header_geometry'] = json.loads(entry.pop('header_geometry_json', None) or '{}')
        profiles = json.loads(entry.pop('profile_json') or '[]')
        for p in profiles:
            if 'display_name' not in p and 'column' in p:
                p['display_name'] = format_display_label(p['column'])
        entry['profiles'] = [{k: v for k, v in p.items() if k not in ('vector', 'embedding_model')} for p in profiles]
        entry['display_columns'] = {c: format_display_label(c) for c in entry['columns']}

        # Summary completeness and data types metrics for instant display in Data Explorer
        total_rows = entry.get('row_count', 0)
        total_cols = len(entry['columns'])
        total_cells = max(1, total_rows * total_cols)
        total_missing = sum(p.get('missing', 0) for p in profiles)
        cols_with_missing = [p['column'] for p in profiles if p.get('missing', 0) > 0]
        numeric_count = sum(1 for p in profiles if p.get('numeric') is not None)
        date_count = sum(1 for p in profiles if any(t in p.get('column', '').lower() for t in ('date', 'time', 'year', 'month', 'day', 'timestamp', 'period')) or p.get('unit') in ('date', 'datetime'))
        cat_count = max(0, total_cols - numeric_count - date_count)
        entry['completeness'] = {
            'total_missing': total_missing,
            'total_cells': total_cells,
            'missing_pct': round((total_missing / total_cells) * 100, 2),
            'completeness_pct': round(100.0 - ((total_missing / total_cells) * 100), 2),
            'cols_with_missing_count': len(cols_with_missing),
            'cols_with_missing': cols_with_missing,
            'is_incomplete': total_missing > 0,
            'data_types_breakdown': {
                'numeric': numeric_count,
                'categorical': cat_count,
                'datetime': date_count
            }
        }
        output.append(entry)
    return output


def backfill_display_names():
    """Lightweight migration: ensures existing stored sheet profiles include display_name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, profile_json FROM sheets").fetchall()
        for r in rows:
            sid = r["id"]
            if not r["profile_json"]:
                continue
            profiles = json.loads(r["profile_json"])
            modified = False
            for p in profiles:
                if 'display_name' not in p and 'column' in p:
                    p['display_name'] = format_display_label(p['column'])
                    modified = True
            if modified:
                conn.execute("UPDATE sheets SET profile_json=? WHERE id=?", (json.dumps(profiles), sid))
        conn.commit()
    except Exception as e:
        logger.warning(f"Failed to backfill display names: {e}")
    finally:
        conn.close()


def relationships(conn):
    return [dict(row) for row in conn.execute('''SELECT r.*, l.name AS left_name, rr.name AS right_name,
        ld.original_name AS left_file, rd.original_name AS right_file FROM sheet_relationships r
        JOIN sheets l ON l.id=r.left_sheet JOIN sheets rr ON rr.id=r.right_sheet
        JOIN dataset_uploads ld ON ld.id=l.dataset_id JOIN dataset_uploads rd ON rd.id=rr.dataset_id ORDER BY r.id''')]


def overview():
    conn = get_connection()
    try:
        sheets = catalogue(conn)
        links = relationships(conn)
        sources = [dict(r) for r in conn.execute('SELECT id,original_name,filename,summary_insights,row_count,sheet_count FROM dataset_uploads ORDER BY id DESC')]
        return {'stats': {'datasets': len(sources), 'sheets': len(sheets), 'rows': sum(s['row_count'] for s in sheets),
                          'linked_relationships': sum(r['status'] == 'linked' for r in links)},
                'sheets': sheets, 'relationships': links, 'sources': sources,
                'note': 'Rows are source records, not unique employees. Metrics stay separate by sheet to avoid double counting joins.'}
    finally:
        conn.close()


def migrate_existing():
    """Import legacy original files once; archive old derived data before retiring it."""
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM app_metadata WHERE key='sheet_catalog_v1'").fetchone():
            sync_catalog_metadata(conn)
            conn.commit()
            return
        # A local recovery snapshot includes the legacy derived employee data.
        import sqlite3
        backup_path = config.DB_PATH.parent / 'before_sheet_catalog_v1.sqlite3'
        if not backup_path.exists():
            backup = sqlite3.connect(backup_path)
            try:
                conn.backup(backup)
            finally:
                backup.close()
        pending = []
        for dataset in conn.execute('SELECT * FROM dataset_uploads').fetchall():
            if conn.execute('SELECT 1 FROM sheets WHERE dataset_id=?', (dataset['id'],)).fetchone():
                continue
            path = (config.UPLOADS_DIR / dataset['filename']).resolve()
            if not path.is_relative_to(config.UPLOADS_DIR.resolve()):
                continue
            if not path.is_file() and dataset['filename'] == 'attendance_2023_2024.csv':
                path = config.KAGGLE_LOCAL_CACHE / dataset['filename']
            try:
                pending.append((dataset['id'], prepare_sheets(read_sheets(path), dataset['original_name'], embed=False)))
            except (OSError, ValueError, ImportError) as exc:
                logger.warning('Cannot migrate dataset %s: %s', dataset['id'], exc)
                pending.append((dataset['id'], None))
        with conn:
            conn.execute("DELETE FROM tabular_vectors WHERE id IN (SELECT id FROM tabular_chunks WHERE json_extract(metadata_json,'$.sheet_id') IS NULL)")
            conn.execute("DELETE FROM tabular_chunks WHERE json_extract(metadata_json,'$.sheet_id') IS NULL")
            conn.execute('DELETE FROM attendance_records')
            conn.execute('DELETE FROM hr_alerts')
            conn.execute('DELETE FROM employees')
            for dataset_id, prepared in pending:
                if prepared is not None:
                    insert_sheets(conn, dataset_id, prepared)
                    conn.execute('UPDATE dataset_uploads SET row_count=?,sheet_count=?,summary_insights=? WHERE id=?',
                                 (sum(len(s['records']) for s in prepared), len(prepared), 'Original sheet data imported. Demo employee synthesis has been retired.', dataset_id))
                else:
                    conn.execute('UPDATE dataset_uploads SET summary_insights=? WHERE id=?', ('Original file unavailable. Delete this entry or upload the file again.', dataset_id))
            sync_catalog_metadata(conn)
            rebuild_relationships(conn)
            conn.execute("INSERT INTO app_metadata VALUES ('sheet_catalog_v1','complete')")
    finally:
        conn.close()


def linked_evidence(results, limit=12):
    """Expand retrieved rows via explicit key equality, never vector similarity alone."""
    conn = get_connection()
    found, seen = [], {r['chunk_id'] for r in results}
    try:
        for result in results:
            meta = result.get('metadata', {})
            sid, index = meta.get('sheet_id'), meta.get('row_index')
            if sid is None or index is None:
                continue
            links = conn.execute("SELECT * FROM sheet_relationships WHERE status='linked' AND (left_sheet=? OR right_sheet=?)", (sid, sid)).fetchall()
            for link in links:
                forward = sid == link['left_sheet']
                target = link['right_sheet'] if forward else link['left_sheet']
                source_col = link['left_column'] if forward else link['right_column']
                target_col = link['right_column'] if forward else link['left_column']
                rows = conn.execute('''SELECT c.*,d.original_name FROM sheet_cells a JOIN sheet_cells b ON a.value_key=b.value_key
                    JOIN sheets s ON s.id=b.sheet_id JOIN dataset_uploads d ON d.id=s.dataset_id
                    JOIN tabular_chunks c ON c.dataset_id=s.dataset_id AND c.sheet_name=s.name AND c.row_index=b.row_index
                    WHERE a.sheet_id=? AND a.row_index=? AND a.column_name=? AND b.sheet_id=? AND b.column_name=? LIMIT ?''',
                    (sid, index, source_col, target, target_col, limit)).fetchall()
                for row in rows:
                    if row['id'] in seen:
                        continue
                    seen.add(row['id'])
                    found.append({'chunk_id': row['id'], 'text': row['chunk_text'], 'metadata': json.loads(row['metadata_json']),
                                  'source_file': row['original_name'], 'sheet_name': row['sheet_name'], 'row_index': row['row_index'],
                                  'relevance_score': 0, 'retrieval_methods': ['exact_join'], 'relationship_id': link['id']})
                    if len(found) >= limit:
                        return found
        return found
    finally:
        conn.close()
