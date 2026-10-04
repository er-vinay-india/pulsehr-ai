import React from 'react';
import { sanitizeTitle, sanitizeText } from './surfaceSanitizer';

/**
 * SurfaceGuard.Card
 * Universal card wrapper for dashboard elements (Exception Watch, Briefing, Outlook, Synthesis).
 * Guarantees that card headers, titles, subtitles, badges, and captions never contain raw tokens.
 */
export default function SurfaceGuardCard({
  title,
  subtitle,
  badge,
  caption,
  children,
  className = '',
  style = {},
  showHeader = false,
  ...rest
}) {
  const cleanTitle = title ? sanitizeTitle(title) : '';
  const cleanSubtitle = subtitle ? sanitizeText(subtitle) : '';
  const cleanBadge = badge ? sanitizeText(badge) : '';
  const cleanCaption = caption ? sanitizeText(caption) : '';

  if (typeof children === 'function') {
    return children({
      cleanTitle,
      cleanSubtitle,
      cleanBadge,
      cleanCaption,
      rawTitle: title
    });
  }

  return (
    <div className={`surface-guard-card ${className}`} style={style} {...rest}>
      {showHeader && (cleanTitle || cleanBadge) && (
        <div className="surface-guard-card-header" style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            {cleanTitle && <h3 style={{ margin: 0, fontWeight: 700 }}>{cleanTitle}</h3>}
            {cleanSubtitle && <p style={{ margin: '0.25rem 0 0 0', opacity: 0.8, fontSize: '0.9rem' }}>{cleanSubtitle}</p>}
          </div>
          {cleanBadge && <span className="badge">{cleanBadge}</span>}
        </div>
      )}
      {children}
      {cleanCaption && (
        <div className="surface-guard-card-caption" style={{ marginTop: '0.75rem', fontSize: '0.85rem', opacity: 0.75 }}>
          {cleanCaption}
        </div>
      )}
    </div>
  );
}
