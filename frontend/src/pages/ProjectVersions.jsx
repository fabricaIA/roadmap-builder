import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { apiFetch } from "../api/client";

const PAGE_SIZE = 20;
const formatDate = (value) => new Date(value).toLocaleString("pt-BR");

function SnapshotPreview({ version }) {
  const snapshot = version.snapshot;
  const config = snapshot.config;
  return (
    <div className="version-preview">
      <h3>{snapshot.title}</h3>
      <dl className="version-facts">
        <div>
          <dt>Repositório</dt>
          <dd>
            {snapshot.owner}/{snapshot.repo}
          </dd>
        </div>
        <div>
          <dt>Painel do GitHub</dt>
          <dd>
            {snapshot.project_number ? `#${snapshot.project_number}` : "Nenhum"}
          </dd>
        </div>
        <div>
          <dt>Data de início</dt>
          <dd>{config.schedule?.project_start_date || "Não definida"}</dd>
        </div>
        <div>
          <dt>Fases selecionadas</dt>
          <dd>{snapshot.phase_keys?.join(", ") || "Todas"}</dd>
        </div>
        <div>
          <dt>Campos de data</dt>
          <dd>
            {config.schedule?.project_date_fields?.start || "Início previsto"} /{" "}
            {config.schedule?.project_date_fields?.end || "Fim previsto"}
          </dd>
        </div>
      </dl>
      <h4>Labels</h4>
      <ul className="version-labels">
        {(config.labels || []).map((label, index) => (
          <li key={index}>
            <span
              className="label-swatch"
              style={{ backgroundColor: `#${label.color}` }}
            />
            {label.name}
            {label.description && ` — ${label.description}`}
          </li>
        ))}
      </ul>
      <h4>Etapas na ordem salva</h4>
      <ol>
        {(config.milestones || []).map((phase, index) => {
          const duration = config.schedule?.milestone_durations?.[phase.key];
          return (
            <li key={index}>
              <strong>
                {phase.key} · {phase.title}
              </strong>
              {duration &&
                ` · ${duration.value} ${duration.unit === "days" ? "dia(s)" : "mês(es)"}`}
              <p>{phase.description}</p>
            </li>
          );
        })}
      </ol>
      <h4>Issues na ordem salva ({config.issues?.length || 0})</h4>
      <ol className="version-cards">
        {(config.issues || []).map((issue, index) => (
          <li key={index}>
            <details>
              <summary>
                {issue.title}{" "}
                <span className="phase-badge partial">{issue.milestone}</span>
              </summary>
              <p className="preserve-lines">{issue.description}</p>
              <p>Labels: {issue.labels?.join(", ") || "Nenhuma"}</p>
              <strong>Entregáveis</strong>
              <ol>
                {(issue.entregaveis || []).map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ol>
              <strong>Critérios de aceite</strong>
              <ol>
                {(issue.criterios_aceite || []).map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ol>
            </details>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function ProjectVersions() {
  const { id } = useParams();
  const location = useLocation();
  const previousRequested = useRef(Boolean(location.state?.restorePrevious));
  const pending = useRef(false);
  const previewHeading = useRef(null);
  const [current, setCurrent] = useState(null);
  const [versions, setVersions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [latest, rows] = await Promise.all([
        apiFetch(`/api/projects/${id}/config`),
        apiFetch(
          `/api/projects/${id}/versions?limit=${PAGE_SIZE + 1}&offset=${offset}`,
        ),
      ]);
      setCurrent(latest);
      setVersions(rows.slice(0, PAGE_SIZE));
      setHasNext(rows.length > PAGE_SIZE);
      if (previousRequested.current) {
        previousRequested.current = false;
        if (latest.version > 1) {
          setSelected(
            await apiFetch(
              `/api/projects/${id}/versions/${latest.version - 1}`,
            ),
          );
          setConfirmRestore(true);
        }
      }
    } catch (exception) {
      setError(exception.message);
    } finally {
      setLoading(false);
    }
  }, [id, offset]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  useEffect(() => {
    if (selected) previewHeading.current?.focus();
  }, [selected]);

  const choose = async (number, restore = false) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    setConfirmRestore(false);
    try {
      setSelected(await apiFetch(`/api/projects/${id}/versions/${number}`));
      setConfirmRestore(restore);
    } catch (exception) {
      setError(exception.message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };

  const restore = async () => {
    if (pending.current || !selected || !current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      const version = await apiFetch(
        `/api/projects/${id}/versions/${selected.version}/restore`,
        {
          method: "POST",
          body: {
            base_version: current.version,
            change_note: `Restauração da versão ${selected.version}`,
          },
        },
      );
      setCurrent(version);
      setSelected(version);
      setConfirmRestore(false);
      setNotice(
        `Versão ${version.version} criada com o conteúdo da versão ${version.restored_from_version}.`,
      );
      if (offset === 0) await load();
      else setOffset(0);
    } catch (exception) {
      setError(exception.message);
      setConfirmRestore(false);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };

  return (
    <div className="page versions-page">
      <Link to={`/projects/${id}`} className="btn-text">
        ← Voltar ao projeto
      </Link>
      <h1>Histórico de versões</h1>
      {current && (
        <p>
          {current.snapshot.title} · Versão atual{" "}
          <strong>{current.version}</strong>
        </p>
      )}
      <div className="version-actions">
        <Link to={`/projects/${id}/edit`} className="btn-primary">
          Editar projeto
        </Link>
        <button
          type="button"
          className="btn-secondary"
          disabled={busy || loading || !current || current.version < 2}
          onClick={() => choose(current.version - 1, true)}
        >
          Voltar à versão anterior
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={busy || loading}
          onClick={load}
        >
          Atualizar histórico
        </button>
      </div>
      <p className="version-help">
        Restaurar cria uma nova versão com todo o conteúdo escolhido, incluindo
        owner, etapas e issues. O histórico é preservado.
      </p>
      {error && (
        <div className="message error" role="alert">
          {error} Use “Atualizar histórico” para consultar a versão mais
          recente.
        </div>
      )}
      {notice && (
        <div className="message success" role="status">
          {notice}
        </div>
      )}
      {loading && <p role="status">Carregando histórico…</p>}
      <div className="versions-table-wrap">
        <table className="issue-table">
          <caption>Versões salvas do projeto</caption>
          <thead>
            <tr>
              <th>Versão</th>
              <th>Data</th>
              <th>Autor</th>
              <th>Alteração</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((version) => (
              <tr key={version.id}>
                <td>
                  <strong>v{version.version}</strong>
                  {version.version === current?.version && " · atual"}
                </td>
                <td>{formatDate(version.created_at)}</td>
                <td>{version.author_login}</td>
                <td>
                  {version.change_note}
                  {version.restored_from_version && (
                    <small>
                      {" "}
                      · Restaurada de v{version.restored_from_version}
                    </small>
                  )}
                </td>
                <td>
                  <div className="version-actions">
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={busy || loading}
                      onClick={() => choose(version.version)}
                    >
                      Ver versão {version.version}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={
                        busy || loading || version.version === current?.version
                      }
                      onClick={() => choose(version.version, true)}
                    >
                      Restaurar versão {version.version}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="version-actions pagination">
        <button
          type="button"
          className="btn-secondary"
          disabled={busy || loading || offset === 0}
          onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
        >
          Mais recentes
        </button>
        <span>Página {Math.floor(offset / PAGE_SIZE) + 1}</span>
        <button
          type="button"
          className="btn-secondary"
          disabled={busy || loading || !hasNext}
          onClick={() => setOffset((value) => value + PAGE_SIZE)}
        >
          Mais antigas
        </button>
      </div>
      {selected && (
        <section
          className="version-selection"
          aria-labelledby="version-preview-heading"
        >
          <h2 id="version-preview-heading" ref={previewHeading} tabIndex={-1}>
            Conteúdo da versão {selected.version}
          </h2>
          {confirmRestore && (
            <div className="restore-confirmation">
              <p>
                Restaurar a versão {selected.version} de{" "}
                <strong>
                  {selected.snapshot.owner}/{selected.snapshot.repo}
                </strong>
                ? Ela será salva como uma nova versão do projeto.
              </p>
              <div className="version-actions">
                <button
                  type="button"
                  className="btn-success"
                  disabled={busy || loading}
                  onClick={restore}
                >
                  {busy ? "Restaurando…" : "Confirmar restauração"}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={busy}
                  onClick={() => setConfirmRestore(false)}
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
          <SnapshotPreview version={selected} />
        </section>
      )}
    </div>
  );
}
