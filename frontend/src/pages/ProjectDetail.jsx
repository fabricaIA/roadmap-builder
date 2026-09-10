import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../api/client";

const STATUS_LABEL = {
  created: "criada",
  partial: "parcial",
  not_created: "não criada",
  empty: "sem issues",
};

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [phases, setPhases] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [alertMode, setAlertMode] = useState(false); // on_duplicate = "error"
  const [busyPhase, setBusyPhase] = useState("");
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [p, ph] = await Promise.all([
        apiFetch(`/api/projects/${id}`),
        apiFetch(`/api/projects/${id}/phases`).catch(() => ({
          phases: [],
          history: [],
        })),
      ]);
      setProject(p);
      setPhases(ph.phases || []);
      setHistory(ph.history || []);
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

  const applyPhase = async (phaseKey) => {
    setBusyPhase(phaseKey);
    setToast("");
    try {
      const res = await apiFetch(
        `/api/projects/${id}/phases/${phaseKey}/apply`,
        {
          method: "POST",
          body: { on_duplicate: alertMode ? "error" : "skip", apply: true },
        },
      );
      if (res.status === "already_done") {
        setToast(`Fase ${phaseKey} já estava completa — nada a fazer.`);
      } else {
        setToast(
          `Fase ${phaseKey}: ${res.created} criada(s), ${res.updated} atualizada(s).` +
            (res.project_error ? ` (painel: ${res.project_error})` : ""),
        );
      }
      await load();
    } catch (e) {
      setToast(`Erro: ${e.message}`);
    } finally {
      setBusyPhase("");
    }
  };

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
      )}

      <div className="phase-head">
        <h2>Fases</h2>
        <label className="alert-toggle">
          <input
            type="checkbox"
            checked={alertMode}
            onChange={(e) => setAlertMode(e.target.checked)}
          />{" "}
          Alertar se a fase já foi criada (em vez de ignorar)
        </label>
      </div>

      {toast && (
        <div
          className={`message ${toast.startsWith("Erro") ? "error" : "success"}`}
        >
          {toast}
        </div>
      )}

      {phases === null || phases.length === 0 ? (
        <p style={{ color: "#666" }}>
          {project.summary_error
            ? "Não foi possível calcular o estado das fases (sem acesso ao GitHub)."
            : "Nenhuma fase no template/config."}
        </p>
      ) : (
        <div className="phase-list">
          {phases.map((ph) => (
            <div className="phase-row wide" key={ph.phase}>
              <div className="phase-title">
                {ph.title}{" "}
                <span className={`phase-badge ${ph.status}`}>
                  {STATUS_LABEL[ph.status] || ph.status}
                  {ph.status === "partial" && ` ${ph.existing}/${ph.expected}`}
                </span>
              </div>
              <div className="phase-counts">
                {ph.existing}/{ph.expected} issues
              </div>
              <button
                className="btn-secondary"
                disabled={busyPhase === ph.phase}
                onClick={() => applyPhase(ph.phase)}
              >
                {busyPhase === ph.phase ? "Aplicando…" : "Aplicar Fase"}
              </button>
            </div>
          ))}
        </div>
      )}

      {history.length > 0 && (
        <>
          <h3 style={{ marginTop: 24 }}>Histórico</h3>
          <ul className="history-list">
            {history.map((h, i) => (
              <li key={i}>
                <strong>{h.phase}</strong> — {h.created} criada(s), {h.updated}{" "}
                atualizada(s){" "}
                <span style={{ color: "#888" }}>
                  · {new Date(h.applied_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
