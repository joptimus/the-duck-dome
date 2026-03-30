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
  const fill = splash.querySelector(".splash-bar-fill");
  if (fill) {
    fill.addEventListener("animationend", () => {
      splash.classList.add("hidden");
      splash.addEventListener("transitionend", () => splash.remove(), { once: true });
    }, { once: true });
  }
}
