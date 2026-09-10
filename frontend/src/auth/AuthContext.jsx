import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import { AuthContext } from "./context";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await apiFetch("/api/auth/me", { allowUnauthorized: true });
      setUser(me?.authenticated ? me : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  const login = () => window.location.assign("/api/auth/github/login");

  const logout = async () => {
    try {
      await apiFetch("/api/auth/logout", {
        method: "POST",
        allowUnauthorized: true,
      });
    } catch {
      /* ignore */
    }
    setUser(null);
    window.location.assign("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}
