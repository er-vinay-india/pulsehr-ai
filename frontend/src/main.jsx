import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { ThemeProvider } from "./context/ThemeContext.jsx";
import { HRIDAYProvider } from "./components/hriday/HRIDAYProvider.jsx";
import "./styles/index.scss";
import "./styles/refinements.scss";
import "./styles/executive-cockpit.scss";
import "katex/dist/katex.min.css";
import "./styles/eda-explorer.scss";
import "./styles/theme-components.scss";
import "./styles/presentation-interface.scss";
import "./styles/slide-accessibility.scss";
import "./styles/hriday-chat.scss";
import "./styles/explorer-workspace.scss";
import "./styles/mobile-layout.scss";
import "./styles/radix-dropdown.scss";
import "./styles/header-logo.scss";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <HRIDAYProvider><App /></HRIDAYProvider>
    </ThemeProvider>
  </React.StrictMode>
);
