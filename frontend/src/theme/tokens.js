/**
 * SCSS is the single palette source. The chart adapter is generated automatically
 * by Vite (including SCSS edits during development) and npm run test:theme.
 */
import { lightTokens, darkTokens } from './tokens.generated.js';
export { lightTokens, darkTokens };
export const getThemeTokens = (isDark = false) => (isDark ? darkTokens : lightTokens);
export const getChartTokens = (isDark = false) => getThemeTokens(isDark).chart;
