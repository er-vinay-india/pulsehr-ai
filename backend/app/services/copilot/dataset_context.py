"""Resolve current HighView analytical state without copying rows into model prompts."""
from dataclasses import dataclass, field
import json
import pandas as pd
from ...db.database import get_connection
from ..data_engine.analysis_context import AnalysisContext


@dataclass
class DatasetContext:
    dataset_id: int
    sheet_id: int
    name: str
    sheet_name: str
    record_count: int
    columns: list[str]
    column_profiles: list[dict] = field(default_factory=list)
    eda: dict = field(default_factory=dict)
    analytical_views: list[dict] = field(default_factory=list)
    snapshot_id: str | None = None
    analysis_context: AnalysisContext | None = None
    context_error: str | None = None
    _frame: pd.DataFrame | None = field(default=None, repr=False)

    def binding(self):
        return {'dataset_id': self.dataset_id, 'sheet_id': self.sheet_id, 'dataset_name': self.name,
                'record_count': self.record_count, 'snapshot_id': self.snapshot_id}

    def compact(self):
        return {**self.binding(), 'columns': self.columns[:80],
                'column_profiles': [{k: p[k] for k in ('column', 'display_name', 'numeric', 'unit', 'missing', 'distinct') if k in p}
                                    for p in self.column_profiles[:40]],
                'key_metrics': self.eda.get('summary', {}), 'analytical_views': self.analytical_views[:10],
                'available_capabilities': ['verified_facts', 'profiles', 'aggregation', 'comparison', 'drilldown', 'charts']}

    def frame(self):
        # Existing analytics execute on the server; never send this frame to a model.
        if self._frame is None:
            if self.record_count > 20000:
                raise ValueError('On-demand analysis exceeds the existing 20,000-record interactive query budget.')
            with get_connection() as conn:
                rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (self.sheet_id,)).fetchall()
            self._frame = pd.DataFrame([json.loads(r['data_json']) for r in rows], columns=self.columns)
        return self._frame


class DatasetContextProvider:
    @staticmethod
    def resolve(dataset_id=None, sheet_id=None):
        with get_connection() as conn:
            sql = 'SELECT s.*, d.analysis_context_json AS dataset_context FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id'
            args = []
            if sheet_id is not None:
                sql += ' WHERE s.id=?'; args.append(sheet_id)
                if dataset_id is not None:
                    sql += ' AND s.dataset_id=?'; args.append(dataset_id)
            elif dataset_id is not None:
                sql += ' WHERE s.dataset_id=?'; args.append(dataset_id)
            sql += ' ORDER BY s.id DESC LIMIT 1'
            sheet = conn.execute(sql, args).fetchone()
            if sheet is None:
                return None
            count = conn.execute('SELECT COUNT(*) FROM sheet_rows WHERE sheet_id=?', (sheet['id'],)).fetchone()[0]
            result = DatasetContext(sheet['dataset_id'], sheet['id'], sheet['display_name'] or sheet['name'], sheet['name'], count, [])
            # A metadata/retrieval failure does not mean the dataset is absent.
            try:
                result.columns = json.loads(sheet['columns_json'] or '[]')
                result.column_profiles = json.loads(sheet['profile_json'] or '[]')
                raw = sheet['analysis_context_json'] or sheet['dataset_context']
                if raw:
                    result.analysis_context = AnalysisContext.model_validate_json(raw)
                row = conn.execute('SELECT report_json, snapshot FROM eda_reports WHERE sheet_id=? ORDER BY id DESC LIMIT 1', (sheet['id'],)).fetchone()
                if row:
                    result.eda = json.loads(row['report_json'])
                    result.snapshot_id = row['snapshot'] or result.eda.get('snapshot')
                views = conn.execute('SELECT id, name, source_sheets_json, columns_json, row_count FROM derived_tables ORDER BY id DESC LIMIT 100').fetchall()
                result.analytical_views = [{'id': v['id'], 'name': v['name'], 'columns': json.loads(v['columns_json']), 'record_count': v['row_count']}
                                           for v in views if sheet['id'] in json.loads(v['source_sheets_json'] or '[]')]
            except (ValueError, TypeError, KeyError) as exc:
                result.context_error = type(exc).__name__
            return result
