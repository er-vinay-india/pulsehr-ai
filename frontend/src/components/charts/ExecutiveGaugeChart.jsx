import React, { useMemo } from 'react';
import ReactECharts from './SafeReactECharts';

export default function ExecutiveGaugeChart({
  score = null,
  title = 'Health Index',
  subtitle = 'Operational Stability',
  height = 190,
  isInverted = false // if true, higher score is worse (e.g. risk/attrition)
}) {
  const option = useMemo(() => {
    const value = Math.min(100, Math.max(0, Math.round(score)));
    
    // Normal: Green > 70, Yellow 40-70, Red < 40
    // Inverted: Green < 30, Yellow 30-60, Red > 60
    const colorStops = isInverted
      ? [
          [0.3, '#34d399'],
          [0.6, '#fbbb27'],
          [1.0, '#fb7185']
        ]
      : [
          [0.4, '#fb7185'],
          [0.7, '#fbbb27'],
          [1.0, '#34d399']
        ];

    return {
      backgroundColor: 'transparent',
      series: [
        {
          type: 'gauge',
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          splitNumber: 5,
          itemStyle: {
            color: isInverted
              ? (value > 60 ? '#fb7185' : value > 30 ? '#fbbb27' : '#34d399')
              : (value >= 70 ? '#34d399' : value >= 40 ? '#fbbb27' : '#fb7185'),
            shadowColor: 'rgba(0, 0, 0, 0.4)',
            shadowBlur: 10,
            shadowOffsetX: 2,
            shadowOffsetY: 2
          },
          progress: {
            show: true,
            roundCap: true,
            width: 10
          },
          pointer: {
            show: false,
            icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
            length: '65%',
            width: 8,
            offsetCenter: [0, '-10%'],
            itemStyle: {
              color: 'auto'
            }
          },
          axisLine: {
            roundCap: true,
            lineStyle: {
              width: 10,
              color: [[1, '#334155']]
            }
          },
          axisTick: {
            show: false,
            distance: -18,
            splitNumber: 2,
            lineStyle: {
              width: 1,
              color: '#524940'
            }
          },
          splitLine: {
            show: false,
            distance: -22,
            length: 8,
            lineStyle: {
              width: 2,
              color: '#ded5cb'
            }
          },
          axisLabel: {
            distance: -14,
            color: '#ded5cb',
            fontSize: 9
          },
          anchor: {
            show: false,
            showAbove: true,
            size: 14,
            itemStyle: {
              borderWidth: 3,
              borderColor: '#1e293b'
            }
          },
          title: {
            show: true,
            offsetCenter: [0, '72%'],
            fontSize: 11,
            color: '#ded5cb',
            fontWeight: 500
          },
          detail: {
            valueAnimation: true,
            fontSize: 24,
            fontWeight: 700,
            offsetCenter: [0, '40%'],
            formatter: '{value}%',
            color: 'inherit'
          },
          data: [
            {
              value: value,
              name: subtitle || title
            }
          ]
        }
      ]
    };
  }, [score, title, subtitle, isInverted]);

  if (score == null || !Number.isFinite(Number(score))) return <p>No score available.</p>;

  return (
    <div className="executive-gauge-card">
      {title && <div className="gauge-header-title">{title}</div>}
      <ReactECharts
        option={option}
        style={{ height: `${height}px`, width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
}
