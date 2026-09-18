-- Schema for PulseHR AI Tabular & Attendance Intelligence Platform

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    employee_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL,
    start_time TEXT DEFAULT '09:00',
    end_time TEXT DEFAULT '17:00',
    total_days INTEGER DEFAULT 0,
    present_days INTEGER DEFAULT 0,
    late_days INTEGER DEFAULT 0,
    attendance_rate REAL DEFAULT 0.0,
    punctuality_rate REAL DEFAULT 0.0,
    avg_daily_hours REAL DEFAULT 8.0,
    overtime_hours REAL DEFAULT 0.0,
    rating REAL DEFAULT 3.0,
    attrition_risk TEXT DEFAULT 'Low',
    tenure_years REAL DEFAULT 2.0,
    salary_band TEXT DEFAULT 'Mid',
    status TEXT DEFAULT 'Active',
    summary_profile TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department);
CREATE INDEX IF NOT EXISTS idx_employees_rating ON employees(rating);
CREATE INDEX IF NOT EXISTS idx_employees_risk ON employees(attrition_risk);

CREATE TABLE IF NOT EXISTS attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    clock_in TEXT,
    clock_out TEXT,
    duration_hours REAL,
    is_late INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Present'
);

CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance_records(employee_id, date);

CREATE TABLE IF NOT EXISTS dataset_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    sheet_count INTEGER DEFAULT 1,
    row_count INTEGER DEFAULT 0,
    col_count INTEGER DEFAULT 0,
    columns_json TEXT,
    sample_preview_json TEXT,
    summary_insights TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tabular_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER REFERENCES dataset_uploads(id) ON DELETE CASCADE,
    sheet_name TEXT DEFAULT 'Sheet1',
    row_index INTEGER,
    chunk_text TEXT NOT NULL,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hr_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    severity TEXT NOT NULL, -- 'high', 'warning', 'info'
    category TEXT NOT NULL, -- 'burnout', 'attendance_drop', 'rating_disconnect', 'retention'
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    employee_id INTEGER REFERENCES employees(id),
    metric_value REAL,
    is_resolved INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_severity ON hr_alerts(severity);
