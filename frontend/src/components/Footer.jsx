import React from "react";
import highviewLogo from "../assets/highview-logo.png";

export default function Footer() {
  return (
    <footer className="app-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <img src={highviewLogo} alt="HighView Logo" className="footer-logo-img" />
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
