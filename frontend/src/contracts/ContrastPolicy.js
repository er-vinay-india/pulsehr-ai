/**
 * ContrastPolicy.js
 *
 * Centralized HighView WCAG AAA Accessibility Contrast Policy.
 * Defines required contrast ratios for every semantic role and provides
 * precision color luminance and contrast ratio calculation.
 */

export const CONTRAST_ROLES = Object.freeze({
  TEXT_PRIMARY: "TEXT_PRIMARY",
  TEXT_SECONDARY: "TEXT_SECONDARY",
  ACTION_PRIMARY_TEXT: "ACTION_PRIMARY_TEXT",
  ACTION_SECONDARY_TEXT: "ACTION_SECONDARY_TEXT",
  ACTION_GHOST_TEXT: "ACTION_GHOST_TEXT",
  ICON: "ICON",
  FOCUS_RING: "FOCUS_RING",
  BORDER: "BORDER",
  CHART_LABEL: "CHART_LABEL",
  STATUS: "STATUS",
});

export const CONTRAST_THRESHOLDS = Object.freeze({
  [CONTRAST_ROLES.TEXT_PRIMARY]: 7.0,          // WCAG AAA standard text
  [CONTRAST_ROLES.TEXT_SECONDARY]: 7.0,        // WCAG AAA strict secondary
  [CONTRAST_ROLES.ACTION_PRIMARY_TEXT]: 7.0,   // WCAG AAA primary action
  [CONTRAST_ROLES.ACTION_SECONDARY_TEXT]: 7.0, // WCAG AAA secondary action
  [CONTRAST_ROLES.ACTION_GHOST_TEXT]: 7.0,     // WCAG AAA ghost action
  [CONTRAST_ROLES.ICON]: 3.0,                  // WCAG AA non-text UI component
  [CONTRAST_ROLES.FOCUS_RING]: 3.0,            // WCAG AA focus indicator
  [CONTRAST_ROLES.BORDER]: 3.0,                // WCAG AA graphical object
  [CONTRAST_ROLES.CHART_LABEL]: 4.5,           // WCAG AA chart text
  [CONTRAST_ROLES.STATUS]: 4.5,                // WCAG AA badge status
});

/**
 * Parse an RGB/RGBA string or hex into { r, g, b, a }.
 */
export function parseColor(colorStr) {
  if (!colorStr || typeof colorStr !== "string") {
    return { r: 0, g: 0, b: 0, a: 1 };
  }
  const str = colorStr.trim().toLowerCase();

  // Handle rgb(r, g, b) or rgba(r, g, b, a)
  const rgbMatch = str.match(/rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)/);
  if (rgbMatch) {
    return {
      r: parseInt(rgbMatch[1], 10),
      g: parseInt(rgbMatch[2], 10),
      b: parseInt(rgbMatch[3], 10),
      a: rgbMatch[4] !== undefined ? parseFloat(rgbMatch[4]) : 1,
    };
  }

  // Handle #hex
  if (str.startsWith("#")) {
    let hex = str.slice(1);
    if (hex.length === 3) {
      hex = hex.split("").map((c) => c + c).join("");
    }
    if (hex.length === 6) {
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
        a: 1,
      };
    }
    if (hex.length === 8) {
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
        a: parseInt(hex.slice(6, 8), 16) / 255,
      };
    }
  }

  return { r: 0, g: 0, b: 0, a: 1 };
}

/**
 * Calculate sRGB relative luminance according to WCAG 2.1 formula.
 */
export function getRelativeLuminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map((val) => {
    const s = val / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Calculate contrast ratio between two colors (foreground and background).
 */
export function calculateContrastRatio(fgColor, bgColor) {
  const fg = typeof fgColor === "string" ? parseColor(fgColor) : fgColor;
  const bg = typeof bgColor === "string" ? parseColor(bgColor) : bgColor;

  // Composite semi-transparent foreground over background
  let effectiveFg = fg;
  if (fg.a < 1) {
    effectiveFg = {
      r: Math.round(fg.r * fg.a + bg.r * (1 - fg.a)),
      g: Math.round(fg.g * fg.a + bg.g * (1 - fg.a)),
      b: Math.round(fg.b * fg.a + bg.b * (1 - fg.a)),
    };
  }

  const l1 = getRelativeLuminance(effectiveFg.r, effectiveFg.g, effectiveFg.b);
  const l2 = getRelativeLuminance(bg.r, bg.g, bg.b);

  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);

  return parseFloat(((lighter + 0.05) / (darker + 0.05)).toFixed(2));
}

/**
 * Validate contrast of an element for a given semantic role.
 */
export function validateContrast(fgColor, bgColor, role = CONTRAST_ROLES.TEXT_PRIMARY) {
  const ratio = calculateContrastRatio(fgColor, bgColor);
  const required = CONTRAST_THRESHOLDS[role] || 7.0;
  return {
    ratio,
    required,
    passed: ratio >= required,
    role,
  };
}
