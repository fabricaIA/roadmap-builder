import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { apiFetch } from "../../api/client";
import { useOrg } from "../../org/useOrg";
import { DashboardErrors } from "./parts";

export default function Devs() {
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
          `/api/dashboards/devs?org=${encodeURIComponent(current.login)}`,
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

  if (current && !isCoordinator)
    return <Navigate to="/dashboards/org" replace />;

  if (!current)
    return (
      <div className="page">
        <h1>Devs</h1>
        <p style={{ color: "#666" }}>
          Nenhuma organização. <Link to="/profile">Sincronize no perfil</Link>.
        </p>
      </div>
    );

  const phaseKeys = data
    ? [...new Set(data.devs.flatMap((d) => Object.keys(d.phases)))].sort()
    : [];

  return (
    <div className="page">
      <h1>Devs · {current.login}</h1>
      {error && <div className="message error">{error}</div>}
      {loading && <p style={{ color: "#666" }}>Carregando…</p>}
      {data && (
        <>
          <div style={{ overflowX: "auto" }}>
            <table className="issue-table">
              <thead>
                <tr>
                  <th>Dev</th>
                  <th>Abertas</th>
                  <th>Fechadas</th>
                  {phaseKeys.map((p) => (
                    <th key={p}>{p}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.devs.map((d) => (
                  <tr key={d.dev}>
                    <td>{d.dev}</td>
                    <td>{d.open}</td>
                    <td>{d.closed}</td>
                    {phaseKeys.map((p) => {
                      const c = d.phases[p];
                      return (
                        <td key={p}>
                          {c ? `${c.closed}/${c.open + c.closed}` : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <DashboardErrors errors={data.errors} />
        </>
      )}
    </div>
  );
}
