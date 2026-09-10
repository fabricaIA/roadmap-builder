import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export default function Login() {
  const { user, loading, login } = useAuth();

  if (loading) return <div className="page-center">Carregando…</div>;
  if (user) return <Navigate to="/" replace />;

  return (
    <div className="welcome-screen">
      <div className="welcome-content">
        <img
          src="/roadmap.png"
          alt="Roadmap Builder"
          className="welcome-logo"
        />
        <span className="welcome-tag">RoadMap Builder</span>
        <h1>Construa Roadmaps Inteligentes para o GitHub</h1>
        <p>
          Gestão centralizada de milestones, etiquetas, cronogramas e painéis de
          projeto — para vários projetos e times.
        </p>
        <button onClick={login} className="btn-welcome-start">
          Entrar com GitHub ➔
        </button>
      </div>
    </div>
  );
}
