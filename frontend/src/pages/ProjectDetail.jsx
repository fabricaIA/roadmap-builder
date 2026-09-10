import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../api/client";

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setProject(await apiFetch(`/api/projects/${id}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  if (loading) return <div className="page-center">Carregando…</div>;
  if (error)
    return (
      <div className="page">
        <div className="message error">{error}</div>
        <Link to="/">← Voltar</Link>
      </div>
    );

  const s = project.summary;

  return (
    <div className="page">
      <Link to="/" className="btn-text">
        ← Projetos
      </Link>
      <h1>{project.title || `${project.owner}/${project.repo}`}</h1>
      <p className="subtitle" style={{ color: "#666" }}>
        <a
          href={`https://github.com/${project.owner}/${project.repo}`}
          target="_blank"
          rel="noreferrer"
        >
          {project.owner}/{project.repo}
        </a>
        {project.project_url && (
          <>
            {" · "}
            <a href={project.project_url} target="_blank" rel="noreferrer">
              Project #{project.project_number}
            </a>
          </>
        )}
        {" · "}
        <span>{project.source === "imported" ? "importado" : "criado"}</span>
      </p>

      {project.summary_error && (
        <div className="message error">{project.summary_error}</div>
      )}

      {s && (
        <>
          <div className="stat-row">
            <div className="stat">
              <div className="stat-num">{s.issues.open}</div>
              <div className="stat-label">abertas</div>
            </div>
            <div className="stat">
              <div className="stat-num">{s.issues.closed}</div>
              <div className="stat-label">fechadas</div>
            </div>
            <div className="stat">
              <div className="stat-num">{s.issues.total}</div>
              <div className="stat-label">total</div>
            </div>
          </div>

          <h2 style={{ marginTop: 24 }}>Fases</h2>
          <div className="phase-list">
            {s.milestones.length === 0 && (
              <p style={{ color: "#666" }}>
                Nenhuma milestone no repositório ainda.
              </p>
            )}
            {s.milestones.map((m) => {
              const pct = m.total ? Math.round((m.closed / m.total) * 100) : 0;
              return (
                <div className="phase-row" key={m.title}>
                  <div className="phase-title">{m.title}</div>
                  <div className="phase-bar">
                    <div
                      className="phase-bar-fill"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="phase-counts">
                    {m.closed}/{m.total} concluídas
                  </div>
                </div>
              );
            })}
          </div>
          <p className="subtitle" style={{ color: "#666", marginTop: 16 }}>
            A aplicação de issues por fase (e o tratamento de duplicação) chega
            na próxima entrega.
          </p>
        </>
      )}
    </div>
  );
}
