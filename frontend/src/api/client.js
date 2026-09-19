const API_BASE = "/api";

export async function getAnalyticsOverview(sheetId = null) {
  const url = sheetId ? `${API_BASE}/analytics/overview?sheet_id=${sheetId}` : `${API_BASE}/analytics/overview`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch analytics overview");
  return res.json();
}

export async function refreshOverviewStory(sheetId = null, model = null) {
  const params = new URLSearchParams();
  if (sheetId) params.set("sheet_id", sheetId);
  if (model) params.set("model", model);
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE}/analytics/overview/refresh-story${qs}`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to refresh executive story");
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

export async function askCopilot(query, model = null, tool = null) {
  const res = await fetch(`${API_BASE}/copilot/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, model, tool })
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

export function getDatasetDownloadUrl(datasetId) {
  return `${API_BASE}/upload/datasets/${datasetId}/download`;
}

export function getSheetDownloadUrl(sheetId, format = "csv") {
  return `${API_BASE}/sheets/${sheetId}/download?format=${format}`;
}

export function getPresentationDownloadUrl() {
  return `${API_BASE}/reports/presentation/latest`;
}

export async function triggerPresentationGeneration() {
  const res = await fetch(`${API_BASE}/reports/presentation`, { method: "POST" });
  if (!res.ok) { const error = await res.json().catch(() => ({})); throw new Error(error.detail || "Failed to generate presentation deck"); }
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


export async function getCalculationColumns(dataset, sheet, relationship) {
  const params = new URLSearchParams();
  if (dataset) params.set('dataset_id', dataset);
  if (relationship) params.set('relationship_id', relationship);
  if (sheet) params.set('sheet', sheet);
  const res = await fetch(`${API_BASE}/copilot/calculation-columns?${params}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Cannot read source columns');
  return data;
}

async function readSheetApi(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Unable to load sheets');
  return data;
}
export const getSheets = () => readSheetApi('/api/sheets');
export const getSheetRows = (id, page, search) => readSheetApi(`/api/sheets/${id}/rows?${new URLSearchParams({page, search})}`);
export const getJoinedRows = (id, page) => readSheetApi(`/api/sheets/relationships/${id}/rows?page=${page}`);
export const getSheetProjections = (id) => readSheetApi(`/api/sheets/${id}/projections`);

