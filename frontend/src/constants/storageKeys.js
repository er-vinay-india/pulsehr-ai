/**
 * Centralized Web Storage Keys (localStorage & sessionStorage)
 * 
 * Prevents key collision, typos, and fragmented storage access.
 */

export const STORAGE_KEYS = {
  // LocalStorage: UI Theme persistence ("light" | "dark")
  THEME: "highview_theme",

  // SessionStorage: Cross-page presentation workflow context
  PRESENTATION_SOURCE: "highview_presentation_source",
  PRESENTATION_DASHBOARD_CONTEXT: "presentation_dashboard_context",
};
