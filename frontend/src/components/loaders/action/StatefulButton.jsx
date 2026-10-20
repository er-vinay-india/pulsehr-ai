import React, { useRef, useEffect, useState } from "react";
import Spinner from "../primitives/Spinner";
import { Check, AlertCircle } from "lucide-react";

/**
 * StatefulButton
 * Interactive button with seamless Idle -> Loading -> Success -> Idle lifecycle.
 * Locks width on click to prevent layout shift.
 */
export default function StatefulButton({
  status = "idle", // 'idle' | 'loading' | 'success' | 'error'
  loadingText = "Processing…",
  successText = "Saved",
  errorText = "Failed",
  onClick = () => {},
  disabled = false,
  children,
  className = "",
  style = {},
  variant = "primary", // 'primary' | 'secondary' | 'danger'
  type = "button",
  ...rest
}) {
  const btnRef = useRef(null);
  const [fixedWidth, setFixedWidth] = useState(null);

  useEffect(() => {
    if (status === "loading" && btnRef.current && !fixedWidth) {
      setFixedWidth(btnRef.current.offsetWidth);
    } else if (status === "idle") {
      setFixedWidth(null);
    }
  }, [status, fixedWidth]);

  const isLoading = status === "loading";
  const isSuccess = status === "success";
  const isError = status === "error";

  return (
    <button
      ref={btnRef}
      type={type}
      onClick={isLoading || disabled ? undefined : onClick}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
      className={`highview-stateful-btn ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "6px",
        minHeight: "36px",
        padding: "8px 16px",
        borderRadius: "8px",
        fontSize: "0.85rem",
        fontWeight: 600,
        cursor: disabled || isLoading ? "not-allowed" : "pointer",
        transition: "all 0.18s ease",
        width: fixedWidth ? `${fixedWidth}px` : "auto",
        ...style,
      }}
      {...rest}
    >
      {isLoading ? (
        <>
          <Spinner size={14} strokeWidth={3.5} color="currentColor" />
          <span>{loadingText}</span>
        </>
      ) : isSuccess ? (
        <>
          <Check size={14} color="var(--color-success, #075443)" />
          <span>{successText}</span>
        </>
      ) : isError ? (
        <>
          <AlertCircle size={14} color="var(--color-error, #8E1938)" />
          <span>{errorText}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
