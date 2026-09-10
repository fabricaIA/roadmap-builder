import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em dev, encaminha /api para o backend FastAPI (mesma origem no browser →
// cookie de sessão SameSite=Lax funciona e não há CORS no caminho crítico).
// Ajuste o alvo se o backend não estiver em :8000.
// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
