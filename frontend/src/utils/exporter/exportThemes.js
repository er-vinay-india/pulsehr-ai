import { SLIDE_THEMES, getSlideTheme } from '../../theme/slideTokens.js';
// Compatibility adapter for callers of the original HTML-only preset registry.
export const EXPORT_THEMES = Object.fromEntries([...Object.keys(SLIDE_THEMES), 'executive_studio', 'minimal_stark'].map(id => [id, getSlideTheme(id)]));
