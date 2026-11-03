import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { applyStoredTheme } from "./components/window-chrome";
import { loadLocale } from "./lib/locale";
import "./styles.css";

applyStoredTheme(); // before the first render: no light flash in dark mode
loadLocale().finally(() => {
  createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
});
