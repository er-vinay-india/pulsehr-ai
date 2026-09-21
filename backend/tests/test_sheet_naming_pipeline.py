import pytest
from app.services.sheet_naming_pipeline import (
    sanitize_filename_string,
    is_meaningless_or_noise,
    detect_person_name,
    infer_from_columns_and_sample,
    proper_title_case,
    generate_sheet_display_name
)


def test_sanitize_filename_string():
    assert sanitize_filename_string("employee_performance_data_copy(1).csv") == "employee performance data"
    assert sanitize_filename_string("employee_absent_data_copy_2.xlsx") == "employee absent data"
    assert sanitize_filename_string("sales_q3_final_v2.csv") == "sales q3"
    assert sanitize_filename_string("Kaggle_ Employee Attendance & Performance Ratings (yasirub_employee-attendance-ratings).csv") == "Employee Attendance & Performance Ratings"
    assert sanitize_filename_string("enc_9849204_draft.csv") == "enc 9849204"


def test_is_meaningless_or_noise():
    # Noise/Meaningless
    assert is_meaningless_or_noise("1689239842") is True
    assert is_meaningless_or_noise("20230101") is True
    assert is_meaningless_or_noise("76194746933b43b38866ba4a82b2f03b") is True
    assert is_meaningless_or_noise("enc_8492819") is True
    assert is_meaningless_or_noise("Sheet1") is True
    assert is_meaningless_or_noise("data") is True
    assert is_meaningless_or_noise("export_temp") is True

    # Meaningful
    assert is_meaningless_or_noise("employee performance data") is False
    assert is_meaningless_or_noise("sales operations") is False
    assert is_meaningless_or_noise("attendance records") is False


def test_detect_person_name():
    assert detect_person_name("Person 77") == "Person 77"
    assert detect_person_name("Person_0") == "Person 0"
    assert detect_person_name("Employee_104") == "Person 104"
    assert detect_person_name("John Smith") == "John Smith"
    # Should not match common business domains
    assert detect_person_name("employee performance") is None
    assert detect_person_name("sales operations") is None


def test_infer_from_columns_and_sample_attendance():
    cols = ["Date"] + [f"Person_{i}" for i in range(20)]
    sample = [{"Date": "2023-01-01", "Person_0": "08:43-16:42", "Person_1": "09:01-16:43"}]
    name, domain, desc = infer_from_columns_and_sample(cols, sample)
    assert name == "Daily Attendance & Time Tracking Logs"
    assert domain == "Attendance & Working Hours"


def test_infer_from_columns_and_sample_performance():
    cols = ["Employee_ID", "Department", "Performance_Score", "Review_Date"]
    name, domain, desc = infer_from_columns_and_sample(cols, [])
    assert name == "Employee Performance & Review Records"
    assert domain == "Performance & Talent Appraisal"


def test_infer_from_columns_and_sample_absence():
    cols = ["Emp_ID", "Department", "Absent_Days", "Sick_Leave"]
    name, domain, desc = infer_from_columns_and_sample(cols, [])
    assert name == "Employee Absence & Leave Records"
    assert domain == "Attendance & Working Hours"


def test_proper_title_case():
    assert proper_title_case("employee_performance_data") == "Employee Performance Data"
    assert proper_title_case("DAILY ATTENDANCE LOGS") == "Daily Attendance Logs"
    assert proper_title_case("hr kpi performance score") == "HR KPI Performance Score"
    assert proper_title_case("workforce in the office of hr") == "Workforce in the Office of HR"


def test_generate_sheet_display_name_pipeline():
    # 1. Wide attendance matrix with messy filename
    res1 = generate_sheet_display_name(
        "Kaggle_ Employee Attendance & Performance Ratings (yasirub_employee-attendance-ratings)_copy(1).csv",
        columns=["Date"] + [f"Person_{i}" for i in range(50)],
        sample_records=[{"Date": "2023-01-01", "Person_0": "08:43-16:42"}]
    )
    assert res1["display_name"] == "Daily Attendance & Time Tracking Logs"
    assert res1["domain"] == "Attendance & Working Hours"

    # 2. Performance file with underscores and copy tag
    res2 = generate_sheet_display_name(
        "employee_performance_data_copy(2).csv",
        columns=["Employee_ID", "Department", "Performance_Score"]
    )
    assert "Employee Performance" in res2["display_name"]

    # 3. Meaningless numeric hash file with absence columns
    res3 = generate_sheet_display_name(
        "enc_8492048102.xlsx",
        columns=["Emp_ID", "Department", "Sick_Leave", "Casual_Leave"]
    )
    assert res3["display_name"] == "Employee Absence & Leave Records"

    # 4. Person name file
    res4 = generate_sheet_display_name(
        "Person_77_records.csv",
        columns=["Date", "Clock_In", "Clock_Out"]
    )
    assert "Person 77" in res4["display_name"]
