import { useMemo, useState } from "react";
import { DashboardErrors } from "./parts";

const GROUPS = [
  ["phase", "Fase"],
  ["state", "Estado"],
  ["assignee", "Responsável"],
];
const STATE_ORDER = ["OPEN", "CLOSED"];
const STATE_LABEL = { OPEN: "Abertas", CLOSED: "Fechadas" };

function IssueCard({ i }) {
  return (
    <a
      className="board-card"
      href={i.url}
      target="_blank"
      rel="noreferrer"
      title={`${i.repo} #${i.number}`}
    >
      <div className="board-card-title">
        #{i.number} {i.title}
      </div>
      <div className="board-card-meta">
        <span className="board-card-repo">{i.repo.split("/")[1]}</span>
        {i.milestone && <span className="phase-badge partial">{i.phase}</span>}
        <span
          className={`phase-badge ${i.state === "OPEN" ? "not_created" : "created"}`}
        >
          {i.state === "OPEN" ? "aberta" : "fechada"}
        </span>
        {(i.assignees || []).slice(0, 3).map((a) => (
          <span key={a} className="board-assignee">
            @{a}
          </span>
        ))}
      </div>
      {(i.labels || []).length > 0 && (
        <div className="board-card-labels">
          {i.labels.slice(0, 6).map((l) => (
            <span key={l} className="board-label">
              {l}
            </span>
          ))}
        </div>
      )}
    </a>
  );
}

/**
 * Board reutilizável. `issues` no formato dos dashboards.
 * `onRefresh` opcional mostra o botão "Atualizar".
 */
export default function BoardView({
  issues = [],
  errors = [],
  repos = 0,
  showRepoFilter = true,
  loading = false,
  onRefresh,
}) {
  const [groupBy, setGroupBy] = useState("phase");
  const [repoFilter, setRepoFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");

  const repoOptions = useMemo(
    () => [...new Set(issues.map((i) => i.repo))].sort(),
    [issues],
  );
  const assigneeOptions = useMemo(
    () => [...new Set(issues.flatMap((i) => i.assignees || []))].sort(),
    [issues],
  );

  const filtered = useMemo(
    () =>
      issues.filter(
        (i) =>
          (!showRepoFilter || !repoFilter || i.repo === repoFilter) &&
          (!assigneeFilter || (i.assignees || []).includes(assigneeFilter)),
      ),
    [issues, repoFilter, assigneeFilter, showRepoFilter],
  );

  const columns = useMemo(() => {
    const map = new Map();
    const push = (key, title, issue) => {
      if (!map.has(key)) map.set(key, { key, title, issues: [] });
      map.get(key).issues.push(issue);
    };

    if (groupBy === "state") {
      for (const s of STATE_ORDER)
        map.set(s, { key: s, title: STATE_LABEL[s], issues: [] });
      filtered.forEach((i) =>
        push(i.state, STATE_LABEL[i.state] || i.state, i),
      );
      return STATE_ORDER.map((s) => map.get(s)).filter(Boolean);
    }

    if (groupBy === "assignee") {
      filtered.forEach((i) => {
        const who = (i.assignees || [])[0] || "— sem responsável";
        push(who, who.startsWith("—") ? who : `@${who}`, i);
      });
      return [...map.values()].sort((a, b) => a.title.localeCompare(b.title));
    }

    filtered.forEach((i) => push(i.phase, i.phase, i));
    return [...map.values()].sort((a, b) => {
      const ma = /^M(\d+)$/.exec(a.key);
      const mb = /^M(\d+)$/.exec(b.key);
      if (ma && mb) return +ma[1] - +mb[1];
      if (ma) return -1;
      if (mb) return 1;
      if (a.key === "sem fase") return 1;
      if (b.key === "sem fase") return -1;
      return a.key.localeCompare(b.key);
    });
  }, [filtered, groupBy]);

  return (
    <div>
      <div className="board-controls">
        <label title="Como agrupar as colunas do board">
          Agrupar por{" "}
          <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            {GROUPS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        {showRepoFilter && (
          <select
            value={repoFilter}
            onChange={(e) => setRepoFilter(e.target.value)}
            title="Filtrar por repositório"
          >
            <option value="">Todos os repositórios</option>
            {repoOptions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        )}
        <select
          value={assigneeFilter}
          onChange={(e) => setAssigneeFilter(e.target.value)}
          title="Filtrar por responsável"
        >
          <option value="">Todos os responsáveis</option>
          {assigneeOptions.map((a) => (
            <option key={a} value={a}>
              @{a}
            </option>
          ))}
        </select>
        {onRefresh && (
          <button
            className="btn-secondary"
            onClick={onRefresh}
            disabled={loading}
            title="Recarrega do GitHub"
          >
            {loading ? "Atualizando…" : "Atualizar"}
          </button>
        )}
      </div>

      <p className="subtitle" style={{ color: "#666" }}>
        {filtered.length} issue(s)
        {repos ? ` · ${repos} projeto(s)` : ""} · dados ao vivo do GitHub
      </p>

      <div className="board">
        {columns.map((col) => (
          <div className="board-col" key={col.key}>
            <div className="board-col-head">
              {col.title}
              <span className="board-col-count">{col.issues.length}</span>
            </div>
            <div className="board-col-body">
              {col.issues.map((i) => (
                <IssueCard key={i.url} i={i} />
              ))}
              {col.issues.length === 0 && <p className="board-empty">vazio</p>}
            </div>
          </div>
        ))}
      </div>

      <DashboardErrors errors={errors} />
    </div>
  );
}
