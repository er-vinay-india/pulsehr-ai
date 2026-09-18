import React, { useEffect, useState } from "react";
import { Search, Filter, ArrowUpDown, ChevronLeft, ChevronRight, Download, RefreshCw, Eye } from "lucide-react";
import { getEmployees } from "../api/client";

export default function DataExplorerPage({ onSelectEmployee }) {
  const [employees, setEmployees] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [risk, setRisk] = useState("");
  const [sortBy, setSortBy] = useState("id");
  const [sortDir, setSortDir] = useState("asc");

  const departments = [
    "All",
    "Engineering",
    "Product & Design",
    "Sales & Enterprise",
    "Marketing & Growth",
    "Human Resources",
    "Finance & Strategy",
    "Operations"
  ];

  const risks = ["All", "Low", "Moderate", "High"];

  const loadData = () => {
    setLoading(true);
    getEmployees({
      search,
      department: department === "All" ? "" : department,
      risk: risk === "All" ? "" : risk,
      page,
      limit: 20,
      sortBy,
      sortDir
    })
      .then(res => {
        setEmployees(res.employees);
        setTotal(res.total);
        setPages(res.pages);
      })
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [search, department, risk, sortBy, sortDir, page]);

  const handleSort = col => {
    if (sortBy === col) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
    setPage(1);
  };

  return (
    <div className="explorer-page">
      {/* Page Title & Search Bar */}
      <div className="page-header-row">
        <div>
          <h2>Workforce Tabular Explorer</h2>
          <p className="subtitle">Interactive database grid grounded in Kaggle attendance punches & performance appraisals</p>
        </div>
        <div className="total-badge">
          Showing <strong>{employees.length}</strong> of <strong>{total}</strong> Records
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="filters-toolbar">
        <div className="search-box">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by employee name, ID, or role..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>

        <div className="filter-group">
          <label>Department:</label>
          <select value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label>Attrition Risk:</label>
          <select value={risk} onChange={e => { setRisk(e.target.value); setPage(1); }}>
            {risks.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </div>

      {/* Grid Table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th onClick={() => handleSort("id")} style={{ cursor: "pointer" }}>
                <span className="th-content">ID <ArrowUpDown size={12} /></span>
              </th>
              <th onClick={() => handleSort("name")} style={{ cursor: "pointer" }}>
                <span className="th-content">Employee <ArrowUpDown size={12} /></span>
              </th>
              <th onClick={() => handleSort("department")} style={{ cursor: "pointer" }}>
                <span className="th-content">Department <ArrowUpDown size={12} /></span>
              </th>
              <th>Role</th>
              <th onClick={() => handleSort("attendance_rate")} style={{ cursor: "pointer" }}>
                <span className="th-content">Attendance <ArrowUpDown size={12} /></span>
              </th>
              <th onClick={() => handleSort("punctuality_rate")} style={{ cursor: "pointer" }}>
                <span className="th-content">Punctuality <ArrowUpDown size={12} /></span>
              </th>
              <th onClick={() => handleSort("rating")} style={{ cursor: "pointer" }}>
                <span className="th-content">Rating <ArrowUpDown size={12} /></span>
              </th>
              <th onClick={() => handleSort("overtime_hours")} style={{ cursor: "pointer" }}>
                <span className="th-content">Overtime <ArrowUpDown size={12} /></span>
              </th>
              <th onClick={() => handleSort("attrition_risk")} style={{ cursor: "pointer" }}>
                <span className="th-content">Risk Level <ArrowUpDown size={12} /></span>
              </th>
              <th style={{ textAlign: "center" }}>Profile</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} style={{ textAlign: "center", padding: "3rem" }}>
                  Loading workforce records...
                </td>
              </tr>
            ) : employees.length === 0 ? (
              <tr>
                <td colSpan={10} style={{ textAlign: "center", padding: "3rem" }}>
                  No employee records matched your filter criteria.
                </td>
              </tr>
            ) : (
              employees.map(emp => (
                <tr key={emp.id} onClick={() => onSelectEmployee(emp.id)}>
                  <td>
                    <span className="code-pill">{emp.employee_code}</span>
                  </td>
                  <td>
                    <div className="emp-cell">
                      <div className="avatar-small">
                        {emp.name.split(" ").map(n => n[0]).join("")}
                      </div>
                      <span className="emp-name">{emp.name}</span>
                    </div>
                  </td>
                  <td>
                    <span className="dept-tag">{emp.department}</span>
                  </td>
                  <td className="role-cell">{emp.role}</td>
                  <td>
                    <span className="metric-val" style={{ color: emp.attendance_rate >= 93 ? "var(--emerald-tier)" : (emp.attendance_rate >= 86 ? "var(--brand-400)" : "var(--rose-tier)") }}>
                      {emp.attendance_rate}%
                    </span>
                  </td>
                  <td>
                    <span className="metric-val">{emp.punctuality_rate}%</span>
                  </td>
                  <td>
                    <span className="rating-pill">★ {emp.rating}</span>
                  </td>
                  <td>
                    <span className={emp.overtime_hours > 25 ? "overtime-warning" : "metric-val"}>
                      {emp.overtime_hours} hrs
                    </span>
                  </td>
                  <td>
                    <span className={`badge badge-${emp.attrition_risk === 'High' ? 'rose' : (emp.attrition_risk === 'Moderate' ? 'amber' : 'emerald')}`}>
                      {emp.attrition_risk}
                    </span>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <button
                      type="button"
                      className="view-btn"
                      onClick={e => { e.stopPropagation(); onSelectEmployee(emp.id); }}
                      title="View detailed employee punches & profile"
                    >
                      <Eye size={15} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination Footer */}
        <div className="table-pagination">
          <div className="page-info">
            Page <strong>{page}</strong> of <strong>{pages}</strong>
          </div>
          <div className="page-buttons">
            <button
              type="button"
              className="btn-secondary"
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={page >= pages}
              onClick={() => setPage(p => Math.min(pages, p + 1))}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
