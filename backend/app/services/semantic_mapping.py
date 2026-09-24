"""Semantic Mapping & Field Governance Engine for PulseHR AI.

Provides versioned, typed metadata for spreadsheet columns, distinguishing
identities, dimensions, measures, periods, and derived totals.
Prevents identity column pollution (e.g. avg_full_name), enforces aggregation rules,
tracks direction of concern, and records data governance limitations.
"""

from dataclasses import dataclass, field
from typing import Literal
import hashlib
import json
import re
import pandas as pd

FieldRole = Literal['identity', 'dimension', 'measure', 'period', 'derived_total']
AggregationRule = Literal['sum', 'distinct_count', 'mean', 'ratio_of_sums', 'do_not_aggregate']
DirectionOfConcern = Literal['lower_is_worse', 'higher_is_worse', 'neutral']


@dataclass
class SemanticField:
    name: str
    field_role: FieldRole
    business_label: str
    aliases: list[str] = field(default_factory=list)
    units: str | None = None
    grain: str = 'record'
    valid_range: tuple[float | None, float | None] | None = None
    aggregation_rule: AggregationRule = 'mean'
    direction_of_concern: DirectionOfConcern = 'neutral'
    numerator_col: str | None = None
    denominator_col: str | None = None
    confidence: float = 1.0
    unresolved_definition: bool = False
    governance_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "field_role": self.field_role,
            "business_label": self.business_label,
            "aliases": self.aliases,
            "units": self.units,
            "grain": self.grain,
            "valid_range": self.valid_range,
            "aggregation_rule": self.aggregation_rule,
            "direction_of_concern": self.direction_of_concern,
            "numerator_col": self.numerator_col,
            "denominator_col": self.denominator_col,
            "confidence": self.confidence,
            "unresolved_definition": self.unresolved_definition,
            "governance_notes": self.governance_notes,
        }


@dataclass
class SemanticCatalog:
    sheet_name: str
    fields: dict[str, SemanticField] = field(default_factory=dict)
    unresolved_count: int = 0
    anomalies: list[str] = field(default_factory=list)

    def get_field(self, name: str) -> SemanticField | None:
        if name in self.fields:
            return self.fields[name]
        canon = name.strip().lower().replace('_', '').replace(' ', '')
        for f in self.fields.values():
            if f.name.strip().lower().replace('_', '').replace(' ', '') == canon:
                return f
            for alias in f.aliases:
                if alias.strip().lower().replace('_', '').replace(' ', '') == canon:
                    return f
        return None

    def get_measures(self) -> list[SemanticField]:
        return [f for f in self.fields.values() if f.field_role in ('measure', 'derived_total')]

    def get_dimensions(self) -> list[SemanticField]:
        return [f for f in self.fields.values() if f.field_role == 'dimension']

    def get_identities(self) -> list[SemanticField]:
        return [f for f in self.fields.values() if f.field_role == 'identity']

    def get_periods(self) -> list[SemanticField]:
        return [f for f in self.fields.values() if f.field_role == 'period']

    def get_catalog_hash(self) -> str:
        """Deterministic SHA-256 hash of catalog field definitions for versioning & audit."""
        payload = [
            (
                f.name,
                f.field_role,
                f.business_label,
                f.aggregation_rule,
                f.direction_of_concern,
                f.unresolved_definition
            )
            for f in sorted(self.fields.values(), key=lambda x: x.name)
        ]
        return hashlib.sha256(json.dumps(payload).encode('utf-8')).hexdigest()


def is_identity_header(col_name: str) -> bool:
    """Strictly checks if a header represents personal names, employee IDs, codes, or row keys."""
    c = str(col_name).strip().lower().replace(' ', '').replace('_', '').replace('-', '')
    if c in (
        'id', 'employeeid', 'empid', 'candidateid', 'applicantid',
        'code', 'index', 'serialno', 'sno', 'srno', 'rowid', 'row',
        'fullname', 'name', 'employeename', 'firstname', 'lastname',
        'candidatename', 'workername', 'staffname', 'personname',
        'email', 'workemail', 'phone', 'ssn'
    ):
        return True
    if c.startswith('unnamed') or c.endswith('id') or c.endswith('code') or c.endswith('key'):
        return True
    return False


def is_sequential_integers(series: pd.Series) -> bool:
    """Detects whether numeric values in a column are just sequential 1..N indices."""
    nums = pd.to_numeric(series, errors='coerce').dropna()
    if len(nums) < 5:
        return False
    # If values are integers and strictly increasing with step 1
    if (nums.astype(int) == nums).all():
        diffs = nums.diff().dropna()
        if (diffs == 1).all():
            return True
        # Or min is 1, max is len, all unique
        if nums.min() == 1 and nums.max() == len(nums) and nums.nunique() == len(nums):
            return True
    return False


def is_period_header(col_name: str) -> bool:
    """Detects headers representing specific date/calendar periods (e.g. '1st to 5th July', 'Leaves(1st to 5th July)')."""
    c = str(col_name).strip().lower()
    months = (
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    )
    has_month = any(m in c for m in months)
    has_range = bool(re.search(r'\b\d+(?:st|nd|rd|th)?\s*(?:to|-)\s*\d+(?:st|nd|rd|th)?\b', c))
    has_week = bool(re.search(r'\b(?:w|week)\s*\d+\b', c))
    return (has_month and (has_range or 'week' in c)) or (has_range and 'day' in c) or has_week


def infer_semantic_catalog(
    columns: list[str],
    records: list[dict] | None = None,
    sheet_name: str = 'Sheet'
) -> SemanticCatalog:
    """Builds a versioned semantic mapping for a sheet, validating field roles and identifying anomalies."""
    catalog = SemanticCatalog(sheet_name=sheet_name)
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=columns)
    total_rows = len(df)

    is_hr = any(any(k in c.lower() for k in ('employee', 'staff', 'worker', 'leave', 'attendance', 'candidate', 'applicant')) for c in columns)
    detected_grain = 'employee' if is_hr else 'record'

    for col in columns:
        col_clean = str(col).strip()
        c_lower = col_clean.lower()
        c_norm = c_lower.replace('_', ' ').replace('-', ' ')

        # 1. Identity field check
        if is_identity_header(col_clean):
            anomalies = []
            # Check if this name/identity column is stored as pure numbers
            if total_rows > 0 and col in df.columns:
                nums = pd.to_numeric(df[col], errors='coerce').dropna()
                if len(nums) > total_rows * 0.8:
                    if is_sequential_integers(df[col]):
                        anomalies.append(f"Header '{col_clean}' contains sequential numeric row indices (1 to {len(nums)}). Preserved as row identity; excluded from arithmetic.")
                    else:
                        anomalies.append(f"Header '{col_clean}' contains numeric entries. Identity semantic preserved; arithmetic aggregation forbidden.")
                    catalog.anomalies.extend(anomalies)

            aliases = [c_norm]
            if is_hr:
                aliases.append(f"Employee {col_clean}")

            catalog.fields[col_clean] = SemanticField(
                name=col_clean,
                field_role='identity',
                business_label=col_clean,
                aliases=aliases,
                grain=detected_grain,
                aggregation_rule='do_not_aggregate',
                direction_of_concern='neutral',
                confidence=1.0,
                governance_notes=anomalies
            )
            continue

        # 2. Period column check (e.g. '1st to 5th July', 'Leaves(1st to 5th July)')
        if is_period_header(col_clean):
            is_leave = 'leave' in c_lower or 'absent' in c_lower or 'off' in c_lower
            metric_type = 'Approved Leave Days' if is_leave else 'Attended Days'
            dir_concern: DirectionOfConcern = 'higher_is_worse' if is_leave else 'lower_is_worse'
            catalog.fields[col_clean] = SemanticField(
                name=col_clean,
                field_role='period',
                business_label=col_clean,
                aliases=[c_norm, f"{metric_type} ({col_clean})"],
                units='days',
                grain='employee_period',
                valid_range=(0.0, 31.0),
                aggregation_rule='sum',
                direction_of_concern=dir_concern,
                confidence=0.95
            )
            continue

        # 3. Derived totals and specific HR measures (Checked before dimension heuristics to prevent small fixtures misclassifying measures as dimensions)
        if 'final attendance' in c_norm or 'net attendance' in c_norm:
            notes = []
            if total_rows > 0 and col in df.columns:
                nums = pd.to_numeric(df[col], errors='coerce')
                neg_count = int((nums < 0).sum())
                if neg_count > 0:
                    notes.append(
                        f"Final Attendance contains {neg_count} negative observation(s) (minimum {nums.min()}). "
                        "Calculated as Total Attendance minus Approved Leaves. Negative balance reflects leave balance accounting, "
                        "not employee disciplinary underperformance. Marked as unresolved definition pending confirmed policy."
                    )
                    catalog.anomalies.extend(notes)
            catalog.fields[col_clean] = SemanticField(
                name=col_clean,
                field_role='derived_total',
                business_label='Final Attendance (Net Days)',
                aliases=['final attendance', 'net attendance', 'adjusted attendance'],
                units='days',
                grain='employee_month',
                valid_range=(None, 31.0),  # May have negative values as observed
                aggregation_rule='mean',
                direction_of_concern='lower_is_worse',
                confidence=0.9,
                unresolved_definition=True,
                governance_notes=notes
            )
            continue

        if 'total attendance' in c_norm or ('attendance' in c_norm and 'leave' not in c_norm and 'rate' not in c_norm):
            catalog.fields[col_clean] = SemanticField(
                name=col_clean,
                field_role='derived_total' if 'total' in c_norm else 'measure',
                business_label='Total Attended Days',
                aliases=['total attendance', 'attended days', 'monthly attendance', 'attendance'],
                units='days',
                grain='employee_month',
                valid_range=(0.0, 31.0),
                aggregation_rule='sum',
                direction_of_concern='lower_is_worse',
                confidence=0.95
            )
            continue

        if 'approved leave' in c_norm or 'total approved leave' in c_norm or 'total leave' in c_norm or ('leave' in c_norm and 'attendance' not in c_norm):
            catalog.fields[col_clean] = SemanticField(
                name=col_clean,
                field_role='derived_total',
                business_label='Approved Leave Days',
                aliases=['approved leaves', 'total approved leaves', 'leave days', 'leaves'],
                units='days',
                grain='employee_month',
                valid_range=(0.0, 31.0),
                aggregation_rule='sum',
                direction_of_concern='neutral',
                confidence=0.95
            )
            continue

        # 4. Explicit Categorical Dimension check (Department, Team, Status, Stage, Role, Location)
        is_dim = any(k in c_norm for k in ('department', 'dept', 'team', 'division', 'business unit', 'unit', 'location', 'status', 'stage', 'role', 'designation', 'category', 'band', 'grade'))
        if is_dim:
            aliases = [c_norm]
            if is_hr:
                aliases.append(f"Employee {col_clean}")
            catalog.fields[col_clean] = SemanticField(
                name=col_clean,
                field_role='dimension',
                business_label=col_clean,
                aliases=aliases,
                grain=detected_grain,
                aggregation_rule='distinct_count',
                direction_of_concern='neutral',
                confidence=0.95
            )
            continue

        # General numeric measure fallback
        if total_rows > 0 and col in df.columns:
            nums = pd.to_numeric(df[col], errors='coerce').dropna()
            if len(nums) >= total_rows * 0.4:
                catalog.fields[col_clean] = SemanticField(
                    name=col_clean,
                    field_role='measure',
                    business_label=col_clean,
                    aliases=[c_norm],
                    units=None,
                    grain=detected_grain,
                    valid_range=None,
                    aggregation_rule='mean',
                    direction_of_concern='neutral',
                    confidence=0.75
                )
                continue

        # Default fallback
        catalog.fields[col_clean] = SemanticField(
            name=col_clean,
            field_role='dimension',
            business_label=col_clean,
            aliases=[c_norm],
            grain=detected_grain,
            aggregation_rule='distinct_count',
            direction_of_concern='neutral',
            confidence=0.5,
            unresolved_definition=True
        )
        catalog.unresolved_count += 1

    return catalog
