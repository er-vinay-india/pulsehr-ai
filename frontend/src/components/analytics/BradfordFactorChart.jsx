import React from 'react';

export default function BradfordFactorChart({ data, onInvestigate }) {
  const departments = data?.departments || [];
  const maxScore = Math.max(...departments.map((d) => d.avg_bradford_score || 0), 250);

  return (
    <div className="bradford-spectrum-container">
      <div className="bradford-tiers-legend">
        <span className="tier-tag tier-normal">● &lt; 50: Normal</span>
        <span className="tier-tag tier-moderate">● 51–200: Moderate</span>
        <span className="tier-tag tier-high">● 201–500: High Disruption</span>
        <span className="tier-tag tier-critical">● &gt; 500: Critical Escalation</span>
      </div>

      <div className="bradford-dept-list">
        {departments.map((dept, idx) => {
          const score = dept.avg_bradford_score;
          const barWidthPct = Math.min(100, Math.max(8, (score / maxScore) * 100));

          let tierColor = '#10b981';
          let tierLabel = 'Normal';
          if (score > 500) { tierColor = '#f43f5e'; tierLabel = 'Critical Disruption'; }
          else if (score > 200) { tierColor = '#f59e0b'; tierLabel = 'High Disruption'; }
          else if (score > 50) { tierColor = '#06b6d4'; tierLabel = 'Moderate'; }

          return (
            <div
              key={idx}
              className="bradford-dept-row interactive-row"
              onClick={() =>
                onInvestigate &&
                onInvestigate({
                  entityType: 'department',
                  targetId: dept.department,
                  metric: 'Absent ( no of days )'
                })
              }
              title={`Click to investigate ${dept.department} department absence records`}
            >
              <div className="dept-label-col">
                <span className="dept-name">{dept.department}</span>
                <span className="dept-headcount">{dept.headcount} staff · {dept.total_absent_days}d lost</span>
              </div>
              <div className="dept-bar-track">
                <div
                  className="dept-bar-fill"
                  style={{ width: `${barWidthPct}%`, backgroundColor: tierColor }}
                >
                  <span className="bar-val-text">{score} pts</span>
                </div>
              </div>
              <div className="dept-tier-badge" style={{ color: tierColor, borderColor: `${tierColor}55` }}>
                {tierLabel}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
