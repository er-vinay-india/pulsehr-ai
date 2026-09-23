const API_BASE = "/api";

export async function getAnalyticsOverview(sheetId = null) {
  const url = sheetId ? `${API_BASE}/analytics/overview?sheet_id=${sheetId}` : `${API_BASE}/analytics/overview`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch analytics overview");
  return res.json();
}

export async function getOverviewBase() {
  const res = await fetch(`${API_BASE}/analytics/overview/base`);
  if (!res.ok) throw new Error("Failed to fetch base overview metrics");
  return res.json();
}

export async function getOverviewVisuals(sheetId = null) {
  const url = sheetId ? `${API_BASE}/analytics/overview/visuals?sheet_id=${sheetId}` : `${API_BASE}/analytics/overview/visuals`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch visual intelligence");
  return res.json();
}

export async function getOverviewStory(sheetId = null, forceRefresh = false, model = null) {
  const params = new URLSearchParams();
  if (sheetId) params.set("sheet_id", sheetId);
  if (forceRefresh) params.set("force_refresh", "true");
  if (model) params.set("model", model);
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE}/analytics/overview/story${qs}`);
  if (!res.ok) throw new Error("Failed to fetch executive story");
  return res.json();
}

export async function getOverviewRelational(model = null) {
  const qs = model ? `?model=${encodeURIComponent(model)}` : "";
  const res = await fetch(`${API_BASE}/analytics/overview/relational${qs}`);
  if (!res.ok) throw new Error("Failed to fetch relational insights");
  return res.json();
}

export async function getOverviewEvidencePackage(sheetId = null) {
  const url = sheetId ? `${API_BASE}/analytics/overview/evidence-package?sheet_id=${sheetId}` : `${API_BASE}/analytics/overview/evidence-package`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch shared evidence package");
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

export async function askCopilot(
  query,
  model = null,
  tool = null,
  datasetId = null,
  sheetId = null,
  signal = null,
  priorContext = null,
  snapshotId = null,
  page = null
) {
  const res = await fetch(`${API_BASE}/copilot/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      model,
      tool,
      dataset_id: datasetId,
      sheet_id: sheetId,
      prior_context: priorContext,
      snapshot_id: snapshotId,
      page
    }),
    signal
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to query AI copilot");
  }
  return res.json();
}

export async function streamCopilotQuery(
  query,
  model = null,
  tool = null,
  datasetId = null,
  sheetId = null,
  callbacks = {},
  signal = null,
  priorContext = null,
  snapshotId = null,
  page = null
) {
  const { onStatus, onToken, onDone, onError } = callbacks;
  try {
    const res = await fetch(`${API_BASE}/copilot/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        model,
        tool,
        dataset_id: datasetId,
        sheet_id: sheetId,
        prior_context: priorContext,
        snapshot_id: snapshotId,
        page
      }),
      signal
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to start copilot stream");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        if (!part.trim()) continue;
        const lines = part.split("\n");
        let eventType = "message";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.slice(6).trim();
          }
        }

        if (dataStr) {
          try {
            const data = JSON.parse(dataStr);
            if (eventType === "status") {
              onStatus?.(data);
            } else if (eventType === "token") {
              onToken?.(data.token);
            } else if (eventType === "done") {
              onDone?.(data);
            } else if (eventType === "error") {
              onError?.(new Error(data.message || "Streaming error"));
            }
          } catch (e) {
            console.warn("Failed to parse SSE data:", dataStr, e);
          }
        }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") {
      return;
    }
    onError?.(err);
  }
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

export async function investigateEvidence(rawTarget = {}) {
  const entityType = rawTarget.entityType || rawTarget.entity_type || rawTarget.type || "department";
  const targetId = rawTarget.targetId || rawTarget.target_id || rawTarget.target || rawTarget.department || null;
  const metric = rawTarget.metric || null;
  const sheetId = rawTarget.sheetId || rawTarget.sheet_id || null;
  const chartId = rawTarget.chartId || rawTarget.chart_id || null;
  const params = new URLSearchParams();
  if (entityType) params.set("entity_type", entityType);
  if (targetId) params.set("target_id", targetId);
  if (metric) params.set("metric", metric);
  if (sheetId) params.set("sheet_id", sheetId);
  if (chartId) params.set("chart_id", chartId);
  const res = await fetch(`${API_BASE}/analytics/investigate?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to execute investigation query");
  return res.json();
}

export async function getPresentationThemes() {
  const res = await fetch(`${API_BASE}/presentations/themes`);
  if (!res.ok) throw new Error("Failed to load presentation themes");
  return res.json();
}

export async function previewPresentationScope(scope) {
  const res = await fetch(`${API_BASE}/presentations/scope-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scope),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to preview presentation scope");
  }
  return res.json();
}

export async function startPresentationGeneration(scope) {
  const res = await fetch(`${API_BASE}/presentations/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scope),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to start presentation generation");
  }
  return res.json();
}

export async function getPresentationDeckEvidence(deckId) {
  const res = await fetch(`${API_BASE}/presentations/decks/${deckId}/evidence`);
  if (!res.ok) throw new Error("Failed to load presentation evidence ledger");
  return res.json();
}

export async function revalidatePresentationDeck(deckSpec) {
  const res = await fetch(`${API_BASE}/presentations/revalidate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deck_spec: deckSpec }),
  });
  if (!res.ok) throw new Error("Failed to revalidate presentation deck claims");
  return res.json();
}

export async function getPresentationJob(jobId) {
  const res = await fetch(`${API_BASE}/presentations/jobs/${jobId}`);
  if (!res.ok) throw new Error("Failed to fetch presentation job status");
  return res.json();
}

export async function cancelPresentationJob(jobId) {
  const res = await fetch(`${API_BASE}/presentations/jobs/${jobId}/cancel`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to cancel presentation job");
  return res.json();
}

export async function getPresentationDeck(deckId) {
  const res = await fetch(`${API_BASE}/presentations/decks/${deckId}`);
  if (!res.ok) throw new Error("Failed to load presentation deck");
  return res.json();
}

export async function updatePresentationDeck(deckId, deckSpec) {
  const res = await fetch(`${API_BASE}/presentations/decks/${deckId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(deckSpec)
  });
  if (!res.ok) throw new Error("Failed to save presentation deck");
  return res.json();
}

export async function regenerateSlide(deckSpec, slideId, prompt) {
  const res = await fetch(`${API_BASE}/presentations/regenerate-slide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deck_spec: deckSpec, slide_id: slideId, prompt })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to regenerate slide");
  }
  return res.json();
}

export async function exportPresentationPptx(deckSpec) {
  const res = await fetch(`${API_BASE}/presentations/export-pptx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deck_spec: deckSpec })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to export PowerPoint");
  }
  const blob = await res.blob();
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const rawTitle = deckSpec.metadata?.title || deckSpec.title || "Executive_Presentation";
  const cleanTitle = rawTitle.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40).replace(/^_+|_+$/g, "") || "Presentation";
  const filename = `${cleanTitle}_${ts}.pptx`;
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function getPresentationDecks() {
  const res = await fetch(`${API_BASE}/presentations/decks`);
  if (!res.ok) throw new Error("Failed to load saved presentations");
  return res.json();
}

export async function getDeckNarration(deckId) {
  const res = await fetch(`${API_BASE}/presentations/${deckId}/narration`);
  if (!res.ok) throw new Error("Failed to load narration manifest");
  return res.json();
}

export async function generateDeckNarration(deckId, voice = "andrew") {
  const res = await fetch(`${API_BASE}/presentations/${deckId}/narration`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ voice })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to generate narration");
  }
  return res.json();
}



