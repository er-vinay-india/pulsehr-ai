import { slideChartOptions } from '../../theme/slideChartOptions.js';
import React, { useRef, useEffect, useState } from 'react';
import * as echarts from 'echarts';
import { lightPalette, darkPalette, isCurrentThemeDark } from './chartOptions';
import { getThemeTokens } from '../../theme/tokens';
import { useTheme } from '../../context/ThemeContext';
import { humanizeLabel } from '../visualization/layout/formatters';
import { resolveAxisFormatter, sanitizeOptionFormatters, validateChartFormatters } from '../visualization/layout/chartFormatterValidator';
import { inspectRenderedChartGeometry } from '../visualization/repair/postRenderValidator';
import { repairChartLayout } from '../visualization/repair/repairChartLayout';
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
    const cleanData = Array.isArray(a.data)
      ? a.data.map(item => {
          if (typeof item === 'string') return humanizeLabel(item);
          if (item && typeof item === 'object' && item.value != null) {
            return { ...item, value: humanizeLabel(item.value) };
          }
          return item;
        })
      : a.data;

    return {
      ...a,
      triggerEvent: true,
      name: a.name ? humanizeLabel(a.name) : a.name,
      ...(cleanData ? { data: cleanData } : {}),
      axisLabel: {
        fontSize: 11,
        ...a?.axisLabel,
        color: sanitizeColor(a?.axisLabel?.color, labelColor),
        formatter: (val, idx) => {
          const rawFmt = a?.axisLabel?.formatter;
          let res;
          if (typeof rawFmt === 'function') {
            res = rawFmt(val, idx);
          } else if (typeof rawFmt === 'string') {
            if (rawFmt.includes('{value}')) {
              res = rawFmt.replace(/\{value\}/g, val != null ? String(val) : '');
            } else if (/^(\(.*\)|function|[a-zA-Z0-9_]+)\s*=>/.test(rawFmt)) {
              res = val != null ? `${Math.round(val)}%` : '';
            } else if (/\{[a-zA-Z0-9_]+\}/.test(rawFmt)) {
              res = val != null ? String(val) : '';
            } else if (rawFmt.startsWith('%')) {
              res = `${val != null ? val : ''}${rawFmt}`;
            } else {
              res = `${val != null ? val : ''} ${rawFmt}`.trim();
            }
          } else if (a?.axisLabel?._unit_suffix) {
            res = `${val != null ? val : ''}${a.axisLabel._unit_suffix}`;
          } else {
            res = val;
          }
          return typeof res === 'string' && res.includes('_') ? humanizeLabel(res) : res;
        },
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
      triggerEvent: true,
      tooltip: { show: true },
      formatter: name => (typeof name === 'string' ? humanizeLabel(name) : name),
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
    const seriesName = s.name ? humanizeLabel(s.name) : s.name;

    let sanitizedData = s.data;
    if (Array.isArray(s.data)) {
      sanitizedData = s.data.map((d, dIdx) => {
        if (d && typeof d === 'object' && !Array.isArray(d)) {
          const itemColor = d.color ? sanitizeColor(d.color, activePalette[dIdx % activePalette.length]) : undefined;
          const itemStyleColor = d.itemStyle?.color ? sanitizeColor(d.itemStyle.color, activePalette[dIdx % activePalette.length]) : undefined;
          const itemBorderColor = d.itemStyle?.borderColor ? sanitizeColor(d.itemStyle.borderColor, tokens.colors.surface) : undefined;
          return {
            ...d,
            ...(d.name ? { name: humanizeLabel(d.name) } : {}),
            ...(d.full_name ? { full_name: humanizeLabel(d.full_name) } : {}),
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
      name: seriesName,
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
  const [hoverTooltip, setHoverTooltip] = useState(null);

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
    node._chartInstance = chart;
    if (typeof window !== 'undefined') {
      window.echarts = echarts;
    }

    const handleMouseOver = (params) => {
      if (!params) return;
      if (params.targetType === 'axisLabel' || params.componentType === 'xAxis' || params.componentType === 'yAxis') {
        const fullText = params.value != null ? humanizeLabel(String(params.value)) : '';
        if (fullText) {
          setHoverTooltip({
            text: fullText,
            x: params.event?.offsetX ?? 120,
            y: params.event?.offsetY ?? 120
          });
        }
      } else if (params.componentType === 'legend') {
        if (params.name) {
          setHoverTooltip({
            text: humanizeLabel(params.name),
            x: params.event?.offsetX ?? 120,
            y: params.event?.offsetY ?? 120
          });
        }
      }
    };

    const handleMouseOut = (params) => {
      if (!params || params.targetType === 'axisLabel' || params.componentType === 'xAxis' || params.componentType === 'yAxis' || params.componentType === 'legend') {
        setHoverTooltip(null);
      }
    };

    chart.on('mouseover', handleMouseOver);
    chart.on('mouseout', handleMouseOut);

    const zr = chart.getZr();
    const handleZrMouseMove = (e) => {
      setHoverTooltip(prev => (prev ? { ...prev, x: e.offsetX, y: e.offsetY } : null));
    };
    const handleZrMouseOut = () => {
      setHoverTooltip(null);
    };

    zr.on('mousemove', handleZrMouseMove);
    zr.on('mouseout', handleZrMouseOut);

    const observer = new ResizeObserver(() => { if (node.clientWidth && node.clientHeight) chart.resize(); });
    observer.observe(node);

    return () => {
      observer.disconnect();
      chart.off('mouseover', handleMouseOver);
      chart.off('mouseout', handleMouseOut);
      zr.off('mousemove', handleZrMouseMove);
      zr.off('mouseout', handleZrMouseOut);
      chart.dispose();
      instance.current = null;
    };
  }, []);

  const [repairedOption, setRepairedOption] = useState(null);
  const [visualSafetyReport, setVisualSafetyReport] = useState(null);

  useEffect(() => {
    try {
      if (instance.current) {
        // Pre-render sanitization
        const safeInput = sanitizeOptionFormatters(repairedOption || option);
        const resolved = presentationTheme
          ? slideChartOptions(safeInput, presentationTheme)
          : minimalOptions(safeInput, isDark);

        instance.current.setOption(resolved, true);
        instance.current.resize();
        setError(false);

        // Post-render geometry inspection & adaptive repair loop
        const timer = setTimeout(() => {
          if (!container.current) return;
          const report = inspectRenderedChartGeometry(container.current);
          setVisualSafetyReport(report);

          // If unresolved tokens or overflow detected and not already repaired
          if (!report.passed && !repairedOption) {
            const { repairedOption: nextOption, repairsApplied } = repairChartLayout(safeInput, {
              hasHorizontalOverflow: report.visualSafetyScore.axis_clipping > 0,
              hasVerticalOverflow: report.visualSafetyScore.container_overflow > 0,
            });
            if (repairsApplied.length > 0) {
              setRepairedOption(nextOption);
            }
          }
        }, 60);

        return () => clearTimeout(timer);
      }
    } catch (err) {
      console.warn('Chart rendering failed', err);
      setError(true);
    }
  }, [option, repairedOption, isDark, presentationTheme]);

  const eventNames = Object.keys(onEvents || {}).sort().join('|');
  useEffect(() => {
    const chart = instance.current;
    if (!chart) return;
    const events = eventNames ? eventNames.split('|') : [];
    const bindings = events.map(name => [name, params => handlers.current?.[name]?.(params)]);
    bindings.forEach(([name, callback]) => chart.on(name, callback));
    return () => bindings.forEach(([name, callback]) => chart.off(name, callback));
  }, [eventNames]);

  const effectiveHeight = (repairedOption || option)?._planned_height || (style && style.height) || 300;

  return (
    <div
      className="minimal-chart"
      data-visual-safety-score={visualSafetyReport?.safetyScore ?? 100}
      style={{ position: 'relative', minWidth: 0, width: '100%', maxWidth: '100%', height: effectiveHeight, overflow: 'visible' }}
    >
      <div
        ref={container}
        data-categories={JSON.stringify(option?.xAxis?.data || (Array.isArray(option?.xAxis) ? option?.xAxis[0]?.data : []) || [])}
        style={{ height: '100%', width: '100%', maxWidth: '100%', overflow: 'hidden' }}
      />
      {hoverTooltip && hoverTooltip.text && (
        <div
          role="tooltip"
          aria-hidden="false"
          style={{
            position: 'absolute',
            left: Math.max(12, Math.min(hoverTooltip.x, (container.current?.clientWidth || 300) - 24)),
            top: Math.max(12, hoverTooltip.y - 10),
            transform: 'translate(-50%, -100%)',
            pointerEvents: 'none',
            zIndex: 9999,
            backgroundColor: isDark ? 'rgba(15, 23, 42, 0.96)' : 'rgba(255, 255, 255, 0.98)',
            color: isDark ? '#f8fafc' : '#0f172a',
            border: isDark ? '1px solid rgba(255, 255, 255, 0.15)' : '1px solid rgba(0, 0, 0, 0.12)',
            boxShadow: isDark ? '0 8px 24px rgba(0, 0, 0, 0.5)' : '0 6px 20px rgba(0, 0, 0, 0.12)',
            borderRadius: '6px',
            padding: '5px 10px',
            fontSize: '11.5px',
            fontWeight: 600,
            lineHeight: 1.35,
            whiteSpace: 'normal',
            maxWidth: '300px',
            wordBreak: 'break-word',
            textAlign: 'center',
            backdropFilter: 'blur(8px)',
          }}
        >
          {humanizeLabel(hoverTooltip.text)}
        </div>
      )}
      {error && <p role="status">Chart unavailable. Open the data table to inspect the values.</p>}
    </div>
  );
}
