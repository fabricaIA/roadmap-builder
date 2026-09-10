// Componentes compartilhados dos dashboards.

export function StatTiles({ agg }) {
  if (!agg) return null;
  return (
    <div className="stat-row">
      <div className="stat">
        <div className="stat-num">{agg.total}</div>
        <div className="stat-label">issues</div>
      </div>
      <div className="stat">
        <div className="stat-num">{agg.by_state?.OPEN ?? 0}</div>
        <div className="stat-label">abertas</div>
      </div>
      <div className="stat">
        <div className="stat-num">{agg.by_state?.CLOSED ?? 0}</div>
        <div className="stat-label">fechadas</div>
      </div>
      <div className="stat">
        <div className="stat-num">{Object.keys(agg.by_phase || {}).length}</div>
        <div className="stat-label">fases</div>
      </div>
    </div>
  );
}

export function PhaseBreakdown({ byPhase }) {
  const entries = Object.entries(byPhase || {});
  if (!entries.length) return null;
  return (
    <div className="phase-list" style={{ marginTop: 16 }}>
      {entries.map(([phase, c]) => {
        const total = c.open + c.closed;
        const pct = total ? Math.round((c.closed / total) * 100) : 0;
        return (
          <div className="phase-row wide" key={phase}>
            <div className="phase-title">{phase}</div>
            <div className="phase-bar">
              <div className="phase-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="phase-counts">
              {c.closed}/{total} concluídas
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function IssueTable({ issues }) {
  if (!issues?.length) return <p style={{ color: "#666" }}>Nenhuma issue.</p>;
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="issue-table">
        <thead>
          <tr>
            <th>Issue</th>
            <th>Repo</th>
            <th>Fase</th>
            <th>Estado</th>
            <th>Responsável</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((i) => (
            <tr key={i.url}>
              <td>
                <a href={i.url} target="_blank" rel="noreferrer">
                  #{i.number} {i.title}
                </a>
              </td>
              <td>{i.repo}</td>
              <td>{i.phase}</td>
              <td>
                <span
                  className={`phase-badge ${i.state === "OPEN" ? "not_created" : "created"}`}
                >
                  {i.state === "OPEN" ? "aberta" : "fechada"}
                </span>
              </td>
              <td>{i.assignees?.join(", ") || i.author || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DashboardErrors({ errors }) {
  if (!errors?.length) return null;
  return (
    <div className="message error" style={{ marginTop: 12 }}>
      Alguns repositórios não puderam ser lidos:
      <ul style={{ margin: "6px 0 0 18px" }}>
        {errors.map((e, i) => (
          <li key={i}>{e}</li>
        ))}
      </ul>
    </div>
  );
}
