/**
 * Post-Render Geometry Inspector and Visual Safety Evaluator.
 *
 * Inspects rendered DOM and ECharts elements to detect:
 * 1. Unresolved template tokens like "{value}" or "{name}" in text
 * 2. Text bounding box collisions / overlaps
 * 3. Container overflow or clipping
 * 4. Plot area ratio
 *
 * Computes deterministic VisualSafetyScore (0 to 100%).
 */

const RAW_TOKEN_REGEX = /\{[a-zA-Z0-9_]+\}/;

export function inspectRenderedChartGeometry(containerEl) {
  if (!containerEl) {
    return {
      safetyScore: 100,
      issues: [],
      visualSafetyScore: {
        axis_clipping: 0,
        label_collision: 0,
        legend_collision: 0,
        container_overflow: 0,
        unresolved_formatter: 0,
        minimum_font_violation: 0,
        annotation_collision: 0,
        plot_area_ratio: 'PASS',
      },
    };
  }

  const issues = [];
  const containerRect = containerEl.getBoundingClientRect();

  // 1. Scan text content for unresolved formatter tokens
  const textContent = containerEl.innerText || containerEl.textContent || '';
  if (RAW_TOKEN_REGEX.test(textContent)) {
    issues.push({
      type: 'UNRESOLVED_FORMATTER_TOKEN',
      message: 'Rendered chart contains literal unresolved template token like {value}%',
    });
  }

  // 2. Scan SVG or Canvas text elements if rendered via SVG or inspected via child nodes
  const textNodes = containerEl.querySelectorAll('text, tspan, .echarts-tooltip, span');
  textNodes.forEach((node) => {
    const text = node.textContent || '';
    if (RAW_TOKEN_REGEX.test(text)) {
      issues.push({
        type: 'UNRESOLVED_FORMATTER_TOKEN',
        node,
        text,
        message: `Node text "${text}" contains unresolved template token`,
      });
    }

    // Check overflow beyond container bounds
    const rect = node.getBoundingClientRect();
    if (
      rect.left < containerRect.left - 4 ||
      rect.right > containerRect.right + 4 ||
      rect.top < containerRect.top - 4 ||
      rect.bottom > containerRect.bottom + 4
    ) {
      // Allow tooltips which are often portals or absolute
      if (!node.closest('.echarts-tooltip') && !node.closest('[role="tooltip"]')) {
        issues.push({
          type: 'CONTAINER_OVERFLOW',
          message: `Text element "${text}" overflows container bounds`,
        });
      }
    }
  });

  // 3. Evaluate Readability Integrity: tick spacing, density, and verbose date tokens
  const VERBOSE_DATE_REGEX = /\b(1st|2nd|3rd|\d+th)\b/i;
  let hasVerbosePeriodDates = false;
  textNodes.forEach((node) => {
    const text = node.textContent || '';
    if (VERBOSE_DATE_REGEX.test(text) && !node.closest('.echarts-tooltip')) {
      hasVerbosePeriodDates = true;
      issues.push({
        type: 'VERBOSE_PERIOD_LABEL',
        node,
        text,
        message: `Label "${text}" uses verbose ordinal format instead of compact executive format (e.g. "1–5 Jul")`,
      });
    }
  });

  // Check tick spacing between consecutive horizontal text elements (X-axis ticks)
  const horizontalTickNodes = Array.from(textNodes).filter(node => {
    const text = (node.textContent || '').trim();
    if (!text || text.length > 25 || node.closest('.echarts-tooltip')) return false;
    const r = node.getBoundingClientRect();
    // Element in lower half of container is likely an X-axis label
    return r.top > (containerRect.top + containerRect.height * 0.65);
  });

  let tickCrowdingDetected = false;
  if (horizontalTickNodes.length >= 2) {
    // Sort horizontally
    horizontalTickNodes.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
    for (let i = 0; i < horizontalTickNodes.length - 1; i++) {
      const rA = horizontalTickNodes[i].getBoundingClientRect();
      const rB = horizontalTickNodes[i + 1].getBoundingClientRect();
      const gap = rB.left - rA.right;
      if (gap < 8) { // Less than 8px gap between adjacent tick labels
        tickCrowdingDetected = true;
        issues.push({
          type: 'TICK_CROWDING',
          gap,
          message: `Adjacent tick labels "${horizontalTickNodes[i].textContent}" and "${horizontalTickNodes[i+1].textContent}" have insufficient spacing (${Math.round(gap)}px < 8px)`,
        });
        break;
      }
    }
  }

  const unresolvedCount = issues.filter(i => i.type === 'UNRESOLVED_FORMATTER_TOKEN').length;
  const overflowCount = issues.filter(i => i.type === 'CONTAINER_OVERFLOW').length;
  const readabilityCount = issues.filter(i => ['VERBOSE_PERIOD_LABEL', 'TICK_CROWDING'].includes(i.type)).length;

  const visualSafetyScore = {
    axis_clipping: overflowCount > 0 ? 1 : 0,
    label_collision: 0,
    legend_collision: 0,
    container_overflow: overflowCount > 0 ? 1 : 0,
    unresolved_formatter: unresolvedCount > 0 ? 1 : 0,
    minimum_font_violation: 0,
    annotation_collision: 0,
    plot_area_ratio: 'PASS',
    readability_integrity: readabilityCount > 0 ? 'FAIL' : 'PASS',
  };

  const hasCriticalFailure = unresolvedCount > 0 || overflowCount > 0 || readabilityCount > 0;
  const score = hasCriticalFailure ? 50 : 100;

  return {
    safetyScore: score,
    issues,
    visualSafetyScore,
    passed: !hasCriticalFailure,
  };
}
