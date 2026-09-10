import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { OrgContext } from "./context";

const LS_KEY = "rmb.currentOrg";

export function OrgProvider({ children }) {
  const { user } = useAuth();
  const [orgs, setOrgs] = useState([]);
  const [currentLogin, setCurrentLogin] = useState(
    () => localStorage.getItem(LS_KEY) || "",
  );
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setOrgs([]);
      return;
    }
    setLoading(true);
    try {
      const list = await apiFetch("/api/orgs", { allowUnauthorized: true });
      setOrgs(Array.isArray(list) ? list : []);
    } catch {
      setOrgs([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  const setCurrent = useCallback((login) => {
    setCurrentLogin(login);
    try {
      localStorage.setItem(LS_KEY, login);
    } catch {
      /* ignore */
    }
  }, []);

  const current = useMemo(
    () => orgs.find((o) => o.login === currentLogin) || orgs[0] || null,
    [orgs, currentLogin],
  );

  const sync = useCallback(async () => {
    await apiFetch("/api/orgs/sync", { method: "POST" });
    await refresh();
  }, [refresh]);

  const value = {
    orgs,
    loading,
    current,
    setCurrent,
    sync,
    isCoordinator: !!current?.is_coordinator,
  };

  return <OrgContext.Provider value={value}>{children}</OrgContext.Provider>;
}
