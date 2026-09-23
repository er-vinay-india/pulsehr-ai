"""AI Sheet Naming & Semantic Classification Pipeline.

Cleanses raw filenames (strips copy artifacts, underscores, hashes, version tags),
evaluates token meaningfulness via data science heuristics, inspects column schemas
and sample data structures, and synthesizes polished, executive Proper Title Case display names.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any

import httpx

from ..core import config

logger = logging.getLogger(__name__)

# Common acronyms that should maintain uppercase casing in titles
KNOWN_ACRONYMS = {
    "HR", "ID", "KPI", "KPIS", "AI", "ML", "USA", "UK", "EU",
    "Q1", "Q2", "Q3", "Q4", "FY", "YTD", "MTD", "EBITDA",
    "CRM", "ERP", "ATS", "IT", "SLA", "CSV", "DB", "CEO", "CFO", "CTO"
}

# Stopwords and generic placeholder names that convey no domain meaning
GENERIC_PLACEHOLDERS = {
    "sheet", "sheets", "sheet1", "sheet2", "sheet3", "sheet4", "sheet5",
    "data", "dataset", "export", "file", "uploaded", "upload", "book", "book1",
    "table", "tabular", "untitled", "test", "temp", "sample", "raw", "new",
    "document", "spreadsheet", "records", "input", "output"
}

# Common English and domain words used to verify meaningfulness
DICTIONARY_WORDS = {
    # HR & Workforce
    "employee", "employees", "staff", "personnel", "workforce", "talent", "worker", "workers",
    "attendance", "attend", "present", "absent", "absence", "leave", "leaves", "sick", "casual",
    "performance", "score", "scores", "rating", "ratings", "review", "reviews", "evaluation",
    "appraisal", "goal", "goals", "kpi", "metric", "metrics", "competency", "feedback",
    "salary", "salaries", "pay", "payroll", "compensation", "wage", "wages", "bonus", "equity",
    "attrition", "turnover", "retention", "tenure", "exit", "resignation", "termination",
    "recruitment", "hiring", "applicant", "applicants", "candidate", "candidates", "interview",
    "training", "course", "courses", "skills", "skill", "learning", "development", "certification",
    "department", "dept", "division", "team", "office", "branch", "location", "headcount",
    "hours", "shift", "overtime", "timecard", "timesheet", "clock", "checkin", "checkout",
    # Business & Operations
    "sales", "weekly", "daily", "monthly", "annual", "quarterly", "revenue", "profit",
    "retail", "store", "stores", "shop", "customer", "customers", "order", "orders",
    "price", "pricing", "margin", "inventory", "stock", "product", "products", "item", "items",
    "finance", "financial", "expense", "expenses", "budget", "ledger", "cost", "costs",
    "supply", "chain", "logistics", "warehouse", "freight", "shipping", "shipment", "fleet",
    "service", "incident", "ticket", "tickets", "support", "survey", "engagement", "pulse"
}


# Noise prefixes and abbreviations
NOISE_PREFIXES = {"enc", "tmp", "temp", "id", "num", "no", "hex", "hash", "code", "str", "val", "v", "ver"}


def sanitize_filename_string(raw_name: str) -> str:
    """Strips extensions, artifact patterns (copy, (1), versions, final, draft), and converts punctuation to spaces."""
    if not raw_name:
        return ""

    name = raw_name.strip()

    # 1. Remove file extensions
    name = re.sub(r"\.(?:csv|xlsx|xls|tsv|txt)$", "", name, flags=re.IGNORECASE)

    # 2. Remove Kaggle/source prefixes like 'Kaggle_' or 'Download_'
    name = re.sub(r"^(?:kaggle|download|export|raw)[_\s-]+", "", name, flags=re.IGNORECASE)

    # 3. Remove all parenthetical tags like '(yasirub_employee-attendance-ratings)', '(1)', '(copy)'
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"\[[^\]]*\]", "", name)

    # 4. Remove copy markers: 'copy', 'copy 2', '_copy', etc.
    name = re.sub(r"(?i)(?:^|[\s_.-]+)copy(?:[\s_.-]*\d+)?", " ", name)

    # 5. Remove version and stage suffixes: '_v2', 'v1.0', '-final', '_draft'
    name = re.sub(r"(?i)(?:^|[\s_.-]+)(?:v\d+(?:\.\d+)?|final|draft|v_\d+|ver\d+)(?=[\s_.-]+|$)", " ", name)

    # 6. Remove numeric run sequences like '(1)', '[2]'
    name = re.sub(r"\[\d+\]|\(\d+\)", "", name)

    # 7. Replace underscores, hyphens, and multiple dots with space
    name = re.sub(r"[_\-\.]+", " ", name)

    # 8. Clean extra whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def compute_shannon_entropy(text: str) -> float:
    """Computes Shannon entropy to detect random hash strings and encryption keys."""
    clean = re.sub(r"[^a-zA-Z0-9]", "", text)
    if not clean:
        return 0.0
    freq = {}
    for ch in clean:
        freq[ch] = freq.get(ch, 0) + 1
    entropy = 0.0
    length = len(clean)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def is_meaningless_or_noise(text: str) -> bool:
    """Determines if a filename string is meaningless noise (hex hashes, timestamps, encryption, or generic)."""
    cleaned = text.strip()
    if not cleaned:
        return True

    lower = cleaned.lower()
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", lower)]

    if not tokens:
        return True

    # Check if tokens are all generic placeholders or noise prefixes or digits
    if all(t.isdigit() or t in GENERIC_PLACEHOLDERS or t in NOISE_PREFIXES for t in tokens):
        return True

    # Check if purely numeric or timestamp (e.g. '1689239842', '20230101', '8492048')
    if re.fullmatch(r"[\d\s_-]+", cleaned):
        return True

    # Check if looks like a hex string / UUID / hash (e.g. '76194746933b43b38866ba4a82b2f03b', 'enc_8492819')
    if re.fullmatch(r"(?:enc|hash|uuid|tmp|id)?[a-f0-9]{6,64}", lower):
        return True

    # High entropy check for random character sequences
    if len(cleaned) >= 8 and compute_shannon_entropy(cleaned) > 4.2 and not any(t in DICTIONARY_WORDS for t in tokens):
        return True

    # Check if at least one token is a recognized dictionary/domain word
    has_real_words = False
    for t in tokens:
        if len(t) >= 3 and t in DICTIONARY_WORDS:
            has_real_words = True
            break
        vowels = len(re.findall(r"[aeiouy]", t))
        if vowels > 0 and len(t) >= 3 and t not in NOISE_PREFIXES and not re.search(r"[0-9]{3,}", t):
            has_real_words = True

    return not has_real_words


def detect_person_name(text: str) -> str | None:
    """Detects if a string represents an individual person's name or employee identifier."""
    # Pattern: Person_77, Person 0, Employee_104, Employee 21
    match_person_id = re.search(r"(?i)\b(?:person|employee|staff|worker)\s*[_ -]?\s*(\d+)\b", text.strip())
    if match_person_id:
        num = match_person_id.group(1)
        return f"Person {num}"

    tokens = [t for t in text.strip().split() if t.lower() not in GENERIC_PLACEHOLDERS and t.lower() not in NOISE_PREFIXES]
    # If 2 or 3 tokens consisting solely of alphabetic characters and not matching common domain words
    if 2 <= len(tokens) <= 3 and all(t.isalpha() for t in tokens):
        if not any(t.lower() in DICTIONARY_WORDS for t in tokens):
            return " ".join(t.capitalize() for t in tokens)

    return None


def infer_from_columns_and_sample(
    columns: list[str],
    sample_records: list[dict[str, Any]] | None = None
) -> tuple[str, str, str]:
    """Infers semantic business domain, display title, and description from column architecture and sample values.

    Returns: (display_name, domain, description)
    """
    if not columns:
        return "Workforce Tabular Dataset", "General Tabular", "Tabular records and business metrics."

    cols_clean = [re.sub(r"[^\w]", "", c.casefold()).replace("_", "") for c in columns]

    # 1. Wide Attendance Matrix Pattern:
    # First column is Date, and multiple columns follow 'Person_X', 'Person X', or sample cell has 'HH:MM-HH:MM'
    has_date = any("date" in c for c in cols_clean[:2])
    person_cols = sum(bool(re.match(r"(?i)person\d+|employee\d+", c)) for c in cols_clean)
    
    # Check sample cell values for time ranges (e.g. '08:43-16:42')
    sample_has_time_range = False
    if sample_records and len(sample_records) > 0:
        for row in sample_records[:3]:
            for val in list(row.values())[:10]:
                if isinstance(val, str) and re.match(r"^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$", val.strip()):
                    sample_has_time_range = True
                    break
            if sample_has_time_range:
                break

    if (has_date and person_cols >= 5) or sample_has_time_range:
        tracked = person_cols if person_cols > 0 else (len(columns) - 1)
        return (
            "Daily Attendance & Time Tracking Logs",
            "Attendance & Working Hours",
            f"Daily check-in and check-out tracking across {tracked} workforce personnel."
        )

    # 2. Performance & Appraisal
    perf_kw = ("performance", "rating", "score", "eval", "kpi", "goal", "review", "competency", "potential", "appraisal")
    perf_matches = sum(any(k in c for k in perf_kw) for c in cols_clean)

    # 3. Absence & Leaves
    abs_kw = ("absent", "absence", "leave", "sick", "casual", "vacation", "unplanned")
    abs_matches = sum(any(k in c for k in abs_kw) for c in cols_clean)

    # 4. Compensation & Payroll
    comp_kw = ("salary", "pay", "payroll", "bonus", "equity", "wage", "compensation", "hourlyrate", "stipend")
    comp_matches = sum(any(k in c for k in comp_kw) for c in cols_clean)

    # 5. Attrition & Retention
    attr_kw = ("attrition", "turnover", "exit", "tenure", "resignation", "termination", "retention")
    attr_matches = sum(any(k in c for k in attr_kw) for c in cols_clean)

    # 6. Recruitment & Hiring
    rec_kw = ("candidate", "applicant", "stage", "timetohire", "requisition", "recruiter", "interview", "offer")
    rec_matches = sum(any(k in c for k in rec_kw) for c in cols_clean)

    # 7. Retail & Store Sales
    sales_kw = ("weeklysales", "sales", "store", "revenue", "cpi", "fuelprice", "unemployment", "holidayflag")
    sales_matches = sum(any(k in c for k in sales_kw) for c in cols_clean)

    # 8. Training & Learning
    train_kw = ("training", "course", "certification", "completion", "skill", "learning", "module")
    train_matches = sum(any(k in c for k in train_kw) for c in cols_clean)

    # 9. Supply Chain & Logistics
    log_kw = ("shipment", "warehouse", "freight", "carrier", "transit", "fleet", "delivery", "dispatch")
    log_matches = sum(any(k in c for k in log_kw) for c in cols_clean)

    # Score evaluations
    scores = {
        ("Employee Performance & Review Records", "Performance & Talent Appraisal", "Quarterly evaluation ratings, KPI milestones, and competency benchmarks."): perf_matches,
        ("Employee Absence & Leave Records", "Attendance & Working Hours", "Logged employee absence patterns, sick leaves, and time off durations."): abs_matches,
        ("Compensation & Payroll Records", "Compensation & Payroll", "Salary distribution, variable bonus payouts, and compensation benchmarks."): comp_matches,
        ("Workforce Retention & Attrition Analysis", "Workforce Retention & Attrition", "Employee tenure progression, flight risk factors, and exit patterns."): attr_matches,
        ("Recruitment & Talent Pipeline", "Recruitment & Hiring Pipeline", "Job candidates, hiring stages, interview scores, and offer metrics."): rec_matches,
        ("Retail Sales & Store Operations", "Retail & Commercial Sales", "Multi-store weekly sales metrics, economic indicators, and holiday volume."): sales_matches,
        ("Employee Training & Skills Development", "Training & Skills Development", "Curriculum progress, technical certification status, and skill mastery."): train_matches,
        ("Supply Chain & Logistics Tracking", "Supply Chain & Logistics", "Shipment lifecycle tracking, warehouse logistics, and fleet metrics."): log_matches,
    }

    best_match, highest_score = max(scores.items(), key=lambda item: item[1])
    if highest_score >= 1:
        return best_match

    # Fallback to general tabular
    return (
        "Workforce Tabular Dataset",
        "General Tabular Analytics",
        f"Multi-column tabular dataset tracking {len(columns)} attributes."
    )


def proper_title_case(text: str) -> str:
    """Formats a text string into clean, professional Proper Title Case:

    - First letter capitalized, remaining letters lowercase.
    - Preserves standard acronyms (HR, ID, KPI, AI, EBITDA).
    - Removes duplicate spaces and trailing punctuation.
    """
    if not text:
        return ""

    # Split into words while preserving punctuation attached to words
    words = re.findall(r"[A-Za-z0-9]+|[&/+\-]", text.strip())
    formatted_words = []

    minor_words = {"and", "or", "of", "for", "to", "in", "on", "at", "by", "with", "a", "an", "the"}

    for idx, word in enumerate(words):
        upper = word.upper()
        lower = word.lower()

        # Check if known acronym
        if upper in KNOWN_ACRONYMS:
            formatted_words.append(upper)
        elif word in ("&", "/", "+", "-"):
            formatted_words.append(word)
        elif idx > 0 and lower in minor_words and idx != len(words) - 1:
            formatted_words.append(lower)
        else:
            # First letter capital, rest lower
            formatted_words.append(word[0].upper() + word[1:].lower())

    result = " ".join(formatted_words)
    # Fix spacing around symbols like &
    result = re.sub(r"\s+&\s+", " & ", result)
    result = re.sub(r"\s+/\s+", " / ", result)
    result = re.sub(r"\s+-\s+", " - ", result)
    return result.strip()


def query_llm_sheet_naming(
    clean_name: str,
    columns: list[str],
    sample_records: list[dict[str, Any]] | None = None
) -> dict[str, str] | None:
    """Lightweight LLM call to synthesize an executive display title using ModelRole.FAST."""
    from .gateway.model_gateway import ModelGateway
    from ..core.models_config import ModelRole

    col_preview = columns[:15]
    prompt = (
        f"You are an enterprise data platform assistant. Given an uploaded dataset with:\n"
        f"Raw Cleaned Name: '{clean_name}'\n"
        f"Columns: {col_preview}\n\n"
        f"Generate:\n"
        f"1. A concise, professional Executive Display Name in Proper Title Case (2 to 5 words, e.g. 'Employee Performance Records', 'Daily Attendance Logs', 'Store Sales Operations').\n"
        f"2. A 1-sentence business description.\n"
        f"Output pure JSON only: {{\"display_name\": \"...\", \"description\": \"...\"}}"
    )

    try:
        res = ModelGateway.generate(
            role=ModelRole.FAST,
            prompt=prompt,
            step_name="sheet_naming"
        )
        if res.success and res.raw_text:
            match = re.search(r"\{[\s\S]*\}", res.raw_text)
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("display_name"):
                    return {
                        "display_name": proper_title_case(parsed["display_name"]),
                        "description": str(parsed.get("description", "")).strip()
                    }
    except Exception as e:
        logger.debug(f"Ollama naming skipped: {e}")
    return None


def generate_sheet_display_name(
    filename: str,
    columns: list[str] | None = None,
    sample_records: list[dict[str, Any]] | None = None,
    sheet_name: str | None = None
) -> dict[str, Any]:
    """Main pipeline entrypoint to generate a clean, proper executive display name.

    Returns:
        {
            "display_name": "Daily Attendance & Time Tracking Logs",
            "domain": "Attendance & Working Hours",
            "description": "Daily check-in and check-out tracking across 100 workforce personnel.",
            "original_name": "Kaggle_ Employee Attendance...csv",
            "is_person_profile": False
        }
    """
    cols = columns or []
    cleaned_filename = sanitize_filename_string(filename)

    # 1. Check for person name in filename
    person_match = detect_person_name(cleaned_filename)
    if person_match:
        inferred_title, domain, desc = infer_from_columns_and_sample(cols, sample_records)
        display_name = proper_title_case(f"{person_match} - {inferred_title}")
        return {
            "display_name": display_name,
            "domain": domain,
            "description": desc,
            "original_name": filename,
            "is_person_profile": True
        }

    # 2. Check if filename is meaningless or generic noise
    meaningless = is_meaningless_or_noise(cleaned_filename)

    # 3. Always run column schema inference
    inferred_title, domain, desc = infer_from_columns_and_sample(cols, sample_records)

    # 4. If filename is meaningless, or if structurally detected as a specialized wide matrix, prioritize structural inference
    if meaningless or inferred_title == "Daily Attendance & Time Tracking Logs":
        display_name = proper_title_case(inferred_title)
    else:
        # Check if the filename already has a rich domain name
        # If it has specific business terms (e.g. "Employee Performance Data"), use it cleaned up!
        title_words = cleaned_filename.split()
        if len(title_words) >= 2 and any(w.lower() in DICTIONARY_WORDS for w in title_words):
            # The cleaned filename is already rich and meaningful: format it properly
            display_name = proper_title_case(cleaned_filename)
        else:
            # Blend or default to inferred title
            display_name = proper_title_case(inferred_title)

    # 5. Optional LLM enhancement if filename has ambiguous context and not a specialized wide matrix
    if not meaningless and inferred_title != "Daily Attendance & Time Tracking Logs" and len(cols) > 0:
        llm_res = query_llm_sheet_naming(cleaned_filename, cols, sample_records)
        if llm_res and llm_res.get("display_name"):
            display_name = llm_res["display_name"]
            if llm_res.get("description"):
                desc = llm_res["description"]

    # Final polish
    display_name = proper_title_case(display_name)

    return {
        "display_name": display_name,
        "domain": domain,
        "description": desc,
        "original_name": filename,
        "is_person_profile": False
    }
