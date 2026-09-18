import json
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd

from ..core import config
from ..db.database import get_connection
from ..services.rag_service import index_uploaded_dataset
from ..services.kaggle_loader import load_and_seed_kaggle_dataset

router = APIRouter(prefix="/api/upload", tags=["upload"])

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

    # Inspect file structure
    try:
        sheets_data = {}
        if ext in [".xlsx", ".xls"]:
            xls = pd.ExcelFile(dest_path)
            sheet_names = xls.sheet_names
            for s in sheet_names:
                df = pd.read_excel(xls, sheet_name=s)
                sheets_data[s] = df
        else:
            df = pd.read_csv(dest_path)
            sheets_data["Sheet1"] = df

        first_sheet_name = list(sheets_data.keys())[0]
        primary_df = sheets_data[first_sheet_name]
        total_rows = sum(len(df) for df in sheets_data.values())
        columns = [str(c) for c in primary_df.columns]

        preview_records = primary_df.head(5).to_dict(orient="records")

        # Save record in database
        conn = get_connection()
        try:
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
                json.dumps(preview_records, default=str),
                f"Ingested {len(sheets_data)} sheet(s) with {total_rows} total rows and {len(columns)} columns."
            ))
            dataset_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        # Index vectors in background / synchronously
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
            "message": f"Successfully parsed and vectorized {indexed_chunks} rows into SQLite vector DB."
        }
    except Exception as e:
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
