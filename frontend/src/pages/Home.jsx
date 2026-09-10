import { Link } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="page">
      <h1>Olá, {user?.name || user?.login} 👋</h1>

      {!user?.has_pat && (
        <div className="message error" style={{ margin: "16px 0" }}>
          Você ainda não configurou um PAT do GitHub.{" "}
          <Link to="/profile">Configurar no perfil</Link> para poder criar
          roadmaps.
        </div>
      )}

      <div className="home-actions">
        <Link to="/projects/new" className="btn-primary">
          ＋ Novo projeto
        </Link>
        <Link to="/profile" className="btn-secondary">
          Meu perfil
        </Link>
      </div>

      <p className="subtitle" style={{ marginTop: 24, color: "#666" }}>
        A lista de projetos e os dashboards de issues chegam nas próximas
        entregas.
      </p>
    </div>
  );
}
