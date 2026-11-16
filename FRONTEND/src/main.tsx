
  import { createRoot } from "react-dom/client";
  import App from "./app/App.tsx";
  import "./styles/index.css";
  import { instalarValidacionEnEspanol } from "./services/validacionEspanol";

  instalarValidacionEnEspanol();

  createRoot(document.getElementById("root")!).render(<App />);
  