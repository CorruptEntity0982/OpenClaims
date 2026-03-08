import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  API_BASE_URL,
  PROJECT_NAME,
  SWAGGER_URL,
  NEO4J_BROWSER_URL,
} from "./config";
import DashboardPage from "./pages/DashboardPage";
import DocumentDetailPage from "./pages/DocumentDetailPage";

type Theme = "dark" | "light";

function AppShell() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = window.localStorage.getItem("lattice-theme");
    if (stored === "light" || stored === "dark") {
      setTheme(stored);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("lattice-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <div className="project-mark">L</div>
          <div className="project-title-block">
            <div className="project-name">{PROJECT_NAME}</div>
            <div className="project-subtitle">
              Clinical PDF → Structured data → Neo4j graph
            </div>
          </div>
        </div>
        <div className="app-header-right">
          <div className="link-group">
            <a
              href={SWAGGER_URL}
              className="header-chip-link"
              target="_blank"
              rel="noreferrer"
            >
              Backend Swagger
            </a>
            <a
              href={API_BASE_URL}
              className="header-chip-link"
              target="_blank"
              rel="noreferrer"
            >
              API Root
            </a>
            <a
              href={NEO4J_BROWSER_URL}
              className="header-chip-link"
              target="_blank"
              rel="noreferrer"
            >
              Neo4j Browser
            </a>
          </div>
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
          >
            <span>{theme === "dark" ? "Dark" : "Light"} mode</span>
            <div className="theme-toggle-switch">
              <div className="theme-toggle-thumb" />
            </div>
          </button>
        </div>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

export default App;
