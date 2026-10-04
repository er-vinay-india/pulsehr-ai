import { useState, useEffect, useRef } from 'react';

/**
 * React Hook for Post-Render DOM Visual QA.
 * Inspects real DOM bounding boxes and overflows to trigger deterministic repair.
 * @param {React.RefObject<HTMLElement>} containerRef 
 * @param {object} [options]
 * @param {boolean} [options.enabled=true]
 * @returns {{ qaIssues: object, isInspecting: boolean }}
 */
export function useVisualQA(containerRef, options = {}) {
  const { enabled = true } = options;
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

      const issuesFound = {
        hasHorizontalOverflow,
        hasVerticalOverflow,
        yAxisClipped,
        xAxisCrowded,
        timestamp: Date.now()
      };

      const hasAnyIssue = hasHorizontalOverflow || hasVerticalOverflow || yAxisClipped || xAxisCrowded;
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
  }, [enabled, containerRef]);

  return { qaIssues, isInspecting };
}
