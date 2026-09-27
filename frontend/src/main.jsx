import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { ThemeProvider } from "./context/ThemeContext.jsx";
import "./styles/index.scss";
import "./styles/refinements.scss";
import "./styles/executive-cockpit.scss";
import "katex/dist/katex.min.css";
import "./styles/mobile-layout.scss";
import "./styles/eda-explorer.scss";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
