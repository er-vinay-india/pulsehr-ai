import { slideChartOptions } from '../../theme/slideChartOptions.js';
import React, { useRef, useEffect, useState } from 'react';
import * as echarts from 'echarts';
import { lightPalette, darkPalette, isCurrentThemeDark } from './chartOptions';
import { getThemeTokens } from '../../theme/tokens';
import { useTheme } from '../../context/ThemeContext';
import '../../styles/minimal-charts.scss';

const LEGACY_COLORS = new Set([
  '#ff8a62', '#1c1815', '#524940', '#ded5cb', '#fff9f2', '#171412', '#3d362f',
  '#201b18', '#beb2a6', '#7ee7d9', '#8ef0c8', '#a78bfa', '#ff8ca0',
  '#22c7f2', '#84cc16'
]);

function sanitizeColor(c, fallback) {
  if (!c || typeof c !== 'string') return fallback;
  const lower = c.trim().toLowerCase();
  if (LEGACY_COLORS.has(lower)) {
    return fallback;
  }
  return c;
}

function minimalOptions(option, isDark = false) {
  const tokens = getThemeTokens(isDark);
  const chartTokens = tokens.chart;
  const activePalette = chartTokens.palette;
  const labelColor = chartTokens.text;
  const headingColor = chartTokens.title;
  const axisLineColor = chartTokens.axisLine;
  const splitLineColor = chartTokens.splitLine;
  const tooltipBg = chartTokens.tooltipBg;
  const tooltipBorder = chartTokens.tooltipBorder;
  const tooltipText = chartTokens.tooltipText;
  const baseTextColor = chartTokens.text;

  const mergeAxis = a => {
    if (!a) return a;
    return {
      ...a,
      axisLabel: {
        fontSize: 11,
        ...a?.axisLabel,
        color: sanitizeColor(a?.axisLabel?.color, labelColor),
      },
      nameTextStyle: {
        fontSize: 11,
        fontWeight: 600,
        ...a?.nameTextStyle,
        color: sanitizeColor(a?.nameTextStyle?.color, headingColor),
      },
      axisLine: {
        ...a?.axisLine,
        lineStyle: {
          ...a?.axisLine?.lineStyle,
          color: sanitizeColor(a?.axisLine?.lineStyle?.color, axisLineColor),
        },
      },
      splitLine: {
        show: a?.type === 'value',
        ...a?.splitLine,
        lineStyle: {
          ...a?.splitLine?.lineStyle,
          color: sanitizeColor(a?.splitLine?.lineStyle?.color, splitLineColor),
        },
      },
    };
  };

  const axes = axis => (Array.isArray(axis) ? axis.map(mergeAxis) : mergeAxis(axis));

  let legendConfig = undefined;
  if (option.legend === false || (option.legend && option.legend.show === false)) {
    legendConfig = { show: false };
  } else if (option.legend) {
    legendConfig = {
      pageTextStyle: { color: labelColor },
      ...option.legend,
      textStyle: {
        fontSize: 11,
        fontWeight: 600,
        ...option.legend.textStyle,
        color: sanitizeColor(option.legend.textStyle?.color, headingColor),
      },
    };
  }

  const sanitizedSeries = (option.series || []).map((s, index) => {
    const fallbackColor = activePalette[index % activePalette.length];
    const seriesColor = sanitizeColor(s.itemStyle?.color, fallbackColor);

    let sanitizedData = s.data;
    if (Array.isArray(s.data)) {
      sanitizedData = s.data.map((d, dIdx) => {
        if (d && typeof d === 'object' && !Array.isArray(d)) {
          const itemColor = d.color ? sanitizeColor(d.color, activePalette[dIdx % activePalette.length]) : undefined;
          const itemStyleColor = d.itemStyle?.color ? sanitizeColor(d.itemStyle.color, activePalette[dIdx % activePalette.length]) : undefined;
          const itemBorderColor = d.itemStyle?.borderColor ? sanitizeColor(d.itemStyle.borderColor, tokens.colors.surface) : undefined;
          return {
            ...d,
            ...(itemColor ? { color: itemColor } : {}),
            itemStyle: {
              ...d.itemStyle,
              ...(itemStyleColor ? { color: itemStyleColor } : {}),
              ...(itemBorderColor ? { borderColor: itemBorderColor } : {}),
            },
          };
        }
        return d;
      });
    }

    return {
      smooth: s.smooth ?? false,
      ...s,
      itemStyle: {
        shadowBlur: 0,
        borderRadius: s.type === 'bar' ? 2 : undefined,
        ...s.itemStyle,
        color: seriesColor,
        borderColor: sanitizeColor(s.itemStyle?.borderColor, tokens.colors.surface),
      },
      lineStyle: {
        width: 2,
        shadowBlur: 0,
        ...s.lineStyle,
        color: sanitizeColor(s.lineStyle?.color, seriesColor),
      },
      label: s.label ? {
        ...s.label,
        color: sanitizeColor(s.label?.color, tokens.colors.textSecondary),
      } : undefined,
      areaStyle: s.areaStyle ? {
        opacity: isDark ? 0.15 : 0.08,
        color: seriesColor,
        ...s.areaStyle,
      } : undefined,
      emphasis: {
        scale: false,
        ...s.emphasis,
        itemStyle: { shadowBlur: 0, ...s.emphasis?.itemStyle },
      },
      data: sanitizedData,
    };
  });

  const sanitizedDataZoom = option.dataZoom ? option.dataZoom.map(dz => {
    if (dz.type === 'slider') {
      return {
        ...dz,
        borderColor: tokens.colors.borderStrong,
        fillerColor: tokens.colors.mint,
        handleStyle: {
          color: tokens.colors.brandAccent,
          ...dz.handleStyle,
        },
        textStyle: {
          color: tokens.colors.textSecondary,
          fontSize: 10,
          ...dz.textStyle,
        },
      };
    }
    return dz;
  }) : undefined;

  return {
    color: activePalette,
    backgroundColor: 'transparent',
    animation: false,
    aria: { enabled: true },
    textStyle: { color: baseTextColor, fontFamily: 'Figtree, system-ui, sans-serif' },
    ...option,
    tooltip: option.tooltip ? {
      confine: true,
      borderWidth: 1,
      ...option.tooltip,
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      textStyle: {
        fontSize: 12,
        fontFamily: 'Figtree, system-ui, sans-serif',
        ...option.tooltip?.textStyle,
        color: tooltipText,
      },
      extraCssText: isDark ? 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); border-radius: 8px;' : 'box-shadow: 0 4px 14px rgba(11, 31, 58, 0.12); border-radius: 8px;',
    } : undefined,
    ...(legendConfig !== undefined ? { legend: legendConfig } : {}),
    ...(option.xAxis ? { xAxis: axes(option.xAxis) } : {}),
    ...(option.yAxis ? { yAxis: axes(option.yAxis) } : {}),
    ...(sanitizedDataZoom ? { dataZoom: sanitizedDataZoom } : {}),
    series: sanitizedSeries,
  };
}

export default function SafeReactECharts({ option = {}, style, onEvents, opts = {}, presentationTheme }) {
  const container = useRef(null);
  const instance = useRef(null);
  const handlers = useRef(onEvents);
  handlers.current = onEvents;
  const [error, setError] = useState(false);

  let themeContext;
  try {
    themeContext = useTheme();
  } catch (e) {
    themeContext = null;
  }
  const isDark = themeContext ? themeContext.isDark : isCurrentThemeDark();

  useEffect(() => {
    const node = container.current;
    if (!node) return;
    const chart = echarts.init(node, null, { renderer: opts.renderer || 'canvas' });
    instance.current = chart;
    const observer = new ResizeObserver(() => { if (node.clientWidth && node.clientHeight) chart.resize(); });
    observer.observe(node);
    return () => { observer.disconnect(); chart.dispose(); instance.current = null; };
  }, []);

  useEffect(() => {
    try {
      if (instance.current) {
        instance.current.setOption(presentationTheme ? slideChartOptions(option, presentationTheme) : minimalOptions(option, isDark), true);
        instance.current.resize();
        setError(false);
      }
    } catch (err) {
      console.warn('Chart rendering failed', err);
      setError(true);
    }
  }, [option, isDark, presentationTheme]);

  const eventNames = Object.keys(onEvents || {}).sort().join('|');
  useEffect(() => {
    const chart = instance.current;
    if (!chart) return;
    const events = eventNames ? eventNames.split('|') : [];
    const bindings = events.map(name => [name, params => handlers.current?.[name]?.(params)]);
    bindings.forEach(([name, callback]) => chart.on(name, callback));
    return () => bindings.forEach(([name, callback]) => chart.off(name, callback));
  }, [eventNames]);

  return (
    <div className="minimal-chart" style={{ minWidth: 0, width: '100%', maxWidth: '100%', overflow: 'hidden' }}>
      <div ref={container} style={{ height: 300, width: '100%', maxWidth: '100%', overflow: 'hidden', ...style }} />
      {error && <p role="status">Chart unavailable. Open the data table to inspect the values.</p>}
    </div>
  );
}
