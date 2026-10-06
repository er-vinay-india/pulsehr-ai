import { getSlideTheme, photoScrimColor } from '../theme/slideTokens.js';
import { SLIDE_LAYOUT_GEOMETRY } from '../theme/slideLayout.generated.js';
export function slideBackground(slide, input) {
  const theme = getSlideTheme(input);
  const color = theme.bg_color;
  // Specialized diagrams keep their existing geometry on the amber palette.
  if (theme.background_asset && (!SLIDE_LAYOUT_GEOMETRY.supported_layouts.includes(slide.layout || 'chart_narrative') || slide.image_url || slide.talent_9box_data || slide.burnout_strain_data)) {
    return { backgroundColor: color };
  }
  if (theme.background_asset) return {
    backgroundColor: color,
    backgroundImage: `url("/api/presentations/theme-assets/${encodeURIComponent(theme.id)}/background")`,
    backgroundSize: '100% 100%', backgroundPosition: 'center',
  };
  if (!slide.background_image) return { backgroundColor: color };
  const scrim = photoScrimColor(slide, theme);
  return {
    backgroundColor: color,
    backgroundImage: `linear-gradient(${scrim}, ${scrim}), url(${JSON.stringify(slide.background_image)})`,
    backgroundSize: 'cover', backgroundPosition: 'center',
  };
}
