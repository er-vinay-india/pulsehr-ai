import { useState, useEffect, useRef } from 'react';

/**
 * Checks if a chart option contains any un-repaired underscore tokens.
 * @param {object} opt 
 * @returns {boolean}
 */
export function detectUnderscoresInOption(opt) {
  if (!opt || typeof opt !== 'object') return false;
  for (const axKey of ['xAxis', 'yAxis']) {
    const axes = Array.isArray(opt[axKey]) ? opt[axKey] : (opt[axKey] ? [opt[axKey]] : []);
    for (const ax of axes) {
      if (typeof ax?.name === 'string' && ax.name.includes('_')) return true;
      if (Array.isArray(ax?.data)) {
        for (const item of ax.data) {
          if (typeof item === 'string' && item.includes('_')) return true;
          if (item && typeof item === 'object' && typeof item.value === 'string' && item.value.includes('_')) return true;
        }
      }
    }
  }
  if (Array.isArray(opt.series)) {
    for (const s of opt.series) {
      if (typeof s?.name === 'string' && s.name.includes('_')) return true;
      if (Array.isArray(s?.data)) {
        for (const d of s.data) {
          if (d && typeof d === 'object') {
            if (typeof d.name === 'string' && d.name.includes('_')) return true;
            if (typeof d.full_name === 'string' && d.full_name.includes('_')) return true;
          }
        }
      }
    }
  }
  if (opt.title) {
    if (typeof opt.title.text === 'string' && opt.title.text.includes('_')) return true;
    if (typeof opt.title.subtext === 'string' && opt.title.subtext.includes('_')) return true;
  }
  return false;
}

/**
 * React Hook for Post-Render DOM Visual QA.
 * Inspects real DOM bounding boxes and overflows to trigger deterministic repair.
 * @param {React.RefObject<HTMLElement>} containerRef 
 * @param {object} [options]
 * @param {boolean} [options.enabled=true]
 * @param {object} [options.chartOption=null]
 * @returns {{ qaIssues: object, isInspecting: boolean }}
 */
export function useVisualQA(containerRef, options = {}) {
  const { enabled = true, chartOption = null } = options;
  const [qaIssues, setQaIssues] = useState(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const checkTimerRef = useRef(null);

  useEffect(() => {
    if (!enabled) return;

    const inspectDOM = () => {
      const node = containerRef.current;
      if (!node) return;

      setIsInspecting(true);

      const clientWidth = node.clientWidth;
      const scrollWidth = node.scrollWidth;
      const clientHeight = node.clientHeight;
      const scrollHeight = node.scrollHeight;

      // 1. Container overflow check
      const hasHorizontalOverflow = scrollWidth > (clientWidth + 2);
      const hasVerticalOverflow = scrollHeight > (clientHeight + 2);

      // 2. SVG Text Boundary Check (detect clipped labels)
      let yAxisClipped = false;
      let xAxisCrowded = false;

      const svgTexts = node.querySelectorAll('svg text');
      if (svgTexts.length > 0) {
        const containerRect = node.getBoundingClientRect();
        for (let i = 0; i < svgTexts.length; i++) {
          const textRect = svgTexts[i].getBoundingClientRect();
          // Check if left of text is pushed out of left edge of chart container
          if (textRect.left < containerRect.left + 4 && textRect.width > 20) {
            yAxisClipped = true;
            break;
          }
        }
      }

      // 3. Underscore Label Check (detect raw machine tokens in chart labels and DOM)
      let hasUnderscoreLabels = false;

      if (svgTexts.length > 0) {
        for (let i = 0; i < svgTexts.length; i++) {
          const text = svgTexts[i].textContent || '';
          if (text.includes('_')) {
            hasUnderscoreLabels = true;
            break;
          }
        }
      }

      const domEls = node.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, div, text, [role="img"], [aria-label]');
      for (let i = 0; i < domEls.length; i++) {
        const el = domEls[i];
        if (el.children.length === 0 || el.tagName.toLowerCase() === 'text') {
          const txt = el.textContent || '';
          if (txt.includes('_') && !txt.includes('__')) {
            hasUnderscoreLabels = true;
            break;
          }
        }
        const aria = el.getAttribute('aria-label') || '';
        if (aria.includes('_')) {
          hasUnderscoreLabels = true;
          break;
        }
      }

      // Check chartOption structure directly if provided
      if (!hasUnderscoreLabels && chartOption) {
        hasUnderscoreLabels = detectUnderscoresInOption(chartOption);
      }

      const issuesFound = {
        hasHorizontalOverflow,
        hasVerticalOverflow,
        yAxisClipped,
        xAxisCrowded,
        hasUnderscoreLabels,
        timestamp: Date.now()
      };

      const hasAnyIssue = hasHorizontalOverflow || hasVerticalOverflow || yAxisClipped || xAxisCrowded || hasUnderscoreLabels;
      setQaIssues(hasAnyIssue ? issuesFound : null);
      setIsInspecting(false);
    };

    // Run after paint
    checkTimerRef.current = setTimeout(inspectDOM, 100);

    const observer = new ResizeObserver(() => {
      clearTimeout(checkTimerRef.current);
      checkTimerRef.current = setTimeout(inspectDOM, 120);
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => {
      clearTimeout(checkTimerRef.current);
      observer.disconnect();
    };
  }, [enabled, containerRef, chartOption]);

  return { qaIssues, isInspecting };
}
