
  import { createRoot } from "react-dom/client";
  import App from "./app/App.tsx";
  import "./styles/index.css";
import { iniciarTema } from "./app/components/ToggleTema";

iniciarTema();

  createRoot(document.getElementById("root")!).render(<App />);
  