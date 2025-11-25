import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./AppFixed";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
