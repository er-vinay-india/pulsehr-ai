/**
 * Deterministic Auto-Repair Priority Chain
 * Applies surgical transformations to ECharts options based on measured DOM defects.
 * 0 LLM calls - purely geometric calculations.
 */

export const RepairAction = {
  EXPAND_LEFT_MARGIN: 'EXPAND_LEFT_MARGIN',
  EXPAND_BOTTOM_MARGIN: 'EXPAND_BOTTOM_MARGIN',
  ROTATE_X_LABELS: 'ROTATE_X_LABELS',
  STAGGER_X_LABELS: 'STAGGER_X_LABELS',
  MOVE_LEGEND_BOTTOM: 'MOVE_LEGEND_BOTTOM',
  CLAMP_Y_DOMAIN: 'CLAMP_Y_DOMAIN'
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

  return {
    repairedOption: repaired,
    repairsApplied
  };
}
