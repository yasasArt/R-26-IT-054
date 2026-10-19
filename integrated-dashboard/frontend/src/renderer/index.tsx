import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@garment-counter/styles.css";
import { App } from "./App";
import "./modules/platform/platform.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("The desktop renderer root element is missing.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
