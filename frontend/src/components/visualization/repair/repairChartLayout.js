/**
 * Deterministic Auto-Repair Priority Chain
 * Applies surgical transformations to ECharts options based on measured DOM defects.
 * 0 LLM calls - purely geometric calculations.
 */

import { humanizeLabel } from '../layout/formatters.js';

export const RepairAction = {
  EXPAND_LEFT_MARGIN: 'EXPAND_LEFT_MARGIN',
  EXPAND_BOTTOM_MARGIN: 'EXPAND_BOTTOM_MARGIN',
  ROTATE_X_LABELS: 'ROTATE_X_LABELS',
  STAGGER_X_LABELS: 'STAGGER_X_LABELS',
  MOVE_LEGEND_BOTTOM: 'MOVE_LEGEND_BOTTOM',
  CLAMP_Y_DOMAIN: 'CLAMP_Y_DOMAIN',
  HUMANIZE_LABELS: 'HUMANIZE_LABELS'
};

/**
 * Executes priority repair chain on an option given measured DOM QA issues.
 * @param {object} option 
 * @param {object} qaIssues 
 * @param {boolean} [qaIssues.yAxisClipped]
 * @param {boolean} [qaIssues.hasHorizontalOverflow]
 * @param {boolean} [qaIssues.hasVerticalOverflow]
 * @param {boolean} [qaIssues.xAxisCrowded]
 * @returns {{ repairedOption: object, repairsApplied: Array<{ action: string, reason: string }> }}
 */
export function repairChartLayout(option, qaIssues = {}) {
  if (!option || typeof option !== 'object') {
    return { repairedOption: option, repairsApplied: [] };
  }

  const repaired = JSON.parse(JSON.stringify(option));
  const repairsApplied = [];

  const grid = repaired.grid || { top: 36, right: 24, bottom: 40, left: 48 };

  // 1. Repair Y-Axis Clipping
  if (qaIssues.yAxisClipped || (qaIssues.hasHorizontalOverflow && grid.left < 70)) {
    const oldLeft = Number(grid.left) || 48;
    const newLeft = Math.min(oldLeft + 24, 180);
    grid.left = newLeft;
    repaired.grid = grid;
    repairsApplied.push({
      action: RepairAction.EXPAND_LEFT_MARGIN,
      reason: `Expanded left margin from ${oldLeft}px to ${newLeft}px to prevent Y-axis text clipping.`
    });
  }

  // 2. Repair X-Axis Label Crowding
  if (qaIssues.xAxisCrowded && repaired.xAxis) {
    const xAxes = Array.isArray(repaired.xAxis) ? repaired.xAxis : [repaired.xAxis];
    let rotated = false;

    xAxes.forEach(ax => {
      if (ax.type === 'category' || !ax.type) {
        ax.axisLabel = ax.axisLabel || {};
        if (!ax.axisLabel.rotate || ax.axisLabel.rotate === 0) {
          ax.axisLabel.rotate = 45;
          rotated = true;
        } else if (ax.axisLabel.rotate < 60) {
          ax.axisLabel.rotate = 60;
          rotated = true;
        }
      }
    });

    if (rotated) {
      grid.bottom = Math.min((Number(grid.bottom) || 40) + 20, 90);
      repaired.grid = grid;
      repairsApplied.push({
        action: RepairAction.ROTATE_X_LABELS,
        reason: 'Rotated X-axis category labels to prevent horizontal text collision.'
      });
    }
  }

  // 3. Repair Vertical Overflow
  if (qaIssues.hasVerticalOverflow) {
    if (grid.top > 24) {
      grid.top = 20;
    }
    if (grid.bottom > 40) {
      grid.bottom = Math.max(32, grid.bottom - 12);
    }
    repaired.grid = grid;
    repairsApplied.push({
      action: RepairAction.EXPAND_BOTTOM_MARGIN,
      reason: 'Compacted top/bottom grid margins to resolve vertical container overflow.'
    });
  }

  // 4. Repair Underscore-Laden Machine Labels (convert snake_case to clean human business labels)
  let labelsRepaired = false;

  const sanitizeAxis = (ax) => {
    if (!ax) return;
    if (Array.isArray(ax.data)) {
      const hasUnderscores = ax.data.some(d => typeof d === 'string' && d.includes('_'));
      if (hasUnderscores) {
        ax.data = ax.data.map(d => (typeof d === 'string' ? humanizeLabel(d) : d));
        labelsRepaired = true;
      }
    }
    if (typeof ax.name === 'string' && ax.name.includes('_')) {
      ax.name = humanizeLabel(ax.name);
      labelsRepaired = true;
    }
  };

  if (repaired.xAxis) {
    if (Array.isArray(repaired.xAxis)) repaired.xAxis.forEach(sanitizeAxis);
    else sanitizeAxis(repaired.xAxis);
  }
  if (repaired.yAxis) {
    if (Array.isArray(repaired.yAxis)) repaired.yAxis.forEach(sanitizeAxis);
    else sanitizeAxis(repaired.yAxis);
  }

  if (Array.isArray(repaired.series)) {
    repaired.series.forEach(s => {
      if (typeof s.name === 'string' && s.name.includes('_')) {
        s.name = humanizeLabel(s.name);
        labelsRepaired = true;
      }
      if (Array.isArray(s.data)) {
        s.data.forEach(item => {
          if (item && typeof item === 'object') {
            if (typeof item.name === 'string' && item.name.includes('_')) {
              item.name = humanizeLabel(item.name);
              labelsRepaired = true;
            }
            if (typeof item.full_name === 'string' && item.full_name.includes('_')) {
              item.full_name = humanizeLabel(item.full_name);
              labelsRepaired = true;
            }
          }
        });
      }
    });
  }

  if (repaired.title) {
    if (typeof repaired.title.text === 'string' && repaired.title.text.includes('_')) {
      repaired.title.text = humanizeLabel(repaired.title.text);
      labelsRepaired = true;
    }
    if (typeof repaired.title.subtext === 'string' && repaired.title.subtext.includes('_')) {
      repaired.title.subtext = humanizeLabel(repaired.title.subtext);
      labelsRepaired = true;
    }
  }

  if (labelsRepaired || qaIssues.hasUnderscoreLabels) {
    repairsApplied.push({
      action: RepairAction.HUMANIZE_LABELS,
      reason: 'Humanized chart labels, axes, and series names by replacing underscores with spaces.'
    });
  }

  return {
    repairedOption: repaired,
    repairsApplied
  };
}
