import React, { useRef, useEffect } from 'react';
import * as echarts from 'echarts';

/**
 * SafeReactECharts:
 * Ultra-robust Apache ECharts wrapper for React.
 * Prevents canvas 0x0 errors, catches option parse errors, and supports responsive resizing.
 */
export default function SafeReactECharts({
  option,
  style = { height: '300px', width: '100%', minHeight: '180px' },
  onEvents = null,
  opts = { renderer: 'canvas' }
}) {
  const containerRef = useRef(null);
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let chart = null;
    try {
      chart = echarts.init(containerRef.current, null, opts);
      chartInstanceRef.current = chart;

      // Apply initial options immediately if available
      if (option && typeof option === 'object' && Object.keys(option).length > 0) {
        chart.setOption(option, true);
      }

      // Attach event listeners
      if (onEvents) {
        Object.entries(onEvents).forEach(([eventName, handler]) => {
          if (typeof handler === 'function') {
            chart.on(eventName, handler);
          }
        });
      }
    } catch (initErr) {
      console.warn('SafeReactECharts: Initialization error:', initErr);
    }

    // Handle responsive container resize safely
    let resizeObserver = null;
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      try {
        resizeObserver = new ResizeObserver(() => {
          if (chartInstanceRef.current && !chartInstanceRef.current.isDisposed()) {
            chartInstanceRef.current.resize();
          }
        });
        resizeObserver.observe(containerRef.current);
      } catch (roErr) {
        console.warn('SafeReactECharts: ResizeObserver warning:', roErr);
      }
    }

    const handleWindowResize = () => {
      if (chartInstanceRef.current && !chartInstanceRef.current.isDisposed()) {
        chartInstanceRef.current.resize();
      }
    };
    window.addEventListener('resize', handleWindowResize);

    return () => {
      window.removeEventListener('resize', handleWindowResize);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (chartInstanceRef.current) {
        try {
          chartInstanceRef.current.dispose();
        } catch (dErr) {
          // ignore dispose error
        }
        chartInstanceRef.current = null;
      }
    };
  }, []);

  // Update chart options whenever `option` changes
  useEffect(() => {
    if (chartInstanceRef.current && !chartInstanceRef.current.isDisposed() && option && typeof option === 'object' && Object.keys(option).length > 0) {
      try {
        chartInstanceRef.current.setOption(option, true);
      } catch (optErr) {
        console.warn('SafeReactECharts: Failed to apply options:', optErr);
      }
    }
  }, [option]);

  return <div ref={containerRef} style={{ minHeight: '180px', width: '100%', ...style }} />;
}
