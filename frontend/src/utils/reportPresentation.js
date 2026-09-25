export function groupLabel(dimension, value) {
  const name = String(dimension || '').replaceAll('_', ' ').trim();
  const label = String(value ?? 'Unknown');
  return !name || label.toLowerCase().startsWith(`${name.toLowerCase()} `) ? label : `${name} ${label}`;
}
export function findingTitle(finding) {
  const d = finding.detail || {};
  const prefix = `${d.focus_group}:`;
  return d.dimension && d.focus_group != null && finding.title?.startsWith(prefix)
    ? `${groupLabel(d.dimension_label || d.dimension, d.focus_group)}:${finding.title.slice(prefix.length)}`
    : finding.title;
}
// Keep different sources separate: matching aggregates do not prove duplicate uploads.
export function visualKey(source, metric, detail) {
  return JSON.stringify([source?.sheet_id, metric, detail.dimension || '', detail.groups || detail.points || []]);
}
export function findingAction(finding) {
  const d = finding.detail || {};
  if (!d.dimension || d.focus_group == null) return finding.action;
  return finding.action?.replace(`the ${d.focus_group} owner`, `the ${groupLabel(d.dimension_label || d.dimension, d.focus_group)} owner`);
}
