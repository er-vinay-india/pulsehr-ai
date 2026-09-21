import React from 'react';

export default function BurnoutStrainChart({ data, onInvestigate }) {
  const departments = data?.departments || [];

  return (
    <div className="burnout-strain-container">
      <div className="strain-header-note">
        <span>Sustainable Strain Threshold: <strong>&lt; 10%</strong></span>
        <span style={{ color: '#f43f5e', fontWeight: 600 }}>Critical Burnout Limit: <strong>&gt; 20%</strong></span>
      </div>

      <div className="strain-dept-grid">
        {departments.map((dept, idx) => {
          const strain = dept.strain_index_pct;
          const isCritical = strain >= 20.0;
          const isElevated = strain >= 10.0 && strain < 20.0;

          return (
            <div
              key={idx}
              className={`strain-dept-card interactive-card ${isCritical ? 'critical' : (isElevated ? 'elevated' : 'sustainable')}`}
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: 'department',
                  targetId: dept.department,
                  metric: 'Overtime Hours'
                })
              }
              title={`Click to investigate workload in ${dept.department}`}
            >
              <div className="card-top">
                <span className="dept-title">{dept.department}</span>
                <span className="strain-badge" style={{ backgroundColor: dept.status_color }}>
                  {dept.status}
                </span>
              </div>
              <div className="strain-metric-val">
                <span className="big-pct">{strain}%</span>
                <span className="metric-label">Workload Strain</span>
              </div>
              <div className="strain-factors-list">
                <div className="factor-row">
                  <span>Avg Overtime:</span>
                  <strong>{dept.avg_overtime_hours} hrs/mo</strong>
                </div>
                <div className="factor-row">
                  <span>Total Absences:</span>
                  <strong>{dept.total_absent_days} days</strong>
                </div>
                <div className="factor-row">
                  <span>Staff Headcount:</span>
                  <strong>{dept.headcount} staff</strong>
                </div>
              </div>
              <div className="card-click-prompt">Click to view source evidence →</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
