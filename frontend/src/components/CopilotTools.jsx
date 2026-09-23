import React, { useEffect, useState } from 'react';
import { listDatasets, getCalculationColumns, getSheets } from '../api/client';

export default function CopilotTools({ loading, onRun }) {
  const [open, setOpen] = useState(false);
  const [datasets, setDatasets] = useState([]);
  const [dataset, setDataset] = useState('');
  const [sheet, setSheet] = useState('');
  const [relationships, setRelationships] = useState([]);
  const [relationship, setRelationship] = useState('');
  const [columns, setColumns] = useState([]);
  const [operation, setOperation] = useState('mean');
  const [column, setColumn] = useState('');
  const [group, setGroup] = useState('');
  const [filterColumn, setFilterColumn] = useState('');
  const [filterValue, setFilterValue] = useState('');
  const [error, setError] = useState('');
  const [fetching, setFetching] = useState(false);
  useEffect(() => {
    if (open) {
      listDatasets().then(r => setDatasets(r.datasets || [])).catch(e => setError(e.message));
      getSheets().then(r => setRelationships(r.relationships.filter(x => x.status === 'linked'))).catch(e => setError(e.message));
    }
  }, [open]);
  useEffect(() => {
    if (!open) return;
    if ((!dataset && !relationship) || (dataset && !sheet)) {
      setColumns([]); setColumn(''); setGroup(''); setFilterColumn(''); setError(''); setFetching(false);
      return;
    }
    let active = true;
    setFetching(true);
    setColumns([]); setColumn(''); setGroup(''); setFilterColumn(''); setError('');
    getCalculationColumns(dataset, sheet, relationship).then(r => {
      if (active) { setColumns(r.columns); setColumn(r.columns.includes('attendance_rate') ? 'attendance_rate' : r.columns[0] || ''); }
    }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setFetching(false); });
    return () => { active = false; };
  }, [open, dataset, sheet, relationship]);
  const run = (name) => onRun(`${name === 'presentation' ? 'Create a presentation of' : 'Calculate'} ${operation} of ${operation === 'count' ? 'rows' : column}${group ? ` by ${group}` : ''}`, {
    name,
    calculation: { dataset_id: relationship ? null : dataset ? Number(dataset) : null, sheet: relationship ? null : sheet || null, relationship_id: relationship ? Number(relationship) : null, operation,
      column: operation === 'count' ? null : column, group_by: group || null,
      filter_column: filterColumn || null, filter_value: filterColumn ? filterValue : null }
  });
  const fields = (placeholder) => <><option value="">{placeholder}</option>{columns.map(c => <option key={c} value={c}>{c}</option>)}</>;
  return (
    <div className="copilot-tools">
      <div className="chips-row">
        <button
          type="button"
          className="chip-btn"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-controls="copilot-verified-calculations"
        >
          {open ? 'Hide calculation builder' : 'Calculate from data'}
        </button>
        <button
          type="button"
          className="chip-btn"
          disabled={loading}
          onClick={() => onRun('Create a presentation', { name: 'presentation' })}
        >
          Create sheet PowerPoint
        </button>
      </div>
      {open && (
        <fieldset
          id="copilot-verified-calculations"
          disabled={loading}
          className="copilot-tools-fieldset"
          style={{
            margin: '12px 0',
            padding: 16,
            border: '1px solid var(--border-strong, #473f38)',
            borderRadius: 10,
            background: 'rgba(23, 20, 17, 0.95)',
            maxHeight: '40vh',
            overflowY: 'auto'
          }}
        >
          <legend style={{ fontWeight: 700, color: '#f8fafc', padding: '0 6px', fontSize: '0.85rem' }}>
            Verified calculations
          </legend>
          <p style={{ color: 'var(--fg-secondary, #d7c5b5)', fontSize: '0.82rem', margin: '4px 0 14px 0', lineHeight: 1.5 }}>
            Choose a full data source. Count counts rows; averages exclude missing values. Joined rows can repeat a source value, so choose the appropriate measure.
          </p>
          <div className="calculation-fields">
            <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
              Source
              <select
                aria-label="Select data source"
                value={dataset}
                onChange={e => {
                  setDataset(e.target.value);
                  const chosen = datasets.find(d => String(d.id) === e.target.value);
                  setSheet(chosen?.sheets?.length === 1 ? chosen.sheets[0].name : '');
                  setRelationship('');
                }}
              >
                <option value="">Choose a source</option>
                {datasets.map(d => (
                  <option key={d.id} value={d.id}>
                    {d.original_name || d.filename}
                  </option>
                ))}
              </select>
            </label>
            {dataset && (
              <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
                Sheet
                <select
                  aria-label="Select sheet"
                  value={sheet}
                  onChange={e => setSheet(e.target.value)}
                >
                  <option value="">Choose a sheet</option>
                  {(datasets.find(d => String(d.id) === dataset)?.sheets || []).map(s => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
              Or connected view
              <select
                aria-label="Select connected view"
                value={relationship}
                onChange={e => {
                  setRelationship(e.target.value);
                  setDataset('');
                  setSheet('');
                }}
              >
                <option value="">No join</option>
                {relationships.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.left_file} [{r.left_column}] ↔ {r.right_file} [{r.right_column}]
                  </option>
                ))}
              </select>
            </label>
            <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
              Operation
              <select
                aria-label="Select operation"
                value={operation}
                onChange={e => setOperation(e.target.value)}
              >
                {['count', 'sum', 'mean', 'min', 'max', 'median'].map(o => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </label>
            {operation !== 'count' && (
              <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
                Column
                <select
                  aria-label="Select column"
                  value={column}
                  onChange={e => setColumn(e.target.value)}
                >
                  {fields('Choose column')}
                </select>
              </label>
            )}
            <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
              Group by
              <select
                aria-label="Group by column"
                value={group}
                onChange={e => setGroup(e.target.value)}
              >
                {fields('All rows')}
              </select>
            </label>
            <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
              Filter column
              <select
                aria-label="Filter column"
                value={filterColumn}
                onChange={e => setFilterColumn(e.target.value)}
              >
                {fields('No filter')}
              </select>
            </label>
            {filterColumn && (
              <label style={{ color: 'var(--fg-secondary, #d7c5b5)', fontWeight: 600 }}>
                Equals
                <input
                  aria-label="Filter equals value"
                  value={filterValue}
                  onChange={e => setFilterValue(e.target.value)}
                  placeholder="Enter filter value..."
                />
              </label>
            )}
          </div>
          {error && <p role="alert" style={{ color: '#f87171', fontSize: '0.82rem', marginTop: 10 }}>{error}</p>}
          {fetching && <p role="status" style={{ color: '#38bdf8', fontSize: '0.82rem', marginTop: 10 }}>Reading source columns…</p>}
          <div className="chips-row" style={{ marginTop: 14 }}>
            <button
              type="button"
              className="chip-btn"
              disabled={fetching || !!error || !columns.length || (operation !== 'count' && !column)}
              onClick={() => run('calculate')}
              style={{ fontWeight: 600, color: '#f8fafc' }}
            >
              Calculate
            </button>
            <button
              type="button"
              className="chip-btn"
              disabled={fetching || !!error || !columns.length || (operation !== 'count' && !column)}
              onClick={() => run('presentation')}
              style={{ fontWeight: 600, color: '#f8fafc' }}
            >
              Download calculation as PowerPoint
            </button>
          </div>
        </fieldset>
      )}
    </div>
  );
}
