import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Layers,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  UploadCloud,
  FileQuestion,
  Database
} from 'lucide-react';

export default function DataCompletenessChips({
  dataHealth,
  sheetName = 'Current Sheet',
  onReupload
}) {
  const [showDetails, setShowDetails] = useState(false);

  if (!dataHealth) return null;

  const {
    totalRows = 0,
    totalCols = 0,
    totalNullCells = 0,
    nullPct = 0,
    completenessPct = 100,
    incompleteRows = 0,
    incompleteRowsPct = 0,
    colsWithNulls = [],
    typeBreakdown = {},
    healthScore = 100,
    isClean = true,
    columnList = []
  } = dataHealth;

  const handleUploadClick = () => {
    if (onReupload) {
      onReupload();
    } else {
      window.location.hash = 'upload';
    }
  };

  const numericCount = typeBreakdown.numeric || 0;
  const categoricalCount = typeBreakdown.categorical || 0;
  const datetimeCount = typeBreakdown.datetime || 0;
  const identifierCount = typeBreakdown.identifier || 0;

  return (
    <div className="data-completeness-container">
      {/* 1. Incomplete Sheet Alert Ribbon when nulls are found */}
      {!isClean && (
        <div className="incomplete-sheet-alert-ribbon" role="alert">
          <div className="alert-ribbon-left">
            <div className="alert-ribbon-icon">
              <AlertTriangle size={20} color="#f43f5e" />
            </div>
            <div className="alert-ribbon-text">
              <div className="alert-ribbon-title">
                Incomplete Sheet Uploaded: {totalNullCells.toLocaleString()} Missing / Null Values Detected
              </div>
              <div className="alert-ribbon-desc">
                {colsWithNulls.length} column{colsWithNulls.length > 1 ? 's' : ''} affected across{' '}
                {incompleteRows.toLocaleString()} row{incompleteRows > 1 ? 's' : ''} ({incompleteRowsPct}% of rows).
                Downstream statistical aggregations or predictive models will use automated imputations.
                If this data was incomplete by mistake, please upload a corrected sheet.
              </div>
            </div>
          </div>
          <button
            type="button"
            className="btn-upload-corrected"
            onClick={handleUploadClick}
            title="Open upload dialog to upload a corrected spreadsheet"
          >
            <UploadCloud size={15} />
            <span>Upload Corrected Sheet</span>
          </button>
        </div>
      )}

      {/* 2. Prominent Big Font Highlight Chips */}
      <div className="completeness-chips-row" role="region" aria-label="Dataset Completeness and Type Summary">
        {/* CHIP 1: Missing / Null Values (Prominent Warning or Success) */}
        <div
          className={`big-stat-chip ${isClean ? 'chip-state-clean' : 'chip-state-warning'}`}
          title={isClean ? 'No missing cells found' : `${totalNullCells} null cells in dataset`}
        >
          <div className="chip-header">
            <span className="chip-tag-label">Missing Values</span>
            {isClean ? (
              <CheckCircle2 size={16} color="#10b981" />
            ) : (
              <AlertTriangle size={16} color="#f43f5e" />
            )}
          </div>
          <div className="chip-primary-metric">
            {isClean ? (
              <span className="metric-big text-clean">0 Missing</span>
            ) : (
              <span className="metric-big text-warning">
                {totalNullCells.toLocaleString()} Nulls
              </span>
            )}
            <span className="metric-sub-pct">
              {isClean ? '(100% Complete)' : `(${nullPct}% Null)`}
            </span>
          </div>
          <div className="chip-footer-caption">
            {isClean ? (
              '100% data density · Perfect matrix'
            ) : (
              `${colsWithNulls.length} column${colsWithNulls.length > 1 ? 's' : ''} with null values`
            )}
          </div>
        </div>

        {/* CHIP 2: Incomplete Rows */}
        <div
          className={`big-stat-chip ${incompleteRows === 0 ? 'chip-state-clean' : 'chip-state-warning'}`}
          title={`${incompleteRows} rows contain at least one null value`}
        >
          <div className="chip-header">
            <span className="chip-tag-label">Incomplete Rows</span>
            <FileQuestion size={16} color={incompleteRows === 0 ? '#10b981' : '#fb923c'} />
          </div>
          <div className="chip-primary-metric">
            <span className={`metric-big ${incompleteRows === 0 ? 'text-clean' : 'text-warning-amber'}`}>
              {incompleteRows.toLocaleString()}
            </span>
            <span className="metric-sub-pct">
              / {totalRows.toLocaleString()} rows ({incompleteRowsPct}%)
            </span>
          </div>
          <div className="chip-footer-caption">
            {incompleteRows === 0
              ? 'Every row has complete fields'
              : `${(totalRows - incompleteRows).toLocaleString()} rows fully populated`}
          </div>
        </div>

        {/* CHIP 3: Data Types Information Breakdown */}
        <div className="big-stat-chip chip-state-types" title="Inferred data types distribution">
          <div className="chip-header">
            <span className="chip-tag-label">Data Types Breakdown</span>
            <Layers size={16} color="#60a5fa" />
          </div>
          <div className="chip-primary-metric">
            <span className="metric-big text-types">
              {numericCount} Num · {categoricalCount} Cat
              {datetimeCount > 0 ? ` · ${datetimeCount} Date` : ''}
              {identifierCount > 0 ? ` · ${identifierCount} ID` : ''}
            </span>
          </div>
          <div className="chip-footer-caption">
            {totalCols} columns typed & profiled
          </div>
        </div>

        {/* CHIP 4: Data Health Score & Completeness */}
        <div className="big-stat-chip chip-state-health" title="Overall statistical data quality score">
          <div className="chip-header">
            <span className="chip-tag-label">Ingestion Health Score</span>
            <ShieldCheck
              size={16}
              color={healthScore >= 80 ? '#10b981' : healthScore >= 60 ? '#fb923c' : '#f43f5e'}
            />
          </div>
          <div className="chip-primary-metric">
            <span
              className={`metric-big ${
                healthScore >= 80 ? 'text-clean' : healthScore >= 60 ? 'text-warning-amber' : 'text-warning'
              }`}
            >
              {healthScore}/100
            </span>
            <span className="metric-sub-pct">({completenessPct}% Dense)</span>
          </div>
          <div className="chip-footer-caption">
            {healthScore >= 85 ? 'Production Grade Hygiene' : 'Contains Nulls / Coercions'}
          </div>
        </div>
      </div>

      {/* 3. Expandable Column Types & Missing Details Drawer Toggle */}
      {columnList.length > 0 && (
        <div className="completeness-details-toggle-bar">
          <button
            type="button"
            className="btn-details-toggle"
            onClick={() => setShowDetails((prev) => !prev)}
            aria-expanded={showDetails}
          >
            <Database size={14} />
            <span>
              {showDetails ? 'Hide' : 'Inspect'} Column Types & Null Distribution ({columnList.length} Columns)
            </span>
            {showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {showDetails && (
            <div className="column-types-detail-grid">
              {columnList.map((col, idx) => {
                const hasNull = (col.null_count || 0) > 0;
                const typeStr = col.inferred_type || (col.numeric ? 'numeric' : 'categorical');
                return (
                  <div
                    key={idx}
                    className={`col-type-card ${hasNull ? 'has-null-values' : 'all-values-clean'}`}
                  >
                    <div className="col-type-header">
                      <span className="col-name" title={col.column}>
                        {col.column}
                      </span>
                      <span className={`col-type-badge badge-${typeStr.split('_')[0]}`}>
                        {typeStr.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="col-type-stat-row">
                      {hasNull ? (
                        <span className="col-null-warn">
                          ⚠️ {col.null_count} nulls ({col.null_percentage}%)
                        </span>
                      ) : (
                        <span className="col-null-ok">✓ 100% complete</span>
                      )}
                      {col.distinct_count != null && (
                        <span className="col-distinct-sub">
                          {col.distinct_count} distinct
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
