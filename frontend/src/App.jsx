import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/useAuth";
import { useOrg } from "./org/useOrg";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Manual from "./pages/Manual";
import Profile from "./pages/Profile";
import ProjectDetail from "./pages/ProjectDetail";
import ProjectWizard from "./pages/ProjectWizard";
import Devs from "./pages/dashboards/Devs";
import MyIssues from "./pages/dashboards/MyIssues";
import OrgIssues from "./pages/dashboards/OrgIssues";
import "./App.css";

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page-center">Carregando…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function OrgSwitcher() {
  const { orgs, current, setCurrent } = useOrg();
  if (!orgs.length) return null;
  return (
    <select
      className="org-switcher"
      value={current?.login || ""}
      onChange={(e) => setCurrent(e.target.value)}
    >
      {orgs.map((o) => (
        <option key={o.login} value={o.login}>
          {o.login}
          {o.is_coordinator ? " (coord.)" : ""}
        </option>
      ))}
    </select>
  );
}

function Header() {
  const { user, logout } = useAuth();
  const { current, isCoordinator } = useOrg();
  if (!user) return null;
  return (
    <header className="app-header">
      <Link to="/" className="app-brand">
        RoadMap Builder
      </Link>
      <nav className="app-nav">
        <Link to="/" title="Seus projetos de roadmap">
          Projetos
        </Link>
        <Link to="/projects/new" title="Provisionar um novo repositório">
          Novo
        </Link>
        {current && (
          <Link
            to="/dashboards/my"
            title="Issues em que você é autor ou responsável"
          >
            Minhas issues
          </Link>
        )}
        {current && (
          <Link
            to="/dashboards/org"
            title="Todas as issues dos projetos da organização"
          >
            Issues da org
          </Link>
        )}
        {current && isCoordinator && (
          <Link
            to="/dashboards/devs"
            title="Progresso por desenvolvedor e por fase (coordenador)"
          >
            Devs
          </Link>
        )}
        <Link to="/profile" title="Seu PAT e configurações gerais">
          Perfil
        </Link>
        <Link to="/manual" title="Como usar o RoadMap Builder">
          Manual
        </Link>
      </nav>
      <div className="app-user">
        <OrgSwitcher />
        {user.avatar_url && (
          <img src={user.avatar_url} alt="" className="app-avatar" />
        )}
        <span>{user.login}</span>
        <button className="btn-text" onClick={logout}>
          Sair
        </button>
      </div>
    </header>
  );
}

function Protected({ children }) {
  return <RequireAuth>{children}</RequireAuth>;
}

export default function App() {
  return (
    <div className="app-root">
      <Header />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <Protected>
              <Home />
            </Protected>
          }
        />
        <Route
          path="/profile"
          element={
            <Protected>
              <Profile />
            </Protected>
          }
        />
        <Route
          path="/manual"
          element={
            <Protected>
              <Manual />
            </Protected>
          }
        />
        <Route
          path="/projects/new"
          element={
            <Protected>
              <ProjectWizard />
            </Protected>
          }
        />
        <Route
          path="/projects/:id"
          element={
            <Protected>
              <ProjectDetail />
            </Protected>
          }
        />
        <Route
          path="/dashboards/my"
          element={
            <Protected>
              <MyIssues />
            </Protected>
          }
        />
        <Route
          path="/dashboards/org"
          element={
            <Protected>
              <OrgIssues />
            </Protected>
          }
        />
        <Route
          path="/dashboards/devs"
          element={
            <Protected>
              <Devs />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
