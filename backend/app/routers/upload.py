import json
import math
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd

from ..core import config
from ..db.database import get_connection
from ..services.rag_service import index_uploaded_dataset
from ..services.kaggle_loader import load_and_seed_kaggle_dataset

router = APIRouter(prefix="/api/upload", tags=["upload"])


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans trailing empty columns, normalizes headers, and handles nulls safely."""
    # Drop columns that are completely empty
    df = df.dropna(axis=1, how="all")
    
    # Drop Unnamed columns with all nulls
    unnamed_empty = [c for c in df.columns if str(c).startswith("Unnamed") and df[c].isna().all()]
    if unnamed_empty:
        df = df.drop(columns=unnamed_empty)
    
    # Strip whitespace from string column names
    df.columns = [str(c).strip() for c in df.columns]
    return df


def sanitize_for_json(records: list[dict]) -> list[dict]:
    """Ensures no float('nan'), np.nan, or inf exists before json serialization."""
    sanitized = []
    for r in records:
        clean_row = {}
        for k, v in r.items():
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                clean_row[k] = ""
            elif pd.isna(v):
                clean_row[k] = ""
            else:
                clean_row[k] = v
        sanitized.append(clean_row)
    return sanitized


@router.post("/file")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename or "uploaded_data.csv"
    ext = Path(filename).suffix.lower()

    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file."
        )

    # Save file to uploads dir
    dest_path = config.UPLOADS_DIR / filename
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        sheets_data = {}
        if ext in [".xlsx", ".xls"]:
            xls = pd.ExcelFile(dest_path)
            for s in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=s)
                sheets_data[s] = clean_dataframe(df)
        else:
            # Try reading with multiple encodings
            df = None
            for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
                try:
                    df = pd.read_csv(dest_path, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise ValueError("Could not decode CSV with supported encodings (UTF-8, Latin-1, CP1252).")

            sheets_data["Sheet1"] = clean_dataframe(df)

        first_sheet_name = list(sheets_data.keys())[0]
        primary_df = sheets_data[first_sheet_name]
        total_rows = sum(len(df) for df in sheets_data.values())
        columns = [str(c) for c in primary_df.columns]

        # Clean head for preview
        raw_preview = primary_df.head(5).to_dict(orient="records")
        preview_records = sanitize_for_json(raw_preview)

        # Connect & match employees for semantic enrichment
        conn = get_connection()
        linked_employees_count = 0
        try:
            # Check if any column refers to Employee ID or Employee Name
            id_col = None
            for c in primary_df.columns:
                if c.lower().replace(" ", "").replace("_", "") in ["employeeid", "empid", "id", "code"]:
                    id_col = c
                    break
            
            if id_col:
                emp_codes = [str(val).strip() for val in primary_df[id_col].dropna().unique()]
                if emp_codes:
                    placeholders = ",".join(["?"] * len(emp_codes))
                    match_count = conn.execute(
                        f"SELECT COUNT(*) FROM employees WHERE employee_code IN ({placeholders})",
                        emp_codes
                    ).fetchone()[0]
                    linked_employees_count = match_count

            summary_note = (
                f"Ingested {len(sheets_data)} sheet(s) with {total_rows} total rows and {len(columns)} columns. "
            )
            if linked_employees_count > 0:
                summary_note += f"Semantically linked to {linked_employees_count} existing employee profile(s) for unified RAG reasoning."

            cursor = conn.execute("""
                INSERT INTO dataset_uploads (
                    filename, original_name, file_type, sheet_count, row_count, col_count,
                    columns_json, sample_preview_json, summary_insights
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dest_path.name,
                filename,
                ext.replace(".", ""),
                len(sheets_data),
                total_rows,
                len(columns),
                json.dumps(columns),
                json.dumps(preview_records),
                summary_note
            ))
            dataset_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        # Index vectors into SQLite
        indexed_chunks = index_uploaded_dataset(dataset_id, dest_path)

        return {
            "status": "success",
            "dataset_id": dataset_id,
            "filename": filename,
            "sheets": list(sheets_data.keys()),
            "total_rows": total_rows,
            "columns": columns,
            "sample_preview": preview_records,
            "indexed_chunks": indexed_chunks,
            "linked_employees": linked_employees_count,
            "message": f"Successfully parsed and vectorized {indexed_chunks} rows into SQLite vector DB." + (
                f" Linked with {linked_employees_count} employee profiles." if linked_employees_count else ""
            )
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")


@router.get("/datasets")
def list_datasets():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT id, filename, original_name, file_type, sheet_count, row_count, col_count,
                   columns_json, summary_insights, uploaded_at
            FROM dataset_uploads
            ORDER BY id DESC
        """).fetchall()

        results = []
        for r in rows:
            cols = []
            if r["columns_json"]:
                try:
                    cols = json.loads(r["columns_json"])
                except Exception:
                    pass
            results.append({
                "id": r["id"],
                "filename": r["filename"],
                "original_name": r["original_name"],
                "file_type": r["file_type"],
                "sheet_count": r["sheet_count"],
                "row_count": r["row_count"],
                "col_count": r["col_count"],
                "columns": cols,
                "summary_insights": r["summary_insights"],
                "uploaded_at": r["uploaded_at"]
            })
        return {"datasets": results}
    finally:
        conn.close()


@router.post("/reseed-kaggle")
def reseed_kaggle():
    res = load_and_seed_kaggle_dataset(force=True)
    return {"message": "Kaggle attendance & ratings dataset re-seeded successfully", "details": res}
