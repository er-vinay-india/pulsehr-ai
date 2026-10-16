/**
 * ProductErrorSanitizer.js
 *
 * Executive Error Firewall.
 * Sanitizes backend exceptions, HTTP status errors, and diagnostic traces
 * into safe, professional executive copy.
 *
 * Technical error details are preserved for logging/debugging, but NEVER
 * rendered directly to the executive user.
 */

export class ProductError extends Error {
  constructor(message, userMessage, category = "GENERIC", technicalDetails = null) {
    super(message);
    this.name = "ProductError";
    this.userMessage = userMessage;
    this.category = category;
    this.technicalDetails = technicalDetails;
  }
}

/**
 * Sanitize any error (backend API response, network error, or runtime exception)
 * into a structured, executive-safe message object.
 */
export function sanitizeError(err) {
  if (!err) {
    return {
      title: "Notice",
      message: "An unexpected condition occurred.",
      category: "UNKNOWN",
      recoverable: true,
    };
  }

  const rawMessage = typeof err === "string" ? err : err.message || "";
  const rawLower = rawMessage.toLowerCase();

  // 1. Dataset / Workbook Not Found (HTTP 404 or missing records)
  if (
    rawLower.includes("no uploaded sheet found") ||
    rawLower.includes("dataset_id") ||
    rawLower.includes("sheet_id") ||
    rawLower.includes("not found") ||
    rawLower.includes("404")
  ) {
    return {
      title: "Workbook Unavailable",
      message: "The requested workbook is no longer available in the workspace.",
      category: "NOT_FOUND",
      recoverable: true,
      actionText: "Select an uploaded workbook or upload a new spreadsheet.",
    };
  }

  // 2. Network / Server Offline
  if (
    rawLower.includes("failed to fetch") ||
    rawLower.includes("networkerror") ||
    rawLower.includes("connection refused") ||
    rawLower.includes("abort")
  ) {
    return {
      title: "Connection Notice",
      message: "Unable to connect to the HighView service. Please check your network connection.",
      category: "NETWORK",
      recoverable: true,
      actionText: "Retry connection",
    };
  }

  // 3. Calculation / Unsupported Schema / Parsing
  if (
    rawLower.includes("unsupported") ||
    rawLower.includes("cannot compute") ||
    rawLower.includes("statistical") ||
    rawLower.includes("parse")
  ) {
    return {
      title: "Data Structure Notice",
      message: "The selected workbook structure requires additional business columns to compute executive intelligence.",
      category: "DATA_SCHEMA",
      recoverable: true,
      actionText: "Verify column headers and data types in Data Explorer.",
    };
  }

  // 4. Server Internal Error (500, Tracebacks)
  if (
    rawLower.includes("500") ||
    rawLower.includes("traceback") ||
    rawLower.includes("internal server error") ||
    rawLower.includes("syntaxerror")
  ) {
    return {
      title: "Service Notice",
      message: "An internal service condition occurred while processing this workbook.",
      category: "SERVER_ERROR",
      recoverable: true,
      actionText: "Please refresh or try uploading a fresh copy of the workbook.",
    };
  }

  // Fallback generic safe message
  return {
    title: "Intelligence Notice",
    message: "Unable to compute executive intelligence for the selected data.",
    category: "GENERIC",
    recoverable: true,
    actionText: "Select another workbook or upload fresh data.",
  };
}
