import React from "react";
import { BrainCircuit } from "lucide-react";

export default function Footer() {
  return (
    <footer className="app-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <BrainCircuit size={20} />
          <div className="footer-copy">
            <strong>PulseHR AI</strong> · Executive Workforce Analytics & RAG Tabular Intelligence
          </div>
        </div>
        <div className="footer-badge">
          <span className="dot" />
          <span>Spreadsheet analytics · Source-linked answers</span>
        </div>
      </div>
    </footer>
  );
}
