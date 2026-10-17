/**
 * HighView Frontend Centralized Configuration & Environment Defaults
 * 
 * Complies with 12-factor application architecture by consuming Vite environment
 * variables with safe, standard fallbacks for local and containerized deployments.
 */

// Central API Base URL (defaults to relative /api for reverse-proxy or Vite proxy)
export const API_BASE =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE) ||
  "/api";

// Fallback workplace stock photo for presentation slides when no image is provided
export const DEFAULT_FALLBACK_IMAGE_URL =
  "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1600&q=80";

// Ingestion and file processing timing (milliseconds)
export const INGESTION_POLL_INTERVAL_MS = 400;
export const INGESTION_COMPLETION_DELAY_MS = 600;

// UI Notification auto-dismiss timing
export const NOTIFICATION_DISMISS_DELAY_MS = 8000;

// Presentation generation & visual QA polling intervals
export const PRESENTATION_ACTIVE_POLL_MS = 250;
export const PRESENTATION_IDLE_POLL_MS = 2500;
export const IMAGE_PICKER_TIMEOUT_MS = 10000;
