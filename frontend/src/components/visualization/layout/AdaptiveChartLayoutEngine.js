/**
 * Adaptive Chart Layout Engine (Frontend).
 *
 * Deterministically computes presentation-safe geometry:
 * - Dynamic chart height based on category count and header/legend overhead
 * - Grid left margin accommodation based on category label length
 * - Reference-line annotation collision avoidance
 * - Plot area ratio calculation (target >= 0.55)
 * - Multi-viewport responsiveness (desktop, tablet, mobile)
 */

export class AdaptiveChartLayoutEngine {
  static MIN_HORIZONTAL_BAR_HEIGHT = 260;
  static ROW_HEIGHT_PX = 38;
  static HEADER_OVERHEAD_PX = 48;
  static AXIS_OVERHEAD_PX = 42;
  static MIN_PLOT_AREA_RATIO = 0.55;

  /**
   * Plans layout dimensions and containment parameters.
   * @param {object} params
   * @param {string} params.chartType - 'bar'|'horizontal_bar'|'line'|'grouped_bar'|'donut'
   * @param {number} [params.containerWidth=800]
   * @param {number} [params.containerHeight=320]
   * @param {string[]} [params.categories=[]]
   * @param {number} [params.seriesCount=1]
   * @param {number} [params.titleLines=1]
   * @param {boolean} [params.hasLegend=false]
   * @param {Array} [params.annotations=[]]
   * @param {boolean} [params.isMobile=false]
   * @returns {object} LayoutPlan
   */
  static plan({
    chartType = 'bar',
    containerWidth = 800,
    containerHeight = 320,
    categories = [],
    seriesCount = 1,
    titleLines = 1,
    hasLegend = false,
    annotations = [],
    isMobile = false,
  }) {
    const cleanType = String(chartType).toLowerCase();
    const categoryCount = categories.length;
    const longestLabelChars = categories.reduce(
      (max, c) => Math.max(max, String(c || '').length),
      0
    );

    // 1. Dynamic Chart Height
    let chartHeight = containerHeight;
    if (['bar', 'horizontal_bar', 'horizontalbar', 'ranked_bar'].includes(cleanType)) {
      const computedHeight =
        this.HEADER_OVERHEAD_PX +
        categoryCount * this.ROW_HEIGHT_PX +
        this.AXIS_OVERHEAD_PX;
      chartHeight = Math.max(this.MIN_HORIZONTAL_BAR_HEIGHT, computedHeight);
      if (categoryCount > 10) {
        chartHeight = Math.min(chartHeight, 650);
      }
    } else if (['line', 'grouped_bar', 'column', 'area'].includes(cleanType)) {
      chartHeight = Math.max(containerHeight, 260);
      if (isMobile) {
        chartHeight = Math.max(chartHeight, 280);
      }
    }

    // 2. Y-Axis Grid Margin (grid.left)
    let gridLeft = 48;
    let gridRight = 24;

    if (['bar', 'horizontal_bar', 'horizontalbar', 'ranked_bar'].includes(cleanType)) {
      // 7.5px per character + generous padding for clean visual breathing room
      const calcLeft = Math.ceil(longestLabelChars * 7.5) + 24;
      gridLeft = Math.max(76, Math.min(calcLeft, 240));
      gridRight = annotations.length > 0 ? 56 : 36;
    } else {
      gridLeft = isMobile ? 42 : 52;
      gridRight = 24;
    }

    // 3. Grid Top Margin
    let gridTop = 24 + titleLines * 14;
    if (annotations.length > 0) {
      gridTop += 12;
    }

    // 4. Grid Bottom Margin & Label Rotation
    let gridBottom = 36;
    let labelRotation = 0;
    let labelInterval = 0;

    if (['line', 'grouped_bar', 'column'].includes(cleanType)) {
      const availableCatWidth = containerWidth / Math.max(1, categoryCount);
      if (isMobile || availableCatWidth < longestLabelChars * 7.2) {
        labelRotation = longestLabelChars <= 10 ? 30 : 45;
        gridBottom += 24;
      }
    }

    // 5. Legend Intelligence
    let legendPosition = 'none';
    if (seriesCount > 1 || hasLegend) {
      if (isMobile || chartHeight <= 280) {
        // Shallow container or mobile: move legend to top to preserve plot height
        legendPosition = 'top';
        gridTop += 16;
        gridBottom += 6;
      } else {
        legendPosition = 'bottom';
        gridBottom += 24;
      }
    }

    // 6. Annotation Placement (prevent bar collisions)
    let annotationPosition = 'none';
    if (annotations.length > 0) {
      // 'insideEndTop' or 'end' places benchmark text cleanly above/at top of plot
      annotationPosition = 'end';
    }

    // 7. Plot Area Ratio calculation
    const plotW = Math.max(0, containerWidth - gridLeft - gridRight);
    const plotH = Math.max(0, chartHeight - gridTop - gridBottom);
    const totalArea = containerWidth * chartHeight;
    let plotAreaRatio = totalArea > 0 ? (plotW * plotH) / totalArea : 0;

    // Compact margins if ratio < 0.55
    if (plotAreaRatio < this.MIN_PLOT_AREA_RATIO && totalArea > 0) {
      gridTop = Math.max(20, gridTop - 8);
      gridBottom = Math.max(28, gridBottom - 8);
      const adjustedPlotH = Math.max(0, chartHeight - gridTop - gridBottom);
      plotAreaRatio = (plotW * adjustedPlotH) / totalArea;
    }

    // 8. Readability Integrity Metrics
    const tickSpacingPx = categoryCount > 0 ? plotW / categoryCount : plotW;
    const labelWidthPx = longestLabelChars * 7.5;
    const readabilityPassed = tickSpacingPx >= (labelWidthPx + 12);
    const shouldSwitchToLine = ['grouped_bar', 'column', 'bar'].includes(cleanType) &&
      seriesCount >= 2 &&
      (tickSpacingPx < (labelWidthPx + 16) || containerWidth < 500);

    return {
      gridLeft,
      gridRight,
      gridTop,
      gridBottom,
      chartHeight,
      labelRotation,
      labelInterval,
      legendPosition,
      annotationPosition,
      plotAreaRatio: Math.round(plotAreaRatio * 100) / 100,
      safetyScore: plotAreaRatio >= this.MIN_PLOT_AREA_RATIO && readabilityPassed ? 1.0 : 0.85,
      tickSpacingPx: Math.round(tickSpacingPx * 10) / 10,
      labelWidthPx: Math.round(labelWidthPx * 10) / 10,
      readabilityPassed,
      recommendedChartType: shouldSwitchToLine ? 'line' : cleanType,
    };
  }

  /**
   * Deterministically compacts verbose period labels into executive format.
   * e.g. "1st–5th Jul" / "1st to 5th July" -> "1–5 Jul"
   */
  static compactPeriodLabel(label) {
    if (!label) return '';
    const clean = String(label).trim();
    const match = clean.match(/(\d+)(?:st|nd|rd|th)?\s*(?:to|–|-)\s*(\d+)(?:st|nd|rd|th)?\s*(?:July|Jul)?/i);
    if (match) {
      return `${match[1]}–${match[2]} Jul`;
    }
    return clean
      .replace(/(\d+)(?:st|nd|rd|th)/gi, '$1')
      .replace(/\bJuly\b/gi, 'Jul');
  }

  static compactCategories(categories = []) {
    return categories.map(c => this.compactPeriodLabel(c));
  }
}

