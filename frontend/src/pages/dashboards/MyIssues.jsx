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

export default function MyIssues() {
  const { current } = useOrg();
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
          `/api/dashboards/my-issues?org=${encodeURIComponent(current.login)}`,
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
        <h1>Minhas issues</h1>
        <p style={{ color: "#666" }}>
          Nenhuma organização. <Link to="/profile">Sincronize no perfil</Link>{" "}
          (PAT com <code>read:org</code>).
        </p>
      </div>
    );

  return (
    <div className="page">
      <h1>Minhas issues · {current.login}</h1>
      {error && <div className="message error">{error}</div>}
      {loading && <p style={{ color: "#666" }}>Carregando…</p>}
      {data && (
        <>
          <p className="subtitle" style={{ color: "#666" }}>
            {data.repos} projeto(s) de roadmap da organização.
          </p>
          <StatTiles agg={data.agg} />
          <PhaseBreakdown byPhase={data.agg?.by_phase} />
          <h2 style={{ marginTop: 24 }}>Issues</h2>
          <IssueTable issues={data.issues} />
          <DashboardErrors errors={data.errors} />
        </>
      )}
    </div>
  );
}
