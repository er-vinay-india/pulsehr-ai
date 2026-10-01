import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
export const slideThemeSource = fileURLToPath(new URL('../../backend/app/services/presentation/templates/themes.json', import.meta.url));
export async function generateSlideTokens() {
  const themes = JSON.parse(await readFile(slideThemeSource, 'utf8'));
  const aliases = { executive_studio: 'executive_dark', minimal_stark: 'clean_light' };
  const variables = { 'stage-bg':'stage_bg', 'slide-bg':'bg_color', 'card-bg':'card_bg', 'card-bg-alt':'surface_alt', 'card-border':'card_border', 'grid-border':'card_border', 'text-primary':'primary_text', 'text-secondary':'secondary_text', 'text-muted':'muted_text', 'brand-color':'brand_color', 'accent-color':'accent_color', 'success-color':'success_color', 'danger-color':'danger_color', 'warning-color':'warning_color', 'chart-primary':'brand_color', 'font-display':'font_display', 'font-body':'font_body', 'font-mono':'font_mono' };
  const css = Object.entries(themes).map(([id,t]) => {
    const ids = [id, ...Object.keys(aliases).filter(a=>aliases[a]===id)];
    return `${ids.flatMap(i=>[`.theme-${i}`, `[data-slide-theme="${i}"]`]).join(',\n')} {\n${Object.entries(variables).map(([k,v])=>`  --${k}: ${t[v]};`).join('\n')}\n  --accent-gradient: linear-gradient(135deg, ${t.brand_color}, ${t.accent_color});\n}\n`;
  }).join('\n');
  const outputs = [
    [new URL('../src/styles/_slide-themes.generated.scss', import.meta.url), `// Generated from presentation/templates/themes.json. Edit that source.\n${css}`],
    [new URL('../src/theme/slideThemes.generated.js', import.meta.url), `// Generated from presentation/templates/themes.json. Edit that source.\nexport const SLIDE_THEMES = ${JSON.stringify(themes,null,2)};\nexport const SLIDE_THEME_ALIASES = ${JSON.stringify(aliases)};\n`]
  ];
  for (const [path,value] of outputs) {
    let previous; try { previous = await readFile(path,'utf8'); } catch {}
    if (previous !== value) await writeFile(path,value);
  }
}
if (process.argv[1] === fileURLToPath(import.meta.url)) await generateSlideTokens();
