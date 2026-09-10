import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../api/client";
import { useAuth } from "../auth/useAuth";

function ImportForm({ onDone }) {
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [number, setNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await apiFetch("/api/projects/import", {
        method: "POST",
        body: {
          owner: owner.trim(),
          repo: repo.trim(),
          project_number: number ? parseInt(number, 10) : null,
        },
      });
      onDone();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="import-form">
      <input
        placeholder="owner"
        value={owner}
        onChange={(e) => setOwner(e.target.value)}
        required
      />
      <input
        placeholder="repo"
        value={repo}
        onChange={(e) => setRepo(e.target.value)}
        required
      />
      <input
        placeholder="Project # (opcional)"
        value={number}
        onChange={(e) => setNumber(e.target.value)}
        type="number"
        min="1"
      />
      <button className="btn-primary" disabled={busy}>
        {busy ? "Importando…" : "Importar"}
      </button>
      {err && <span className="import-err">{err}</span>}
    </form>
  );
}

function ProjectCard({ p }) {
  const s = p.summary;
  return (
    <Link to={`/projects/${p.id}`} className="project-card">
      <div className="project-card-title">
        {p.title || `${p.owner}/${p.repo}`}
      </div>
      <div className="project-card-repo">
        {p.owner}/{p.repo}
        {p.source === "imported" && " · importado"}
      </div>
      {s ? (
        <div className="project-card-stats">
          <span>{s.issues.open} abertas</span>
          <span>{s.issues.closed} fechadas</span>
          <span>{s.milestones.length} fases</span>
        </div>
      ) : (
        <div className="project-card-stats muted">
          {p.summary_error || "sem dados"}
        </div>
      )}
    </Link>
  );
}

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState("");
  const [showImport, setShowImport] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      setProjects(await apiFetch("/api/projects"));
    } catch (e) {
      setProjects([]);
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  return (
    <div className="page">
      <div className="home-head">
        <h1>Projetos</h1>
        <div className="home-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={() => navigate("/projects/new")}
            title="Provisiona um repositório do zero: milestones, labels e issues do template (você escolhe as fases)."
          >
            ＋ Novo projeto
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setShowImport((v) => !v)}
            title="Cadastra no app um repositório que já tem o roadmap criado, para acompanhar aqui e nos dashboards."
          >
            Importar existente
          </button>
        </div>
      </div>

      {!user?.has_pat && (
        <div className="message error" style={{ margin: "12px 0" }}>
          Configure um PAT do GitHub no <Link to="/profile">perfil</Link> para
          criar e acompanhar projetos.
        </div>
      )}

      {showImport && (
        <ImportForm
          onDone={() => {
            setShowImport(false);
            load();
          }}
        />
      )}

      {error && <div className="message error">{error}</div>}

      {projects === null ? (
        <p style={{ color: "#666" }}>Carregando…</p>
      ) : projects.length === 0 ? (
        <p style={{ color: "#666", marginTop: 16 }}>
          Nenhum projeto ainda. Crie o primeiro pelo botão acima.
        </p>
      ) : (
        <div className="project-grid">
          {projects.map((p) => (
            <ProjectCard key={p.id} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}
