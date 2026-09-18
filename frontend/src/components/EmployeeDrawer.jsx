import React, { useEffect, useState } from "react";
import { X, Calendar, Clock, AlertTriangle, User, Award, ShieldAlert, CheckCircle2 } from "lucide-react";
import { getEmployeeDetail } from "../api/client";

export default function EmployeeDrawer({ employeeId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (employeeId === null || employeeId === undefined) return;
    setLoading(true);
    getEmployeeDetail(employeeId)
      .then(res => setData(res))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, [employeeId]);

  if (employeeId === null || employeeId === undefined) return null;

  const emp = data?.employee;
  const punches = data?.recent_punches || [];
  const alerts = data?.alerts || [];

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={e => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-title-group">
            <div className="avatar-large">
              {emp?.name ? emp.name.split(" ").map(n => n[0]).join("") : "EMP"}
            </div>
            <div>
              <h2>{emp?.name || "Loading..."}</h2>
              <div className="drawer-subtitle">
                <span>{emp?.employee_code}</span> · <span>{emp?.role}</span> · <span className="dept-tag">{emp?.department}</span>
              </div>
            </div>
          </div>
          <button type="button" className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="drawer-loading">Loading workforce profile...</div>
        ) : (
          <div className="drawer-body">
            {/* Quick Metrics */}
            <div className="metrics-strip">
              <div className="strip-card">
                <div className="strip-label">Attendance Rate</div>
                <div className="strip-val" style={{ color: "var(--emerald-tier)" }}>{emp.attendance_rate}%</div>
                <div className="strip-sub">{emp.present_days} / {emp.total_days} days</div>
              </div>
              <div className="strip-card">
                <div className="strip-label">Punctuality Rate</div>
                <div className="strip-val" style={{ color: "var(--accent-500)" }}>{emp.punctuality_rate}%</div>
                <div className="strip-sub">{emp.late_days} late arrivals</div>
              </div>
              <div className="strip-card">
                <div className="strip-label">Appraisal Rating</div>
                <div className="strip-val" style={{ color: "var(--brand-400)" }}>{emp.rating} / 5.0</div>
                <div className="strip-sub">{emp.salary_band} Level</div>
              </div>
              <div className="strip-card">
                <div className="strip-label">Monthly Overtime</div>
                <div className="strip-val" style={{ color: emp.overtime_hours > 20 ? "var(--rose-tier)" : "var(--fg-primary)" }}>
                  {emp.overtime_hours} hrs
                </div>
                <div className="strip-sub">Avg {emp.avg_daily_hours}h daily</div>
              </div>
            </div>

            {/* AI Summary Profile */}
            <div className="section-card">
              <div className="section-title">
                <Award size={16} />
                <span>AI Profile Assessment</span>
              </div>
              <p className="profile-text">{emp.summary_profile}</p>
              <div className="profile-tags">
                <span className={`badge badge-${emp.attrition_risk === 'High' ? 'rose' : (emp.attrition_risk === 'Moderate' ? 'amber' : 'emerald')}`}>
                  {emp.attrition_risk} Attrition Risk
                </span>
                <span className="badge badge-amber">{emp.tenure_years} Years Tenure</span>
                <span className="badge badge-emerald">Schedule: {emp.start_time} - {emp.end_time}</span>
              </div>
            </div>

            {/* Alerts */}
            {alerts.length > 0 && (
              <div className="section-card alert-section">
                <div className="section-title">
                  <ShieldAlert size={16} color="var(--rose-tier)" />
                  <span style={{ color: "var(--rose-tier)" }}>Active Talent Risk Alerts ({alerts.length})</span>
                </div>
                {alerts.map(a => (
                  <div key={a.id} className="alert-mini-card">
                    <strong>{a.title}</strong>
                    <p>{a.message}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Punch History */}
            <div className="section-card">
              <div className="section-title">
                <Calendar size={16} />
                <span>Recent Attendance Punches ({punches.length} records)</span>
              </div>
              <div className="punches-table-wrap">
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Clock In</th>
                      <th>Clock Out</th>
                      <th>Duration</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {punches.slice(0, 15).map((p, idx) => (
                      <tr key={idx}>
                        <td>{p.date}</td>
                        <td>{p.clock_in || "—"}</td>
                        <td>{p.clock_out || "—"}</td>
                        <td>{p.duration_hours ? `${p.duration_hours}h` : "—"}</td>
                        <td>
                          <span className={`status-pill ${p.status.toLowerCase()}`}>
                            {p.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
