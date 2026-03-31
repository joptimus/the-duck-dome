import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Dismiss splash screen after progress bar animation completes (~4.05s)
const splash = document.getElementById("app-splash");
if (splash) {
  let dismissed = false;
  const dismiss = () => {
    if (dismissed) return;
    dismissed = true;
    splash.classList.add("hidden");
    splash.addEventListener("transitionend", () => splash.remove(), { once: true });
  };
  const fill = splash.querySelector(".splash-bar-fill");
  if (fill) {
    // Dismiss when the CSS animation ends
    fill.addEventListener("animationend", dismiss, { once: true });
  }
  // Fallback: if animationend fires before this JS runs (e.g. cached HTML + slow
  // network), the event is already gone and the splash would hang indefinitely.
  setTimeout(dismiss, 5500);
}
