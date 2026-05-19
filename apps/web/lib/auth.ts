import { api } from "./api";

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export const auth = {
  async register(email: string, username: string, password: string): Promise<AuthTokens> {
    const resp = await api.post("/api/auth/register", { email, username, password });
    auth.setTokens(resp.data);
    return resp.data;
  },

  async login(email: string, password: string): Promise<AuthTokens> {
    const resp = await api.post("/api/auth/login", { email, password });
    auth.setTokens(resp.data);
    return resp.data;
  },

  setTokens(tokens: AuthTokens) {
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
    }
  },

  logout() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
  },

  isAuthenticated(): boolean {
    if (typeof window === "undefined") return false;
    return !!localStorage.getItem("access_token");
  },
};

// API key management — stored in localStorage (client-side only, not sent to backend)
// For a production app, these would be managed by the backend.
export const apiKeys = {
  KEYS: [
    { key: "ANTHROPIC_API_KEY", label: "Anthropic API Key", placeholder: "sk-ant-...", required: true, link: "https://console.anthropic.com/" },
    { key: "OPENAI_API_KEY", label: "OpenAI API Key", placeholder: "sk-...", required: false, link: "https://platform.openai.com/api-keys" },
    { key: "NEWS_API_KEY", label: "NewsAPI Key", placeholder: "...", required: true, link: "https://newsapi.org/register" },
    { key: "FRED_API_KEY", label: "FRED API Key", placeholder: "...", required: true, link: "https://fred.stlouisfed.org/docs/api/api_key.html" },
    { key: "POLYGON_API_KEY", label: "Polygon.io API Key", placeholder: "...", required: false, link: "https://polygon.io/dashboard/api-keys" },
    { key: "TRADIER_API_KEY", label: "Tradier API Key (Options)", placeholder: "...", required: false, link: "https://developer.tradier.com/" },
    { key: "FMP_API_KEY", label: "Financial Modeling Prep Key", placeholder: "...", required: false, link: "https://site.financialmodelingprep.com/developer/docs" },
  ],

  get(key: string): string {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(`apikey_${key}`) || "";
  },

  set(key: string, value: string) {
    if (typeof window === "undefined") return;
    if (value) {
      localStorage.setItem(`apikey_${key}`, value);
    } else {
      localStorage.removeItem(`apikey_${key}`);
    }
  },

  getAll(): Record<string, string> {
    const result: Record<string, string> = {};
    for (const { key } of apiKeys.KEYS) {
      result[key] = apiKeys.get(key);
    }
    return result;
  },

  hasRequired(): boolean {
    return !!apiKeys.get("ANTHROPIC_API_KEY") && !!apiKeys.get("NEWS_API_KEY");
  },
};
