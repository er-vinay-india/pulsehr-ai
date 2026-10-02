import { useHRIDAY } from './hriday/HRIDAYProvider.jsx';
import React from "react";
import highviewLogo from "../assets/highview-logo.png";

export default function Footer() {
  const { identity } = useHRIDAY();
  const currentYear = new Date().getFullYear();

  return (
    <footer className="app-footer">
      <div className="footer-inner">
        {/* Left: HighView Logo, Tagline & Copyright */}
        <div className="footer-brand">
          <img src={highviewLogo} alt="HighView Logo" className="footer-logo-img" />
          <div className="footer-copy">
            <span className="footer-brand-tagline">
              <strong>HighView</strong> · Clarity From Every Sheet.
            </span>
            <span className="footer-copyright">
              © {currentYear} HighView. All rights reserved.
            </span>
          </div>
        </div>

        {/* Right: Powered by HRIDAY */}
        <div className="footer-powered-by" aria-label={`Powered by ${identity.name}`}>
          <span className="powered-text">Powered by</span>
          <span className="powered-brand">{identity.name}</span>
        </div>
      </div>
    </footer>
  );
}
