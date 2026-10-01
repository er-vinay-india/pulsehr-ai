import { getSlideTheme, photoScrimColor } from '../theme/slideTokens.js';
export function slideBackground(slide, input) {
  const theme = getSlideTheme(input);
  const color = theme.bg_color;
  if (!slide.background_image) return { backgroundColor: color };
  const scrim = photoScrimColor(slide, theme);
  return {
    backgroundColor: color,
    backgroundImage: `linear-gradient(${scrim}, ${scrim}), url(${JSON.stringify(slide.background_image)})`,
    backgroundSize: 'cover', backgroundPosition: 'center',
  };
}
