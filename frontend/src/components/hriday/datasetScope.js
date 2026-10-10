// Upload completion selects an uploaded dataset workbook, normalizing Executive Dashboard to dataset_id.
export function activateUploadedSheet(result, browser = window) {
  const datasetId = Number(result.dataset_id || result.id);
  const url = new URL(browser.location.href);
  if (Number.isSafeInteger(datasetId) && datasetId > 0) {
    url.searchParams.set('dataset_id', datasetId);
  }
  url.searchParams.delete('sheet_id');
  url.searchParams.delete('derived_id');
  browser.history.replaceState(null, '', url);
  browser.dispatchEvent(new browser.CustomEvent('workbook-uploaded', { detail: result }));
}
