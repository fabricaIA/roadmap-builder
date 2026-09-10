import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../../api/client";
import { useOrg } from "../../org/useOrg";
import BoardView from "./BoardView";

export default function Board() {
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
        <h1>Board</h1>
        <p style={{ color: "#666" }}>
          Nenhuma organização. <Link to="/profile">Sincronize no perfil</Link>.
        </p>
      </div>
    );

  return (
    <div className="page board-page">
      <h1>Board · {current.login}</h1>
      {error && <div className="message error">{error}</div>}
      {loading && !data && <p style={{ color: "#666" }}>Carregando…</p>}
      {data && (
        <BoardView
          issues={data.issues}
          errors={data.errors}
          repos={data.repos}
          statusOrder={data.status_order || []}
          loading={loading}
          onRefresh={load}
        />
      )}
    </div>
  );
}
