import { useContext, createContext } from 'react';
import { sanitizeText, sanitizeTitle, sanitizeMetric, hasUnderscores } from './surfaceSanitizer';

export const SurfaceGuardContext = createContext({
  surface: 'default',
  sanitize: sanitizeText,
  sanitizeTitle: sanitizeTitle,
  sanitizeMetric: sanitizeMetric,
  hasUnderscores: hasUnderscores
});

/**
 * Hook to access SurfaceGuard text sanitation and policy invariants.
 */
export function useSurfaceGuard() {
  return useContext(SurfaceGuardContext);
}
