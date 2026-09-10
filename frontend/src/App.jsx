import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/useAuth";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import ProjectWizard from "./pages/ProjectWizard";
import "./App.css";

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page-center">Carregando…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function Header() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <header className="app-header">
      <Link to="/" className="app-brand">
        RoadMap Builder
      </Link>
      <nav className="app-nav">
        <Link to="/">Projetos</Link>
        <Link to="/projects/new">Novo</Link>
        <Link to="/profile">Perfil</Link>
      </nav>
      <div className="app-user">
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

export default function App() {
  return (
    <div className="app-root">
      <Header />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth>
              <Profile />
            </RequireAuth>
          }
        />
        <Route
          path="/projects/new"
          element={
            <RequireAuth>
              <ProjectWizard />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
