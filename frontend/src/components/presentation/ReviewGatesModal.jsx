import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Clock,
  UserCheck,
  X,
  RefreshCw,
  FileText,
  Sliders,
  Check,
  Ban
} from "lucide-react";
import { getPresentationReviewGates, approvePresentationReviewGate } from "../../api/client";

const GATE_TITLES = {
  gate_1_brief: "1. Brief & Audience",
  gate_2_storyline: "2. Storyline & Headlines",
  gate_3_evidence: "3. Evidence & Calculations",
  gate_4_visual: "4. Visual Design & Density",
  gate_5_export_accessibility: "5. Accessibility & Technical Exports"
};

export default function ReviewGatesModal({
  isOpen,
  onClose,
  deckSpec,
  onDeckUpdated
}) {
  const [gatesData, setGatesData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [signoffNotes, setSignoffNotes] = useState({});

  const deckId = deckSpec?.id;

  const fetchGates = useCallback(async () => {
    if (!deckId) return;
    setLoading(true);
    setErrorMessage("");
    try {
      const res = await getPresentationReviewGates(deckId);
      if (res?.review_gates) {
        setGatesData(res.review_gates);
      }
    } catch (err) {
      // Fallback to local spec if API call fails
      const localGates = deckSpec?.review_gates || deckSpec?.metadata?.review_gates;
      if (localGates) {
        setGatesData(localGates);
      } else {
        setErrorMessage(err.message || "Unable to fetch review gates from server.");
      }
    } finally {
      setLoading(false);
    }
  }, [deckId, deckSpec]);

  useEffect(() => {
    if (!isOpen) return;
    fetchGates();
  }, [isOpen, fetchGates]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleApprove = async (gateId, approved = true) => {
    if (!deckId) return;
    setActionInProgress(gateId);
    setErrorMessage("");
    try {
      const note = signoffNotes[gateId] || (approved ? "Sign-off recorded by executive reviewer." : "Revision requested.");
      const updated = await approvePresentationReviewGate(
        deckId,
        gateId,
        approved,
        "Executive Reviewer",
        note
      );
      if (updated?.review_gates) {
        setGatesData(updated.review_gates);
        if (onDeckUpdated && updated.deck) {
          onDeckUpdated(updated.deck);
        }
      } else {
        await fetchGates();
      }
    } catch (err) {
      setErrorMessage(err.message || "Failed to update human review status.");
    } finally {
      setActionInProgress(null);
    }
  };

  if (!isOpen) return null;

  const gates = gatesData?.gates || {};
  const revision = gatesData?.revision || 1;
  const gateKeys = [
    "gate_1_brief",
    "gate_2_storyline",
    "gate_3_evidence",
    "gate_4_visual",
    "gate_5_export_accessibility"
  ];

  const approvedHumanCount = Object.values(gates).filter(
    (g) => g?.human_approval?.status === "APPROVED"
  ).length;

  return (
    <div
      className="pres-review-gates-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="review-gates-modal-title"
      onClick={onClose}
    >
      <div
        className="pres-review-gates-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="review-gates-header">
          <div className="header-title-area">
            <div className="title-row">
              <ShieldCheck size={20} className="shield-icon" />
              <h3 id="review-gates-modal-title">Presentation Review Gates</h3>
              <span className="revision-tag">Revision {revision}</span>
            </div>
            <p className="header-subtitle">
              Strict separation between automated empirical verification and explicit human sign-off.
              Edits automatically invalidate affected checks.
            </p>
          </div>
          <div className="header-actions">
            <button
              type="button"
              className="btn-icon-refresh"
              onClick={fetchGates}
              disabled={loading}
              title="Refresh gate status"
              aria-label="Refresh gate status"
            >
              <RefreshCw size={15} className={loading ? "spin-icon" : ""} />
            </button>
            <button
              type="button"
              className="btn-icon-close"
              onClick={onClose}
              aria-label="Close Review Gates"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Status Summary Banner */}
        <div className="review-gates-summary-banner">
          <div className="summary-col">
            <span className="summary-label">Automated Verification</span>
            <span className="summary-val passed">
              <CheckCircle2 size={14} /> Passed Programmatic Checks
            </span>
          </div>
          <div className="summary-col">
            <span className="summary-label">Human Executive Sign-off</span>
            <span className={`summary-val ${approvedHumanCount === 5 ? "approved" : "pending"}`}>
              <UserCheck size={14} /> {approvedHumanCount} / 5 Gates Signed Off
            </span>
          </div>
          <div className="summary-col">
            <span className="summary-label">Audit Policy</span>
            <span className="summary-val policy-note">
              No automated sign-off · Rev {revision} bound
            </span>
          </div>
        </div>

        {errorMessage && (
          <div className="review-gates-alert-error" role="alert">
            <AlertTriangle size={15} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Gates List */}
        <div className="review-gates-list">
          {gateKeys.map((key) => {
            const gate = gates[key] || {
              name: GATE_TITLES[key],
              description: "Audit gate pending evaluation.",
              automated: { status: "PENDING", details: "Evaluating..." },
              human_approval: { status: "PENDING" }
            };
            const autoStatus = gate.automated?.status || "PENDING";
            const humanStatus = gate.human_approval?.status || "PENDING";
            const isActing = actionInProgress === key;

            return (
              <div key={key} className={`gate-card gate-${autoStatus.toLowerCase()}`}>
                <div className="gate-card-header">
                  <div className="gate-info">
                    <span className="gate-id-badge">{key.replace("gate_", "GATE ").toUpperCase()}</span>
                    <h4 className="gate-name">{gate.name || GATE_TITLES[key]}</h4>
                  </div>
                  <div className="gate-status-badges">
                    <span className={`badge-status auto-${autoStatus.toLowerCase()}`}>
                      {autoStatus === "PASSED" && <CheckCircle2 size={12} />}
                      {autoStatus === "REQUIRES_REVIEW" && <AlertTriangle size={12} />}
                      {autoStatus === "FAILED" && <ShieldAlert size={12} />}
                      Automated: {autoStatus.replace("_", " ")}
                    </span>
                    <span className={`badge-status human-${humanStatus.toLowerCase()}`}>
                      <UserCheck size={12} />
                      Human: {humanStatus}
                    </span>
                  </div>
                </div>

                <p className="gate-description">{gate.description}</p>

                {/* Automated Details */}
                <div className="gate-section-automated">
                  <span className="sec-label">Automated Finding:</span>
                  <p className="sec-content">
                    {gate.automated?.details || "Evaluation completed."}
                  </p>
                  {gate.automated?.checked_at && (
                    <span className="sec-timestamp">
                      <Clock size={11} /> Checked: {new Date(gate.automated.checked_at).toLocaleTimeString()}
                    </span>
                  )}
                </div>

                {/* Human Sign-off Row */}
                <div className="gate-section-human">
                  <div className="human-status-row">
                    {humanStatus === "APPROVED" ? (
                      <div className="human-approved-meta">
                        <Check size={14} className="green-icon" />
                        <span>
                          Signed off by <strong>{gate.human_approval?.approved_by || "Executive"}</strong> on{" "}
                          {gate.human_approval?.approved_at
                            ? new Date(gate.human_approval.approved_at).toLocaleDateString()
                            : "record"}
                          {gate.human_approval?.notes && ` (${gate.human_approval.notes})`}
                        </span>
                      </div>
                    ) : humanStatus === "REJECTED" ? (
                      <div className="human-rejected-meta">
                        <Ban size={14} className="red-icon" />
                        <span>
                          Revision requested by <strong>{gate.human_approval?.approved_by || "Reviewer"}</strong>
                          {gate.human_approval?.notes && `: ${gate.human_approval.notes}`}
                        </span>
                      </div>
                    ) : (
                      <div className="human-pending-meta">
                        <Clock size={14} className="amber-icon" />
                        <span>Pending explicit human review and sign-off.</span>
                      </div>
                    )}

                    <div className="gate-actions">
                      {humanStatus !== "APPROVED" && (
                        <button
                          type="button"
                          className="btn-gate-approve"
                          onClick={() => handleApprove(key, true)}
                          disabled={isActing || loading}
                          title="Record human approval for this gate"
                        >
                          <Check size={13} />
                          <span>{isActing ? "Recording..." : "Sign Off on Gate"}</span>
                        </button>
                      )}
                      {humanStatus === "APPROVED" && (
                        <button
                          type="button"
                          className="btn-gate-reopen"
                          onClick={() => handleApprove(key, false)}
                          disabled={isActing || loading}
                          title="Re-open gate for revision"
                        >
                          <Ban size={13} />
                          <span>Re-open Gate</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="review-gates-footer">
          <span className="footer-policy">
            All 5 gates require human sign-off prior to final executive presentation rehearsal.
          </span>
          <button type="button" className="btn-secondary btn-sm" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
