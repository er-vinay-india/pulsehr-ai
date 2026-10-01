import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { SLIDE_THEMES, getSlideTheme, contrastRatio, photoScrimOpacity, slideTagStyle } from '../src/theme/slideTokens.js';
import { slideChartOptions } from '../src/theme/slideChartOptions.js';
import { buildSlideHtml } from '../src/utils/exporter/slideHtmlBuilder.js';
import { generateFullPresentationHtml } from '../src/utils/exporter/exportTemplate.js';
let checks=0; const check=(value,message)=>{assert.ok(value,message);checks++;};
const chart={categories:['North','South'],series:[{name:'Attendance',values:[10,20]}]};
const sample={title:'Contrast audit',subtitle:'Small captions must remain readable',category:'Evidence',narrative:'[Evidence] **Verified** result [Data Limitation]',bullets:['[Recommendation] Follow up'],metrics:[{label:'Coverage',value:'97%',context:'Audited rows',change:'2%',benchmark:'95%'}],chart,charts:[chart,chart],table:{headers:['Metric','Value'],rows:[['Coverage','97%']]},initiatives:[{title:'Follow up',priority:'High',owner:'Operations',finding:'Verified evidence',success_metric:'97%'}],left_bullets:['Strength'],right_bullets:['Risk']};
const layouts=['title_cover','title_hero','kpi_summary','chart_narrative','full_chart_takeaway','two_charts','comparison_split','action_plan','initiative_detail','methodology_panel','table_detail'];
for(const [id,theme] of Object.entries(SLIDE_THEMES)) {
 const t=getSlideTheme(id);const surfaces=[t.bg_color,t.card_bg,t.surface_alt];
 for(const key of ['primary_text','secondary_text','muted_text','brand_color','accent_color','success_color','danger_color','warning_color']) for(const bg of surfaces) check(contrastRatio(t[key],bg)>=7,`${id} ${key} on ${bg}`);
 for(const color of t.chart_palette) for(const bg of surfaces) check(contrastRatio(color,bg)>=3,`${id} chart graphic`);
 for(const bg of surfaces) check(contrastRatio(t.card_border,bg)>=3,`${id} boundary`);
 for(const tag of ['[Evidence]','[Derived Metric]','[Interpretation]','[Hypothesis]','[Data Limitation]','[Open Question]','[Recommendation]']) {const style=slideTagStyle(tag,t);check(contrastRatio(style.text,style.bg)>=7,`${id} ${tag}`);}
 const old=getSlideTheme({...theme,secondary_text:'#888888',brand_color:'#FF5722'});check(old.secondary_text===t.secondary_text,`${id} saved deck palette upgrade`);
 for(const layout of layouts) {
  const html=buildSlideHtml({...sample,layout},0,1,t);check(!/undefined|\$\{/.test(html),`${id} ${layout} broken HTML`);
  for(const [,fg] of html.matchAll(/(?:^|[;\s])color:\s*(#[\da-f]{6})/gi)) for(const bg of surfaces) check(contrastRatio(fg,bg)>=7,`${id} ${layout} ${fg}`);
 }
 const options=slideChartOptions({xAxis:{axisLabel:{color:'#ffffff'}},yAxis:{},legend:{textStyle:{color:'#888888'}},series:[{type:'bar',label:{position:'inside'},data:[10,20]}]},t);
 check(contrastRatio(options.xAxis.axisLabel.color,t.card_bg)>=7,`${id} axis`);
 check(contrastRatio(options.legend.textStyle.color,t.card_bg)>=7,`${id} legend`);
 check(options.backgroundColor===t.card_bg && options.series[0].label.position==='top',`${id} chart independence`);
 assert.deepEqual(options.series[0].data,[10,20]);
 for(const requested of [0,70,90,100]) {
  const opacity=photoScrimOpacity({scrim_opacity:requested},t);
  for(const pixel of [0,255]) {
   const bg='#'+[1,3,5].map(i=>Math.round(parseInt(t.bg_color.slice(i,i+2),16)*opacity+pixel*(1-opacity)).toString(16).padStart(2,'0')).join('');
   for(const key of ['primary_text','secondary_text','muted_text','brand_color','accent_color','success_color','danger_color','warning_color']) check(contrastRatio(t[key],bg)>=7,`${id} photo ${pixel} ${key}`);
  }
 }
 const doc=generateFullPresentationHtml('Audit',buildSlideHtml({...sample,layout:'title_cover'},0,1,t),1,t);check(doc.includes(`--slide-bg: ${t.bg_color}`),`${id} document background`);
}
const source=JSON.parse(await readFile(new URL('../../backend/app/services/presentation/templates/themes.json',import.meta.url)));assert.deepEqual(SLIDE_THEMES,source);
console.log(`${checks} slide contrast checks passed across ${Object.keys(SLIDE_THEMES).length} palettes and ${layouts.length} layouts.`);
