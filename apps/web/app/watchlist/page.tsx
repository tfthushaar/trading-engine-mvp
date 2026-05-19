"use client";
import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, WS_URL } from "@/lib/api";
import { Bell, Plus, Search, Trash2, TrendingUp, TrendingDown, Activity, Volume2, Zap, X } from "lucide-react";
import { useRouter } from "next/navigation";

const POPULAR_STOCKS = [
  { ticker:"AAPL", name:"Apple Inc." },
  { ticker:"MSFT", name:"Microsoft" },
  { ticker:"NVDA", name:"NVIDIA" },
  { ticker:"GOOGL", name:"Alphabet" },
  { ticker:"AMZN", name:"Amazon" },
  { ticker:"META", name:"Meta" },
  { ticker:"TSLA", name:"Tesla" },
  { ticker:"AMD", name:"AMD" },
  { ticker:"NFLX", name:"Netflix" },
  { ticker:"JPM", name:"JPMorgan" },
  { ticker:"BAC", name:"Bank of America" },
  { ticker:"GS", name:"Goldman Sachs" },
  { ticker:"XOM", name:"ExxonMobil" },
  { ticker:"CVX", name:"Chevron" },
  { ticker:"JNJ", name:"Johnson & Johnson" },
  { ticker:"PFE", name:"Pfizer" },
  { ticker:"LLY", name:"Eli Lilly" },
  { ticker:"UNH", name:"UnitedHealth" },
  { ticker:"WMT", name:"Walmart" },
  { ticker:"COST", name:"Costco" },
];

const ALERT_TYPES = [
  { key:"volume_spike", label:"Volume Spike", icon:Volume2 },
  { key:"breakout", label:"Breakout", icon:TrendingUp },
  { key:"price_move", label:"Large Move", icon:Activity },
  { key:"options_anomaly", label:"Options Activity", icon:Zap },
];

interface Notification { id:string; ticker:string; type:string; message:string; timestamp:string; severity:"high"|"medium"|"low"; read:boolean; }

export default function WatchlistPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [wlName, setWlName] = useState("My Watchlist");
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  const { data: watchlists } = useQuery({
    queryKey: ["watchlists"],
    queryFn: () => api.get("/api/watchlist/").then(r => r.data),
  });

  const { data: alertsData } = useQuery({
    queryKey: ["watchlist-alerts"],
    queryFn: () => api.get("/api/intelligence/watchlist-alerts").then(r => r.data),
    refetchInterval: 60_000,
  });

  const createWatchlist = useMutation({
    mutationFn: (data:any) => api.post("/api/watchlist/", data),
    onSuccess: () => { qc.invalidateQueries({queryKey:["watchlists"]}); setSelectedTickers([]); setSearch(""); },
  });

  // WebSocket for real-time notifications
  useEffect(() => {
    const userId = typeof window !== "undefined" ? localStorage.getItem("user_id") || "anon" : "anon";
    const ws = new WebSocket(`${WS_URL}/ws/alerts/${userId}`);
    wsRef.current = ws;
    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const notif: Notification = {
          id: Date.now().toString(),
          ticker: data.ticker || "",
          type: data.type || "alert",
          message: data.message || "",
          timestamp: data.timestamp || new Date().toISOString(),
          severity: data.severity || "medium",
          read: false,
        };
        setNotifications(prev => [notif, ...prev].slice(0, 50));
      } catch {}
    };
    return () => ws.close();
  }, []);

  const filteredStocks = POPULAR_STOCKS.filter(s =>
    s.ticker.includes(search.toUpperCase()) || s.name.toLowerCase().includes(search.toLowerCase())
  );

  const toggleTicker = (ticker: string) =>
    setSelectedTickers(prev => prev.includes(ticker) ? prev.filter(t => t !== ticker) : [...prev, ticker]);

  const markRead = (id: string) => setNotifications(prev => prev.map(n => n.id === id ? {...n, read:true} : n));
  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 space-y-6 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title">Watchlist & Alerts</h1>
          <p className="section-subtitle">Monitor stocks and receive AI-narrated real-time notifications</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 text-xs ${wsConnected ? "text-green-400" : "text-[#555]"}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? "bg-green-400" : "bg-[#555]"}`} />
            {wsConnected ? "Live" : "Offline"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Stock picker + Watchlist builder */}
        <div className="lg:col-span-2 space-y-4">
          {/* Create watchlist */}
          <div className="card">
            <p className="label mb-3">Create Watchlist</p>
            <div className="flex gap-2 mb-4">
              <input className="input flex-1" placeholder="Watchlist name..." value={wlName} onChange={e => setWlName(e.target.value)} />
              <button
                disabled={!selectedTickers.length || createWatchlist.isPending}
                onClick={() => createWatchlist.mutate({ name: wlName, tickers: selectedTickers })}
                className="btn-primary"
              >
                {createWatchlist.isPending ? "Creating..." : <><Plus size={14}/> Create</>}
              </button>
            </div>

            {/* Search stocks */}
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555]" size={14} />
              <input className="input pl-8" placeholder="Search stocks..." value={search} onChange={e => setSearch(e.target.value)} />
            </div>

            {/* Selected tickers */}
            {selectedTickers.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {selectedTickers.map(t => (
                  <span key={t} className="chip gap-2">
                    {t}
                    <button onClick={() => toggleTicker(t)} className="text-[#555] hover:text-white"><X size={10} /></button>
                  </span>
                ))}
              </div>
            )}

            {/* Stock grid */}
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-1.5">
              {filteredStocks.map(s => (
                <button
                  key={s.ticker}
                  onClick={() => toggleTicker(s.ticker)}
                  className={`rounded-xl px-3 py-2 text-left transition-all ${
                    selectedTickers.includes(s.ticker)
                      ? "bg-white text-black"
                      : "bg-[#0f0f0f] text-[#aaa] hover:text-white hover:bg-[#1a1a1a] border border-transparent hover:border-[#2a2a2a]"
                  }`}
                >
                  <div className="text-xs font-semibold">{s.ticker}</div>
                  <div className="text-[10px] opacity-60 truncate">{s.name}</div>
                </button>
              ))}
            </div>
          </div>

          {/* My watchlists */}
          {watchlists?.length > 0 && (
            <div className="card">
              <p className="label mb-3">My Watchlists</p>
              <div className="space-y-3">
                {watchlists.map((wl:any) => (
                  <div key={wl.id} className="bg-[#0f0f0f] rounded-xl p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-sm">{wl.name}</span>
                      <button onClick={() => router.push(`/explore`)} className="text-xs text-[#888] hover:text-white">View alerts →</button>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(wl.tickers||[]).map((t:string) => (
                        <button key={t} onClick={() => router.push(`/ticker/${t}`)} className="chip hover:border-[#444] hover:text-white transition-colors">{t}</button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Scanned alerts */}
          {alertsData?.alerts?.length > 0 && (
            <div className="card">
              <p className="label mb-3">Live Watchlist Intelligence</p>
              <div className="space-y-2">
                {alertsData.alerts.map((a:any, i:number) => (
                  <div key={i} className={`rounded-xl p-3 ${a.severity==="high"?"alert-high":a.severity==="medium"?"alert-medium":"alert-low"}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <button onClick={() => router.push(`/ticker/${a.ticker}`)} className="font-semibold text-sm hover:underline">{a.ticker}</button>
                      <span className="text-[10px] text-[#666]">{a.type?.replace(/_/g," ")}</span>
                    </div>
                    <p className="text-xs text-[#aaa]">{a.narration}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Notification feed */}
        <div className="space-y-4">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Bell size={14} />
                <p className="label">Notifications</p>
                {unreadCount > 0 && <span className="text-xs bg-white text-black px-2 py-0.5 rounded-full font-semibold">{unreadCount}</span>}
              </div>
              {notifications.length > 0 && (
                <button onClick={() => setNotifications([])} className="text-xs text-[#555] hover:text-white">Clear all</button>
              )}
            </div>

            <div className="space-y-2 max-h-96 overflow-y-auto" ref={notifRef}>
              {notifications.length === 0 ? (
                <div className="text-center py-8">
                  <Bell size={24} className="mx-auto mb-2 text-[#333]" />
                  <p className="text-xs text-[#555]">No notifications yet</p>
                  <p className="text-[10px] text-[#444] mt-1">Add stocks to a watchlist to receive alerts</p>
                </div>
              ) : notifications.map(n => (
                <button
                  key={n.id}
                  onClick={() => { markRead(n.id); router.push(`/ticker/${n.ticker}`); }}
                  className={`w-full text-left rounded-xl p-3 transition-all border ${
                    n.read ? "border-transparent bg-[#0a0a0a]" : `${n.severity==="high"?"alert-high":n.severity==="medium"?"alert-medium":"alert-low"}`
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold">{n.ticker}</span>
                    <span className="text-[10px] text-[#555]">{new Date(n.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-xs text-[#aaa] leading-relaxed">{n.message}</p>
                  {!n.read && <div className="w-1 h-1 rounded-full bg-white mt-1.5" />}
                </button>
              ))}
            </div>
          </div>

          {/* Alert type legend */}
          <div className="card">
            <p className="label mb-3">Alert Types</p>
            <div className="space-y-2">
              {ALERT_TYPES.map(({ key, label, icon: Icon }) => (
                <div key={key} className="flex items-center gap-2.5 text-xs text-[#888]">
                  <Icon size={13} className="text-[#555] shrink-0" />
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
