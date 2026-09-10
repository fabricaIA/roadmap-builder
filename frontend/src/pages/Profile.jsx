import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import { useAuth } from "../auth/useAuth";

const CONFIG_FIELDS = [
  [
    "project_title_pattern",
    "Padrão do título do painel",
    "{owner}/{repo} - Roadmap",
  ],
  ["default_project_start_date", "Data de início padrão (AAAA-MM-DD)", ""],
  ["date_field_start", "Nome do campo de data — início", "Início previsto"],
  ["date_field_end", "Nome do campo de data — fim", "Fim previsto"],
];

export default function Profile() {
  const { refresh } = useAuth();
  const [config, setConfig] = useState({});
  const [hasPat, setHasPat] = useState(false);
  const [patInput, setPatInput] = useState("");
  const [patInfo, setPatInfo] = useState(null); // {login, scopes}
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/profile")
      .then((p) => {
        setConfig(p.config || {});
        setHasPat(p.has_pat);
      })
      .catch((e) => setMsg(`Erro: ${e.message}`))
      .finally(() => setLoading(false));
  }, []);

  const testPat = async () => {
    setMsg("");
    try {
      const info = await apiFetch("/api/profile/pat/test");
      setPatInfo(info);
    } catch (e) {
      setPatInfo(null);
      setMsg(`Erro: ${e.message}`);
    }
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const body = { config };
      if (patInput.trim()) body.pat = patInput.trim();
      const res = await apiFetch("/api/profile", { method: "PUT", body });
      setHasPat(res.has_pat);
      setConfig(res.config || {});
      setPatInput("");
      if (res.pat_login) {
        setPatInfo({ login: res.pat_login, scopes: res.pat_scopes });
      }
      setMsg("Perfil salvo.");
      refresh();
    } catch (e) {
      setMsg(`Erro: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const removePat = async () => {
    setBusy(true);
    setMsg("");
    try {
      const res = await apiFetch("/api/profile", {
        method: "PUT",
        body: { pat: "" },
      });
      setHasPat(res.has_pat);
      setPatInfo(null);
      setMsg("PAT removido.");
      refresh();
    } catch (e) {
      setMsg(`Erro: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="page-center">Carregando…</div>;

  return (
    <div className="page">
      <h1>Meu perfil</h1>

      <form onSubmit={save} className="container" style={{ maxWidth: 640 }}>
        <div className="step-panel">
          <h2>Token do GitHub (PAT clássico)</h2>
          <p className="subtitle" style={{ color: "#666", fontSize: "0.9rem" }}>
            Usado para criar milestones, issues e painéis. Escopos necessários:{" "}
            <code>repo</code> e <code>project</code>. O token é guardado cifrado
            e nunca é exibido de volta.
          </p>

          <div className="form-group">
            <label>{hasPat ? "Substituir PAT" : "Definir PAT"}</label>
            <input
              type="password"
              value={patInput}
              onChange={(e) => setPatInput(e.target.value)}
              placeholder={hasPat ? "•••••••• (configurado)" : "ghp_..."}
              title="Personal Access Token clássico do GitHub. Guardado cifrado; usado pelo backend nas operações."
            />
          </div>

          <div className="home-actions">
            {hasPat && (
              <button
                type="button"
                className="btn-secondary"
                onClick={testPat}
                disabled={busy}
                title="Valida o PAT salvo contra a API do GitHub e mostra login + escopos."
              >
                Testar PAT
              </button>
            )}
            {hasPat && (
              <button
                type="button"
                className="btn-remove"
                onClick={removePat}
                disabled={busy}
                title="Remove o PAT salvo. Você não conseguirá criar/atualizar roadmaps até definir outro."
              >
                Remover PAT
              </button>
            )}
          </div>

          {patInfo && (
            <p style={{ color: "#0a7d28", fontSize: "0.9rem", marginTop: 8 }}>
              PAT válido — <strong>{patInfo.login}</strong>. Escopos:{" "}
              {patInfo.scopes.length
                ? patInfo.scopes.join(", ")
                : "(fine-grained)"}
            </p>
          )}
        </div>

        <div className="step-panel">
          <h2>Configurações gerais</h2>
          {CONFIG_FIELDS.map(([key, label, placeholder]) => (
            <div className="form-group" key={key}>
              <label>{label}</label>
              <input
                type="text"
                value={config[key] || ""}
                placeholder={placeholder}
                onChange={(e) =>
                  setConfig((c) => ({ ...c, [key]: e.target.value }))
                }
              />
            </div>
          ))}
        </div>

        {msg && (
          <div
            className={`message ${msg.startsWith("Erro") ? "error" : "success"}`}
          >
            {msg}
          </div>
        )}

        <div style={{ marginTop: 16 }}>
          <button type="submit" className="btn-success" disabled={busy}>
            {busy ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </form>
    </div>
  );
}
