"""Classification utilities for spreadsheet row entities."""

import re


def classify_row_entity(columns: list[str], sample_records: list[dict]) -> dict:
    """Determines what each row represents in the sheet."""
    cols_clean = [re.sub(r'[^a-zA-Z0-9]', '', str(c).lower()) for c in columns]

    has_date = any(k in cols_clean for k in ('date', 'timestamp', 'datetime', 'day', 'clockin', 'punchdate'))
    has_emp_id = any(k in cols_clean for k in ('employeeid', 'empid', 'employeecode', 'staffid', 'empcode'))
    has_candidate_id = any(k in cols_clean for k in ('candidateid', 'applicantid', 'requisitionid', 'applicationid'))
    has_salary = any(k in cols_clean for k in ('salary', 'compensation', 'basepay', 'payroll', 'wage'))
    has_perf = any(k in cols_clean for k in ('rating', 'performancescore', 'appraisal', 'kpiscore', 'score'))
    has_absent = any(k in cols_clean for k in ('absent', 'absence', 'leave', 'sickdays', 'daysabsent'))
    has_hours = any(k in cols_clean for k in ('hours', 'duration', 'overtime', 'clockout'))
    has_sales = any(k in cols_clean for k in ('sales', 'weeklysales', 'store', 'revenue', 'orders', 'transactions', 'product', 'retail'))
    has_store = any(k in cols_clean for k in ('store', 'storeid', 'branch', 'location'))

    if has_sales and has_date and has_store:
        entity_type = "store_sales_periodic"
        entity_label = "Store Weekly Sales Record"
        is_event_level = True
    elif has_sales and has_date:
        entity_type = "sales_periodic_record"
        entity_label = "Periodic Sales Transaction"
        is_event_level = True
    elif has_sales:
        entity_type = "sales_record"
        entity_label = "Commercial Sales Record"
        is_event_level = False
    elif has_candidate_id or any(k in cols_clean for k in ('candidate', 'applicant', 'stage', 'resume')):
        entity_type = "recruitment_application"
        entity_label = "Candidate Application"
        is_event_level = False
    elif has_date and (has_emp_id or has_hours or any(c.startswith('person') for c in cols_clean)):
        entity_type = "attendance_event"
        entity_label = "Daily Attendance Check-In"
        is_event_level = True
    elif has_emp_id and has_absent and not has_date:
        entity_type = "employee_absence_summary"
        entity_label = "Employee Absence Record"
        is_event_level = False
    elif has_emp_id and has_perf:
        entity_type = "employee_performance_record"
        entity_label = "Employee Performance Appraisal"
        is_event_level = False
    elif has_emp_id and has_salary:
        entity_type = "employee_compensation_record"
        entity_label = "Compensation Record"
        is_event_level = False
    elif has_emp_id:
        entity_type = "employee_record"
        entity_label = "Employee Master Record"
        is_event_level = False
    else:
        entity_type = "generic_tabular_record"
        entity_label = "Tabular Data Record"
        is_event_level = False

    return {
        "entity_type": entity_type,
        "entity_label": entity_label,
        "is_event_level": is_event_level,
        "has_unique_identifier": has_emp_id or has_candidate_id or has_store
    }
