"use client";
import { useState, useEffect } from "react";
import { apiKeys } from "@/lib/auth";
import { CheckCircle, ExternalLink, Eye, EyeOff, Save, AlertTriangle, Key } from "lucide-react";

interface KeyEntry {
  key: string;
  label: string;
  placeholder: string;
  required: boolean;
  link: string;
}

export default function ApiKeysPage() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [saved, setSaved] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setValues(apiKeys.getAll());
  }, []);

  function handleSave() {
    for (const { key } of apiKeys.KEYS) {
      apiKeys.set(key, values[key] || "");
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  function toggle(key: string) {
    setVisible((v) => ({ ...v, [key]: !v[key] }));
  }

  function maskValue(value: string): string {
    if (!value) return "";
    if (value.length <= 8) return "•".repeat(value.length);
    return value.slice(0, 4) + "•".repeat(Math.min(value.length - 8, 20)) + value.slice(-4);
  }

  const requiredMissing = apiKeys.KEYS.filter((k) => k.required && !values[k.key]);

  if (!mounted) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Key className="text-blue-400" size={24} />
          <h1 className="text-2xl font-bold">API Keys</h1>
        </div>
        <p className="text-gray-400 text-sm leading-relaxed">
          These keys are stored <strong>locally in your browser only</strong> and never sent to our servers.
          They enable live market data, AI analysis, and news intelligence features.
        </p>
      </div>

      {/* Status banner */}
      {requiredMissing.length > 0 ? (
        <div className="flex items-start gap-3 bg-yellow-900/20 border border-yellow-700/40 rounded-xl p-4 mb-6">
          <AlertTriangle className="text-yellow-400 mt-0.5 shrink-0" size={18} />
          <div>
            <div className="text-sm font-semibold text-yellow-300 mb-1">Missing required keys</div>
            <div className="text-xs text-yellow-400/80">
              {requiredMissing.map((k) => k.label).join(", ")} {requiredMissing.length === 1 ? "is" : "are"} required for full functionality.
            </div>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 bg-emerald-900/20 border border-emerald-700/40 rounded-xl p-4 mb-6">
          <CheckCircle className="text-emerald-400 shrink-0" size={18} />
          <div className="text-sm text-emerald-300">All required API keys are configured.</div>
        </div>
      )}

      {/* Key entries */}
      <div className="space-y-4">
        {apiKeys.KEYS.map(({ key, label, placeholder, required, link }) => {
          const val = values[key] || "";
          const isSet = !!val;
          const isVisible = visible[key];

          return (
            <div key={key} className="card">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-200">{label}</span>
                    {required && (
                      <span className="text-xs bg-blue-900/50 text-blue-400 px-1.5 py-0.5 rounded">required</span>
                    )}
                    {isSet && (
                      <span className="text-xs bg-emerald-900/50 text-emerald-400 px-1.5 py-0.5 rounded flex items-center gap-1">
                        <CheckCircle size={10} /> configured
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 font-mono mt-0.5">{key}</div>
                </div>
                <a
                  href={link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 shrink-0"
                >
                  Get key <ExternalLink size={11} />
                </a>
              </div>

              <div className="relative">
                <input
                  type={isVisible ? "text" : "password"}
                  value={val}
                  onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                  placeholder={isSet ? maskValue(val) : placeholder}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-blue-500 pr-10"
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="button"
                  onClick={() => toggle(key)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                >
                  {isVisible ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Save button */}
      <div className="mt-6 flex items-center gap-4">
        <button
          onClick={handleSave}
          className="btn-primary flex items-center gap-2 px-6 py-2.5"
        >
          <Save size={16} />
          Save API Keys
        </button>
        {saved && (
          <div className="flex items-center gap-2 text-emerald-400 text-sm">
            <CheckCircle size={16} />
            Saved locally
          </div>
        )}
      </div>

      {/* Security note */}
      <div className="mt-8 bg-gray-900/50 border border-gray-800 rounded-xl p-4 text-xs text-gray-500 space-y-1">
        <div className="font-semibold text-gray-400">Security Note</div>
        <div>• Keys are stored in your browser&apos;s localStorage only.</div>
        <div>• They are never transmitted to our servers or third parties.</div>
        <div>• Clearing browser data will remove your saved keys.</div>
        <div>• For production use, set these as environment variables on your server.</div>
      </div>
    </div>
  );
}
