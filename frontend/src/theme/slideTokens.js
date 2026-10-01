import { SLIDE_THEMES, SLIDE_THEME_ALIASES } from './slideThemes.generated.js';
export { SLIDE_THEMES };

// Built-in IDs deliberately use the current preset, including decks saved before a palette fix.
export function getSlideTheme(input = 'executive_dark') {
  const rawId = typeof input === 'string' ? input : input?.id || input?.theme_id;
  const id = String(rawId || 'executive_dark').toLowerCase().replaceAll('-', '_');
  const theme = SLIDE_THEMES[SLIDE_THEME_ALIASES[id] || id] || SLIDE_THEMES.executive_dark;
  return { ...theme, slide_bg: theme.bg_color };
}
export function slideCssVariables(input) {
  const t = getSlideTheme(input);
  return Object.fromEntries(Object.entries({ 'slide-bg':t.bg_color, 'stage-bg':t.stage_bg, 'card-bg':t.card_bg, 'card-bg-alt':t.surface_alt, 'card-border':t.card_border, 'grid-border':t.card_border, 'text-primary':t.primary_text, 'text-secondary':t.secondary_text, 'text-muted':t.muted_text, 'brand-color':t.brand_color, 'accent-color':t.accent_color, 'success-color':t.success_color, 'danger-color':t.danger_color, 'warning-color':t.warning_color, 'font-display':t.font_display, 'font-body':t.font_body, 'font-mono':t.font_mono }).map(([k,v])=>[`--${k}`,v]));
}
export const EVIDENCE_TAG_TOKENS = { '[evidence]':'success_color', '[derived metric]':'brand_color', '[interpretation]':'accent_color', '[hypothesis]':'warning_color', '[data limitation]':'danger_color', '[open question]':'warning_color', '[recommendation]':'accent_color' };
export function slideTagStyle(tag, theme) {
  const t = getSlideTheme(theme);
  const text = t[EVIDENCE_TAG_TOKENS[tag.toLowerCase()]];
  return text ? { bg:t.surface_alt, text, border:text } : null;
}
export function contrastRatio(a,b) {
  const lum = c => [1,3,5].map(i=>parseInt(c.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  const [lo,hi] = [lum(a),lum(b)].sort((x,y)=>x-y); return (hi+.05)/(lo+.05);
}
// Covers every possible photo pixel, rather than assuming the photo is already dark.
export function photoScrimOpacity(slide, theme) {
  const t = getSlideTheme(theme);
  const foregrounds = ['primary_text','secondary_text','muted_text','brand_color','accent_color','success_color','danger_color','warning_color'].map(k=>t[k]);
  const requested = Math.max(0, Math.min(100, Number(slide.scrim_opacity ?? 70) || 0))/100;
  for (let step=Math.ceil(requested*1000);step<=1000;step++) {
    const alpha=step/1000;
    const extremes=[0,255].map(pixel=>'#'+[1,3,5].map(i=>Math.round(parseInt(t.bg_color.slice(i,i+2),16)*alpha+pixel*(1-alpha)).toString(16).padStart(2,'0')).join(''));
    if (foregrounds.every(c=>extremes.every(bg=>contrastRatio(c,bg)>=7.1))) return alpha;
  }
  return 1;
}

export function photoScrimColor(slide, input) {
  const t=getSlideTheme(input);
  return `rgba(${[1,3,5].map(i=>parseInt(t.bg_color.slice(i,i+2),16)).join(',')},${photoScrimOpacity(slide,t)})`;
}
