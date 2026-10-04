import React from 'react';
import { sanitizeText } from './surfaceSanitizer';

/**
 * SurfaceGuard.Text
 * Renders sanitized text with guaranteed zero raw underscores or machine prefixes.
 */
export default function SurfaceGuardText({ children, as = 'span', className, style, ...rest }) {
  if (children === null || children === undefined) return null;

  const raw = typeof children === 'string' || typeof children === 'number'
    ? String(children)
    : '';

  const clean = sanitizeText(raw);
  const Component = as;

  return (
    <Component className={className} style={style} {...rest}>
      {clean}
    </Component>
  );
}
