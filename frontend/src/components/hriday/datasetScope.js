// Upload completion selects a stored sheet, not a sheet name or workbook ID.
export function activateUploadedSheet(result, browser = window) {
  const sheetId = Number(result.sheet_ids?.[0]);
  const url = new URL(browser.location.href);
  if (Number.isSafeInteger(sheetId) && sheetId > 0) url.searchParams.set('sheet_id', sheetId);
  else url.searchParams.delete('sheet_id');
  url.searchParams.delete('derived_id');
  browser.history.replaceState(null, '', url);
  browser.dispatchEvent(new browser.CustomEvent('workbook-uploaded', { detail: result }));
}
