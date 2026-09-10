import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../../api/client";
import { useOrg } from "../../org/useOrg";
import {
  DashboardErrors,
  IssueTable,
  PhaseBreakdown,
  StatTiles,
} from "./parts";

export default function OrgIssues() {
  const { current, isCoordinator } = useOrg();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!current) return;
    setLoading(true);
    setError("");
    try {
      setData(
        await apiFetch(
          `/api/dashboards/org-issues?org=${encodeURIComponent(current.login)}`,
        ),
      );
    } catch (e) {
      setError(e.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [current]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  if (!current)
    return (
      <div className="page">
        <h1>Issues da organização</h1>
        <p style={{ color: "#666" }}>
          Nenhuma organização. <Link to="/profile">Sincronize no perfil</Link>.
        </p>
      </div>
    );

  const byDev = data?.agg?.by_dev || {};

  return (
    <div className="page">
      <h1>Issues da organização · {current.login}</h1>
      {error && <div className="message error">{error}</div>}
      {loading && <p style={{ color: "#666" }}>Carregando…</p>}
      {data && (
        <>
          <p className="subtitle" style={{ color: "#666" }}>
            {data.repos} projeto(s) de roadmap.
            {isCoordinator && " Você é coordenador desta organização."}
          </p>
          <StatTiles agg={data.agg} />
          <PhaseBreakdown byPhase={data.agg?.by_phase} />

          {isCoordinator && Object.keys(byDev).length > 0 && (
            <>
              <h2 style={{ marginTop: 24 }}>Por desenvolvedor</h2>
              <table className="issue-table">
                <thead>
                  <tr>
                    <th>Dev</th>
                    <th>Abertas</th>
                    <th>Fechadas</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(byDev).map(([dev, c]) => (
                    <tr key={dev}>
                      <td>{dev}</td>
                      <td>{c.open}</td>
                      <td>{c.closed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <h2 style={{ marginTop: 24 }}>Todas as issues</h2>
          <IssueTable issues={data.issues} />
          <DashboardErrors errors={data.errors} />
        </>
      )}
    </div>
  );
}
