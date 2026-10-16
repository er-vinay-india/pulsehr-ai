/**
 * NavigationIntentRegistry.js
 *
 * Centralized HighView Navigation Intent Registry.
 * Executive Dashboard components emit navigation intents rather than
 * manipulating window.location or window.history directly.
 */

export const NAVIGATION_INTENTS = Object.freeze({
  NAVIGATE_TAB: "NAVIGATE_TAB",
  OPEN_UPLOAD: "OPEN_UPLOAD",
  OPEN_EXPLORER: "OPEN_EXPLORER",
  OPEN_EVIDENCE: "OPEN_EVIDENCE",
  CREATE_PRESENTATION: "CREATE_PRESENTATION",
});

/**
 * Dispatch navigation intent safely through application shell callbacks.
 * Fallbacks to history/hash only at the application shell boundary.
 */
export function dispatchNavigationIntent(intent, payload = {}, handlers = {}) {
  const { onNavigateTab, onOpenUpload } = handlers;

  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("highview:navigation-intent", { detail: { intent, payload } })
    );
  }

  switch (intent) {
    case NAVIGATION_INTENTS.OPEN_UPLOAD:
      if (typeof onOpenUpload === "function") {
        onOpenUpload();
      } else if (typeof onNavigateTab === "function") {
        onNavigateTab("upload");
      } else {
        window.location.hash = "upload";
      }
      break;

    case NAVIGATION_INTENTS.NAVIGATE_TAB:
      if (typeof onNavigateTab === "function") {
        onNavigateTab(payload.tab || "adaptive");
      } else {
        window.location.hash = payload.tab || "adaptive";
      }
      break;

    case NAVIGATION_INTENTS.OPEN_EXPLORER:
      if (typeof onNavigateTab === "function") {
        onNavigateTab("explorer");
      } else {
        window.location.hash = "explorer";
      }
      break;

    case NAVIGATION_INTENTS.OPEN_EVIDENCE:
      if (typeof onNavigateTab === "function") {
        onNavigateTab("explorer");
      } else {
        window.location.hash = "explorer";
      }
      break;

    case NAVIGATION_INTENTS.CREATE_PRESENTATION:
      if (typeof onNavigateTab === "function") {
        onNavigateTab("presentation");
      } else {
        window.location.hash = "presentation";
      }
      break;

    default:
      console.warn(`[NavigationIntentRegistry] Unrecognized navigation intent: ${intent}`);
      break;
  }
}
