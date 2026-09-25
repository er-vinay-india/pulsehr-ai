import React, { useRef, useEffect, useState } from 'react';
import * as echarts from 'echarts';
import { palette } from './chartOptions';
import '../../styles/minimal-charts.scss';

function minimalOptions(option) {
  const mergeAxis = a => {
    if (!a) return a;
    return {
      ...a,
      axisLabel: {
        color: '#cbd5e1',
        fontSize: 12,
        ...a?.axisLabel,
      },
      axisLine: {
        ...a?.axisLine,
        lineStyle: {
          color: '#64748b',
          ...a?.axisLine?.lineStyle,
        },
      },
      splitLine: {
        show: a?.type === 'value',
        ...a?.splitLine,
        lineStyle: {
          color: '#ffffff12',
          ...a?.splitLine?.lineStyle,
        },
      },
    };
  };

  const axes = axis => (Array.isArray(axis) ? axis.map(mergeAxis) : mergeAxis(axis));

  // If legend is explicitly false or has show: false, honor that.
  // If not provided in option at all, do not inject an unwanted default legend.
  let legendConfig = undefined;
  if (option.legend === false || (option.legend && option.legend.show === false)) {
    legendConfig = { show: false };
  } else if (option.legend) {
    legendConfig = {
      pageTextStyle: { color: '#cbd5e1' },
      ...option.legend,
      textStyle: { color: '#cbd5e1', fontSize: 12, ...option.legend.textStyle },
    };
  }

  return {
    color: palette,
    backgroundColor: 'transparent',
    animation: false,
    aria: { enabled: true },
    textStyle: { color: '#e2e8f0', fontFamily: 'system-ui, sans-serif' },
    ...option,
    tooltip: option.tooltip ? {
      confine: true,
      backgroundColor: '#18212f',
      borderColor: '#64748b',
      ...option.tooltip,
      textStyle: { color: '#f1f5f9', fontSize: 13, ...option.tooltip?.textStyle },
    } : undefined,
    ...(legendConfig !== undefined ? { legend: legendConfig } : {}),
    ...(option.xAxis ? { xAxis: axes(option.xAxis) } : {}),
    ...(option.yAxis ? { yAxis: axes(option.yAxis) } : {}),
    series: (option.series || []).map((s, index) => ({
      smooth: false,
      ...s,
      itemStyle: {
        shadowBlur: 0,
        ...(s.type === 'bar' ? { color: palette[index % palette.length], borderRadius: 2 } : {}),
        ...s.itemStyle,
      },
      lineStyle: {
        width: 2,
        shadowBlur: 0,
        ...s.lineStyle,
      },
      areaStyle: s.areaStyle ? {
        opacity: 0.06,
        color: palette[0],
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
  useEffect(() => {
    const node = container.current;
    const chart = echarts.init(node, null, { renderer: opts.renderer || 'canvas' });
    instance.current = chart;
    const observer = new ResizeObserver(() => { if (node.clientWidth && node.clientHeight) chart.resize(); });
    observer.observe(node);
    return () => { observer.disconnect(); chart.dispose(); instance.current = null; };
  }, []);
  useEffect(() => {
    try {
      instance.current?.setOption(minimalOptions(option), true);
      instance.current?.resize();
      setError(false);
    }
    catch (err) { console.warn('Chart rendering failed', err); setError(true); }
  }, [option]);
  const eventNames = Object.keys(onEvents || {}).sort().join('|');
  useEffect(() => {
    const chart = instance.current;
    const events = eventNames ? eventNames.split('|') : [];
    const bindings = events.map(name => [name, params => handlers.current?.[name]?.(params)]);
    bindings.forEach(([name, callback]) => chart.on(name, callback));
    return () => bindings.forEach(([name, callback]) => chart.off(name, callback));
  }, [eventNames]);
  return <div className="minimal-chart" style={{ minWidth: 0, width: '100%', maxWidth: '100%', overflow: 'hidden' }}>
    <div ref={container} style={{ height: 300, width: '100%', maxWidth: '100%', overflow: 'hidden', ...style }} />
    {error && <p role="status">Chart unavailable. Open the data table to inspect the values.</p>}
  </div>;
}
