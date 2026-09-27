import React from "react";
import { BrainCircuit } from "lucide-react";

export default function Footer() {
  return (
    <footer className="app-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <BrainCircuit size={20} />
          <div className="footer-copy">
            <strong>HighView</strong> · Clarity From Every Sheet. · Powered by HRIDAY
          </div>
        </div>
        <div className="footer-badge">
          <span className="dot" />
          <span>Automated spreadsheet analysis · Executive insights · Powered by HRIDAY</span>
        </div>
      </div>
    </footer>
  );
}
