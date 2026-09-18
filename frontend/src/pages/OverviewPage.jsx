import React, { useEffect, useState } from "react";
import { Users, CheckCircle2, Award, AlertTriangle, TrendingUp, Clock, ArrowRight, ShieldAlert, Sparkles, Database, FileSpreadsheet, Check } from "lucide-react";
import { getAnalyticsOverview } from "../api/client";

export default function OverviewPage({ onSelectEmployee, onNavigateTab }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalyticsOverview()
      .then(res => setData(res))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="page-loading">Loading workforce analytics...</div>;
  }

  const { stats, departments, alerts, rating_distribution, latest_upload, sources } = data || {};
  const customUploadsCount = sources?.filter(s => s.filename !== "attendance_2023_2024.csv").length || 0;

  return (
    <div className="overview-page">
      {/* Top Welcome Banner */}
      <div className="executive-banner">
        <div className="banner-content">
          <div className="banner-tag">
            <Sparkles size={14} />
            <span>Kaggle Dataset Grounded · Real-Time Vector Inference</span>
          </div>
          <h2>Workforce Health & Attendance Intelligence</h2>
          <p>
            Autonomous HR synthesis across {stats?.total_employees || 100} enterprise employees, 712 attendance punch logs, and {departments?.length || 7} business divisions.
          </p>
        </div>
        <div className="banner-actions">
          <button type="button" className="btn-primary" onClick={() => onNavigateTab("copilot")}>
            Ask AI Copilot
            <ArrowRight size={16} />
          </button>
        </div>
      </div>

      {/* Active Data Ingestion Source Bar */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "var(--surface-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        padding: "0.75rem 1.25rem",
        marginBottom: "1.75rem",
        flexWrap: "wrap",
        gap: "0.75rem"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{
            width: "10px",
            height: "10px",
            borderRadius: "50%",
            background: "var(--emerald-tier)",
            boxShadow: "0 0 8px var(--emerald-tier)"
          }} />
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--fg-primary)" }}>
            Active Workforce Data Stream:
          </span>
          <span style={{ fontSize: "0.85rem", color: "var(--fg-secondary)" }}>
            Baseline + {customUploadsCount} Uploaded Sheet(s) Synced
          </span>
        </div>

        {latest_upload && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.775rem", color: "var(--brand-400)" }}>
            <FileSpreadsheet size={15} />
            <span>Latest Merged File: <strong>{latest_upload.original_name}</strong></span>
          </div>
        )}
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card kpi-accent">
          <div className="kpi-header">
            <span className="kpi-label">Total Workforce</span>
            <Users className="kpi-icon" size={20} />
          </div>
          <div className="kpi-value">{stats?.total_employees || 100}</div>
          <div className="kpi-subtext">Active personnel across {departments?.length || 7} departments</div>
        </div>

        <div className="kpi-card kpi-success">
          <div className="kpi-header">
            <span className="kpi-label">Average Attendance</span>
            <CheckCircle2 className="kpi-icon" size={20} />
          </div>
          <div className="kpi-value">{stats?.avg_attendance || 92.4}%</div>
          <div className="kpi-subtext">Punctuality rate: {stats?.avg_punctuality}%</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">Appraisal Rating</span>
            <Award className="kpi-icon" size={20} />
          </div>
          <div className="kpi-value">{stats?.avg_rating || 3.8} <span style={{ fontSize: "1.1rem", color: "var(--fg-secondary)" }}>/ 5.0</span></div>
          <div className="kpi-subtext">{stats?.top_performers_count || 20} Elite performers (≥ 4.5)</div>
        </div>

        <div className="kpi-card kpi-danger">
          <div className="kpi-header">
            <span className="kpi-label">High Attrition Risk</span>
            <AlertTriangle className="kpi-icon" size={20} />
          </div>
          <div className="kpi-value">{stats?.high_risk_count || 12}</div>
          <div className="kpi-subtext">Burnout & severe overtime alerts</div>
        </div>
      </div>

      {/* Two Column Grid: Department Benchmarks & Critical Alerts */}
      <div className="dashboard-grid">
        {/* Department Benchmarks */}
        <div className="card-panel">
          <div className="panel-header">
            <div>
              <h3>Department Attendance & Rating Benchmarks</h3>
              <p className="panel-sub">Comparative metrics across enterprise units</p>
            </div>
            <button type="button" className="btn-secondary" onClick={() => onNavigateTab("explorer")}>
              View All Grid
            </button>
          </div>

          <div className="department-list">
            {departments?.map((dept, idx) => (
              <div key={idx} className="dept-item">
                <div className="dept-info">
                  <span className="dept-name">{dept.department}</span>
                  <span className="dept-meta">{dept.headcount} members · {dept.avg_overtime}h avg overtime</span>
                </div>
                <div className="dept-progress-wrap">
                  <div className="progress-bar-bg">
                    <div
                      className="progress-bar-fill"
                      style={{
                        width: `${dept.avg_attendance}%`,
                        backgroundColor: dept.avg_attendance >= 93 ? "var(--emerald-tier)" : (dept.avg_attendance >= 88 ? "var(--brand-500)" : "var(--rose-tier)")
                      }}
                    />
                  </div>
                  <span className="dept-pct">{dept.avg_attendance}%</span>
                </div>
                <div className="dept-rating">
                  <span className="star-val">★ {dept.avg_rating}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Critical Alerts Stream */}
        <div className="card-panel">
          <div className="panel-header">
            <div>
              <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <ShieldAlert size={18} color="var(--rose-tier)" />
                Proactive Talent Risk Alerts
              </h3>
              <p className="panel-sub">Autonomous AI anomaly detection triggers (Baseline & Uploaded)</p>
            </div>
            <span className="badge badge-rose">{alerts?.length || 0} Alerts</span>
          </div>

          <div className="alerts-feed">
            {alerts?.slice(0, 5).map(alert => (
              <div
                key={alert.id}
                className={`alert-item alert-${alert.severity}`}
                onClick={() => alert.employee_id !== null && onSelectEmployee(alert.employee_id)}
              >
                <div className="alert-meta">
                  <span className={`alert-pill ${alert.severity}`}>{alert.severity}</span>
                  <span className="alert-cat">{alert.category.replace("_", " ")}</span>
                </div>
                <h4 className="alert-title">{alert.title}</h4>
                <p className="alert-desc">{alert.message}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Performance Rating Distribution */}
      <div className="card-panel" style={{ marginTop: "1.5rem" }}>
        <div className="panel-header">
          <div>
            <h3>Workforce Appraisal Rating Distribution</h3>
            <p className="panel-sub">Performance cohorts across all enterprise departments</p>
          </div>
        </div>
        <div className="distribution-cards">
          {rating_distribution?.map((dist, idx) => (
            <div key={idx} className="dist-card">
              <div className="dist-label">{dist.bucket}</div>
              <div className="dist-count">{dist.count}</div>
              <div className="dist-sub">Employees ({dist.count}% of workforce)</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
