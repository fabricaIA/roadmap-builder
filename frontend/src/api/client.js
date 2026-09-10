// Cliente HTTP único. Em dev, o proxy do Vite encaminha /api -> backend:8000,
// então BASE fica vazio (mesma origem). Em produção, defina VITE_API_URL.
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401 && !options.allowUnauthorized) {
    // sessão ausente/expirada: manda para o login
    if (window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    throw new ApiError("Não autenticado", 401);
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail = data?.detail ?? data;
    const message = typeof detail === "string" ? detail : `Erro ${res.status}`;
    throw new ApiError(message, res.status, detail);
  }
  return data;
}
