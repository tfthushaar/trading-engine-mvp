import axios from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token from localStorage on each request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          const resp = await axios.post(`${BASE_URL}/api/auth/refresh`, {}, {
            params: { refresh_token: refreshToken },
          });
          const { access_token } = resp.data;
          localStorage.setItem("access_token", access_token);
          error.config.headers.Authorization = `Bearer ${access_token}`;
          return api.request(error.config);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function createPriceFeed(ticker: string, onMessage: (data: any) => void): WebSocket {
  const ws = new WebSocket(`${WS_URL}/ws/prices/${ticker}`);
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)); } catch {}
  };
  const ping = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send("ping");
  }, 30000);
  ws.onclose = () => clearInterval(ping);
  return ws;
}
