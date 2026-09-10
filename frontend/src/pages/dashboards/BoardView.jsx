import { useMemo, useState } from "react";
import { DashboardErrors } from "./parts";

const GROUPS = [
  ["status", "Status"],
  ["phase", "Fase / Milestone"],
  ["assignee", "Responsável"],
  ["state", "Aberta / Fechada"],
];

const STATE_ORDER = ["OPEN", "CLOSED"];
const STATE_LABEL = { OPEN: "Abertas", CLOSED: "Fechadas" };
const FALLBACK_OPEN = "◻ Abertas (sem status)";
const FALLBACK_CLOSED = "✓ Fechadas";
const NO_STATUS = "Sem status";

function statusKeyOf(i) {
  if (i.status) return i.status;
  return i.state === "CLOSED" ? FALLBACK_CLOSED : FALLBACK_OPEN;
}

function FilterSelect({ value, onChange, title, allLabel, options }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      title={title}
    >
      <option value="">{allLabel}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

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
        {i.status && <span className="phase-badge created">{i.status}</span>}
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
 * Board reutilizável. `issues` no formato dos dashboards; `statusOrder` é a
 * ordem das colunas de Status vinda do(s) Project(s) V2 do GitHub.
 */
export default function BoardView({
  issues = [],
  errors = [],
  repos = 0,
  statusOrder = [],
  showRepoFilter = true,
  loading = false,
  onRefresh,
}) {
  const hasStatus = statusOrder.length > 0 || issues.some((i) => i.status);
  const [groupBy, setGroupBy] = useState(hasStatus ? "status" : "phase");
  const [repoFilter, setRepoFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [milestoneFilter, setMilestoneFilter] = useState("");
  const [labelFilter, setLabelFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");

  const opts = useMemo(() => {
    const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort();
    return {
      repos: uniq(issues.map((i) => i.repo)),
      assignees: uniq(issues.flatMap((i) => i.assignees || [])),
      milestones: uniq(issues.map((i) => i.milestone)),
      labels: uniq(issues.flatMap((i) => i.labels || [])),
    };
  }, [issues]);

  const filtered = useMemo(
    () =>
      issues.filter(
        (i) =>
          (!showRepoFilter || !repoFilter || i.repo === repoFilter) &&
          (!assigneeFilter || (i.assignees || []).includes(assigneeFilter)) &&
          (!milestoneFilter || i.milestone === milestoneFilter) &&
          (!labelFilter || (i.labels || []).includes(labelFilter)) &&
          (!stateFilter || i.state === stateFilter),
      ),
    [
      issues,
      showRepoFilter,
      repoFilter,
      assigneeFilter,
      milestoneFilter,
      labelFilter,
      stateFilter,
    ],
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

    if (groupBy === "status") {
      // colunas na ordem do Project V2, depois buckets de fallback
      for (const name of statusOrder)
        map.set(name, { key: name, title: name, issues: [] });
      filtered.forEach((i) => {
        const k = statusKeyOf(i);
        push(k, k, i);
      });
      const rank = (k) => {
        const idx = statusOrder.indexOf(k);
        if (idx >= 0) return idx;
        if (k === FALLBACK_OPEN) return 900;
        if (k === FALLBACK_CLOSED) return 901;
        if (k === NO_STATUS) return 999;
        return 800;
      };
      return [...map.values()]
        .filter((c) => c.issues.length || statusOrder.includes(c.key))
        .sort((a, b) => rank(a.key) - rank(b.key));
    }

    // fase / milestone
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
  }, [filtered, groupBy, statusOrder]);

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
          <FilterSelect
            value={repoFilter}
            onChange={setRepoFilter}
            title="Filtrar por repositório"
            allLabel="Todos os repositórios"
            options={opts.repos}
          />
        )}
        <FilterSelect
          value={milestoneFilter}
          onChange={setMilestoneFilter}
          title="Filtrar por milestone"
          allLabel="Todos os milestones"
          options={opts.milestones}
        />
        <FilterSelect
          value={assigneeFilter}
          onChange={setAssigneeFilter}
          title="Filtrar por responsável (assign to)"
          allLabel="Todos os responsáveis"
          options={opts.assignees.map((a) => a)}
        />
        <FilterSelect
          value={labelFilter}
          onChange={setLabelFilter}
          title="Filtrar por label"
          allLabel="Todas as labels"
          options={opts.labels}
        />
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          title="Filtrar por estado"
        >
          <option value="">Abertas e fechadas</option>
          <option value="OPEN">Só abertas</option>
          <option value="CLOSED">Só fechadas</option>
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
        {repos ? ` · ${repos} projeto(s)` : ""}
        {groupBy === "status" && !hasStatus
          ? " · nenhum Project V2 vinculado — status = aberta/fechada"
          : ""}{" "}
        · dados ao vivo do GitHub
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
