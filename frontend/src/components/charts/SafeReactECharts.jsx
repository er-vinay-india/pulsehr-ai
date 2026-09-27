import React, { useRef, useEffect, useState } from 'react';
import * as echarts from 'echarts';
import { lightPalette, darkPalette, isCurrentThemeDark } from './chartOptions';
import { useTheme } from '../../context/ThemeContext';
import '../../styles/minimal-charts.scss';

function minimalOptions(option, isDark = false) {
  const activePalette = isDark ? darkPalette : lightPalette;
  const labelColor = isDark ? '#CBD5E1' : '#334155';
  const axisLineColor = isDark ? '#26384D' : '#CBD5E1';
  const splitLineColor = isDark ? 'rgba(248, 250, 252, 0.08)' : 'rgba(11, 31, 58, 0.08)';
  const tooltipBg = isDark ? '#172A40' : '#FFFFFF';
  const tooltipBorder = isDark ? '#26384D' : '#CBD5E1';
  const tooltipText = isDark ? '#F8FAFC' : '#0B1F3A';
  const baseTextColor = isDark ? '#F8FAFC' : '#0B1F3A';

  const mergeAxis = a => {
    if (!a) return a;
    return {
      ...a,
      axisLabel: {
        color: labelColor,
        fontSize: 12,
        ...a?.axisLabel,
      },
      axisLine: {
        ...a?.axisLine,
        lineStyle: {
          color: axisLineColor,
          ...a?.axisLine?.lineStyle,
        },
      },
      splitLine: {
        show: a?.type === 'value',
        ...a?.splitLine,
        lineStyle: {
          color: splitLineColor,
          ...a?.splitLine?.lineStyle,
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
      textStyle: { color: labelColor, fontSize: 12, ...option.legend.textStyle },
    };
  }

  return {
    color: activePalette,
    backgroundColor: 'transparent',
    animation: false,
    aria: { enabled: true },
    textStyle: { color: baseTextColor, fontFamily: 'Figtree, system-ui, sans-serif' },
    ...option,
    tooltip: option.tooltip ? {
      confine: true,
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      borderWidth: 1,
      extraCssText: isDark ? 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); border-radius: 8px;' : 'box-shadow: 0 4px 14px rgba(11, 31, 58, 0.12); border-radius: 8px;',
      ...option.tooltip,
      textStyle: { color: tooltipText, fontSize: 13, ...option.tooltip?.textStyle },
    } : undefined,
    ...(legendConfig !== undefined ? { legend: legendConfig } : {}),
    ...(option.xAxis ? { xAxis: axes(option.xAxis) } : {}),
    ...(option.yAxis ? { yAxis: axes(option.yAxis) } : {}),
    series: (option.series || []).map((s, index) => ({
      smooth: false,
      ...s,
      itemStyle: {
        shadowBlur: 0,
        ...(s.type === 'bar' ? { color: activePalette[index % activePalette.length], borderRadius: 2 } : {}),
        ...s.itemStyle,
      },
      lineStyle: {
        width: 2,
        shadowBlur: 0,
        ...s.lineStyle,
      },
      areaStyle: s.areaStyle ? {
        opacity: isDark ? 0.15 : 0.08,
        color: activePalette[0],
        ...s.areaStyle,
      } : undefined,
      emphasis: {
        scale: false,
        ...s.emphasis,
        itemStyle: { shadowBlur: 0, ...s.emphasis?.itemStyle },
      },
    })),
  };
}

export default function SafeReactECharts({ option = {}, style, onEvents, opts = {} }) {
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
        instance.current.setOption(minimalOptions(option, isDark), true);
        instance.current.resize();
        setError(false);
      }
    } catch (err) {
      console.warn('Chart rendering failed', err);
      setError(true);
    }
  }, [option, isDark]);

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
