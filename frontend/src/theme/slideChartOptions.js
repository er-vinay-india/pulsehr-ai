import { getSlideTheme } from './slideTokens.js';
// Presentation charts follow their deck palette even when the app shell changes mode.
export function slideChartOptions(option, input) {
  const t = getSlideTheme(input);
  const axis = a => ({ ...a, triggerEvent: true, axisLabel:{...a.axisLabel,color:t.secondary_text}, nameTextStyle:{...a.nameTextStyle,color:t.secondary_text}, axisLine:{...a.axisLine,lineStyle:{...a.axisLine?.lineStyle,color:t.card_border}}, splitLine:{...a.splitLine,lineStyle:{...a.splitLine?.lineStyle,color:t.card_border}} });
  const axes = a => Array.isArray(a) ? a.map(axis) : axis(a);
  return {
    ...option, color:t.chart_palette, backgroundColor:t.card_bg,
    textStyle:{...option.textStyle,color:t.primary_text,fontFamily:t.font_body},
    ...(option.title ? {title:{...option.title,textStyle:{...option.title.textStyle,color:t.primary_text},subtextStyle:{...option.title.subtextStyle,color:t.secondary_text}}}:{}),
    ...(option.legend && option.legend !== false ? {legend:{...option.legend,triggerEvent:true,tooltip:{show:true},textStyle:{...option.legend.textStyle,color:t.secondary_text},pageTextStyle:{color:t.secondary_text},inactiveColor:t.muted_text}}:{}),
    ...(option.xAxis ? {xAxis:axes(option.xAxis)}:{}), ...(option.yAxis ? {yAxis:axes(option.yAxis)}:{}),
    ...(option.tooltip ? {tooltip:{...option.tooltip,backgroundColor:t.card_bg,borderColor:t.card_border,textStyle:{...option.tooltip.textStyle,color:t.primary_text}}}:{}),
    series:(option.series || []).map((s,i)=>{
      const isTransparent = s.name === 'Helper Base' || s.itemStyle?.color === 'transparent';
      const isCustomColorFunc = typeof s.itemStyle?.color === 'function';
      const isSpecialType = s.type === 'pie' || s.type === 'tree';
      const color = t.chart_palette[i%t.chart_palette.length];
      const seriesColor = isTransparent ? 'transparent' : (isCustomColorFunc ? s.itemStyle.color : (isSpecialType ? undefined : color));
      const borderColor = isTransparent ? 'transparent' : t.card_bg;
      return {
        ...s,
        itemStyle: {
          ...s.itemStyle,
          color: seriesColor,
          borderColor: borderColor
        },
        lineStyle: { ...s.lineStyle, color: isTransparent ? 'transparent' : color },
        label: {
          ...s.label,
          color: t.primary_text,
          position: s.type==='pie' ? 'outside' : (s.label?.position?.startsWith('inside') ? 'top' : s.label?.position)
        },
        emphasis: {
          ...s.emphasis,
          itemStyle: isTransparent ? { color: 'transparent', borderColor: 'transparent' } : s.emphasis?.itemStyle,
          label: { ...s.emphasis?.label, color: t.primary_text }
        },
        data: s.data?.map(d=>d && typeof d==='object' && !Array.isArray(d)
          ? { ...d, itemStyle: { ...d.itemStyle, color: isTransparent ? 'transparent' : (d.itemStyle?.color || undefined), borderColor }, label: { ...d.label, color: t.primary_text } }
          : d)
      };
    })
  };
}
