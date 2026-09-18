const API_BASE = "/api";

export async function getAnalyticsOverview() {
  const res = await fetch(`${API_BASE}/analytics/overview`);
  if (!res.ok) throw new Error("Failed to fetch analytics overview");
  return res.json();
}

export async function getEmployees({ search = "", department = "", risk = "", page = 1, limit = 20, sortBy = "id", sortDir = "asc" } = {}) {
  const query = new URLSearchParams({
    search,
    department: department || "",
    risk: risk || "",
    page: String(page),
    limit: String(limit),
    sort_by: sortBy,
    sort_dir: sortDir
  });
  const res = await fetch(`${API_BASE}/employees?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch employees");
  return res.json();
}

export async function getEmployeeDetail(id) {
  const res = await fetch(`${API_BASE}/employees/${id}`);
  if (!res.ok) throw new Error("Failed to fetch employee detail");
  return res.json();
}

export async function askCopilot(query, model = null) {
  const res = await fetch(`${API_BASE}/copilot/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, model })
  });
  if (!res.ok) throw new Error("Failed to query AI copilot");
  return res.json();
}

export async function getCopilotSuggestions() {
  const res = await fetch(`${API_BASE}/copilot/suggestions`);
  if (!res.ok) return { suggestions: [] };
  return res.json();
}

export async function uploadDatasetFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/upload/file`, {
    method: "POST",
    body: formData
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload dataset file");
  }
  return res.json();
}

export async function listDatasets() {
  const res = await fetch(`${API_BASE}/upload/datasets`);
  if (!res.ok) throw new Error("Failed to fetch datasets list");
  return res.json();
}

export async function reseedKaggle() {
  const res = await fetch(`${API_BASE}/upload/reseed-kaggle`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to re-seed Kaggle dataset");
  return res.json();
}

export function getPresentationDownloadUrl() {
  return `${API_BASE}/reports/presentation/latest`;
}

export async function triggerPresentationGeneration() {
  const res = await fetch(`${API_BASE}/reports/presentation`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to generate presentation deck");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `PulseHR_Executive_Presentation_${Date.now()}.pptx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function openExecutivePrintReport() {
  const res = await fetch(`${API_BASE}/reports/executive-html`);
  if (!res.ok) throw new Error("Failed to generate executive report");
  const html = await res.text();
  const printWindow = window.open("", "_blank");
  if (printWindow) {
    printWindow.document.write(html);
    printWindow.document.close();
  }
}

export async function deleteDataset(id) {
  const res = await fetch(`${API_BASE}/upload/datasets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete dataset");
  return res.json();
}

export async function getAvailableModels() {
  const res = await fetch(`${API_BASE}/copilot/models`);
  if (!res.ok) return { models: [] };
  return res.json();
}
