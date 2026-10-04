"""Migration script: Normalizes dates to ISO-8601, profiles cadence, and generates macro-temporal chunks."""
import json
import logging
import sqlite3
import pandas as pd
from pathlib import Path

from backend.app.core import config
from backend.app.services.data_engine.semantic_classifier import SemanticClassifier
from backend.app.services.sheet_catalog import model_embeddings
from backend.app.services.rag_service import pack_vector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from backend.app.db.database import get_connection


def migrate_database():
    logger.info("Connecting to database via get_connection()...")
    conn = get_connection()

    sheets = conn.execute("SELECT * FROM sheets").fetchall()
    logger.info(f"Found {len(sheets)} sheets to evaluate.")

    for sheet in sheets:
        sid = sheet["id"]
        sname = sheet["name"]
        dataset_id = sheet["dataset_id"]
        logger.info(f"Processing sheet {sid}: '{sname}'...")

        rows = conn.execute("SELECT row_index, data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index", (sid,)).fetchall()
        if not rows:
            continue

        records = [json.loads(r["data_json"]) for r in rows]
        df = pd.DataFrame(records)
        cols = list(df.columns)

        temporal_meta = {}
        for col in cols:
            is_dt, _, _ = SemanticClassifier._is_date(df[col], str(col))
            if is_dt:
                parsed_dt, is_df, info = SemanticClassifier.detect_and_parse_datetime_series(df[col])
                if parsed_dt is not None and info:
                    iso_dates = parsed_dt.dt.strftime('%Y-%m-%d').fillna('')
                    df[col] = iso_dates
                    temporal_meta[col] = info
                    logger.info(f"  Column '{col}': detected {info.get('summary')}")

        if not temporal_meta:
            logger.info(f"  No temporal columns in sheet {sid}.")
            continue

        # 1. Update sheet_rows with normalized ISO dates
        logger.info(f"  Updating {len(records)} rows in sheet_rows with ISO-8601 dates...")
        normalized_records = json.loads(df.to_json(orient='records', date_format='iso'))
        update_rows = [
            (json.dumps(normalized_records[i]), sid, i)
            for i in range(len(normalized_records))
        ]
        conn.executemany("UPDATE sheet_rows SET data_json=? WHERE sheet_id=? AND row_index=?", update_rows)

        # 2. Update sheet_cells for temporal columns
        for t_col in temporal_meta.keys():
            cell_updates = [
                (normalized_records[i][t_col], sid, i, t_col)
                for i in range(len(normalized_records))
                if normalized_records[i].get(t_col)
            ]
            if cell_updates:
                conn.executemany("UPDATE sheet_cells SET value_key=? WHERE sheet_id=? AND row_index=? AND column_name=?", cell_updates)

        # 3. Update sheet profile_json with temporal cadence & summary
        try:
            profs = json.loads(sheet["profile_json"] or "[]")
            for p in profs:
                if p["column"] in temporal_meta:
                    t_info = temporal_meta[p["column"]]
                    p["temporal_cadence"] = t_info.get("temporal_cadence")
                    p["cadence_interval_days"] = t_info.get("cadence_interval_days")
                    p["cadence_anchor"] = t_info.get("cadence_anchor")
                    p["min_date"] = t_info.get("min_date")
                    p["max_date"] = t_info.get("max_date")
                    p["temporal_summary"] = t_info.get("summary")
            conn.execute("UPDATE sheets SET profile_json=? WHERE id=?", (json.dumps(profs), sid))
        except Exception as e:
            logger.warning(f"  Could not update profile_json: {e}")

        # 4. Generate Macro-Temporal Chunks
        source_name = sheet["display_name"] or sname
        macro_chunks = []
        for t_col, t_info in temporal_meta.items():
            macro_chunks.append(
                f"Source: {source_name}; Sheet: {sname}; Column '{t_col}' Temporal Granularity: {t_info.get('summary')}"
            )
            # Monthly rollups
            try:
                dt_series = pd.to_datetime(df[t_col], errors='coerce')
                valid_mask = dt_series.notna()
                if valid_mask.sum() >= 4:
                    frame_temp = df[valid_mask].copy()
                    frame_temp['__month_dt'] = dt_series[valid_mask].dt.to_period('M')
                    frame_temp['__month_name'] = dt_series[valid_mask].dt.strftime('%B %Y')

                    num_cols = [c for c in cols if "sales" in c.lower() or "price" in c.lower() or "attendance" in c.lower()]
                    pri_num = num_cols[0] if num_cols else None
                    id_col = next((c for c in cols if "id" in c.lower() or "store" in c.lower()), None)

                    for _, m_grp in frame_temp.groupby('__month_dt'):
                        m_label = m_grp['__month_name'].iloc[0]
                        m_dates = sorted(m_grp[t_col].unique())
                        if not m_dates:
                            continue

                        cycle_desc = []
                        for d_val, d_grp in m_grp.groupby(t_col):
                            if pri_num:
                                d_num = pd.to_numeric(d_grp[pri_num].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').sum()
                                cycle_desc.append(f"{d_val} (total {pri_num}: ${d_num:,.2f})")
                            else:
                                cycle_desc.append(f"{d_val} ({len(d_grp)} rows)")

                        cycles_str = "; ".join(cycle_desc[:6])
                        m_summary = (
                            f"Source: {source_name}; Sheet: {sname}; Period: {m_label} ({m_dates[0]} to {m_dates[-1]}). "
                            f"Discrete cycles ({len(m_dates)} dates): {cycles_str}."
                        )
                        if pri_num:
                            total_val = pd.to_numeric(m_grp[pri_num].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').sum()
                            avg_val = pd.to_numeric(m_grp[pri_num].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').mean()
                            entity_count = m_grp[id_col].nunique() if id_col else len(m_grp)
                            m_summary += f" Monthly total {pri_num}: ${total_val:,.2f}, average: ${avg_val:,.2f} across {entity_count} entities."
                        macro_chunks.append(m_summary)
            except Exception as e:
                logger.warning(f"  Could not generate monthly rollups: {e}")

        logger.info(f"  Generated {len(macro_chunks)} macro-temporal chunks.")

        # Delete existing macro chunks for this sheet
        conn.execute("DELETE FROM tabular_chunks WHERE sheet_name=? AND row_index=-1", (sname,))

        # Insert new macro chunks
        macro_vectors = model_embeddings(macro_chunks)
        for c_idx, chunk_txt in enumerate(macro_chunks):
            metadata = {
                'dataset_id': dataset_id,
                'sheet_id': sid,
                'sheet_name': sname,
                'row_index': -1,
                'is_macro_summary': True
            }
            if c_idx < len(macro_vectors) and macro_vectors[c_idx]:
                metadata['embedding_model'] = config.OLLAMA_EMBED_MODEL

            chunk_id = conn.execute(
                'INSERT INTO tabular_chunks(dataset_id,sheet_name,row_index,chunk_text,metadata_json) VALUES (?,?,?,?,?)',
                (dataset_id, sname, -1, chunk_txt, json.dumps(metadata))
            ).lastrowid

            if c_idx < len(macro_vectors) and macro_vectors[c_idx]:
                conn.execute(
                    'INSERT INTO tabular_vectors(id,embedding) VALUES (?,?)',
                    (chunk_id, pack_vector(macro_vectors[c_idx]))
                )

        conn.commit()
        logger.info(f"  Successfully migrated sheet {sid} ({sname}).")

    conn.close()
    logger.info("Migration complete.")


if __name__ == "__main__":
    migrate_database()
