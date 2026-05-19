"use client";
import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { Send, Bot, User } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  agent?: string;
  timestamp: string;
}

export default function AIAnalystPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I'm your AI market analyst. I can help you understand market trends, analyze sectors, evaluate trade setups, explain concepts, and answer questions about risk management. What would you like to explore?",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const SUGGESTED_QUESTIONS = [
    "What is happening in the semiconductor sector today?",
    "Explain RSI and when it fails",
    "How should I size my positions for a $50k account?",
    "What does the current market regime mean for swing traders?",
  ];

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const resp = await api.post("/api/agents/chat", {
        message: text,
        conversation_id: conversationId,
      });
      const data = resp.data;
      if (data.conversation_id) setConversationId(data.conversation_id);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          agent: data.agent_used,
          timestamp: data.timestamp,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "I'm unable to process your request right now. Please try again.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 h-[calc(100vh-80px)] flex flex-col">
      <div className="mb-4">
        <h1 className="text-2xl font-bold">AI Analyst</h1>
        <p className="text-gray-400 text-sm">Ask anything about markets, strategies, or trading concepts</p>
      </div>

      {/* Suggested questions (only show at start) */}
      {messages.length === 1 && (
        <div className="grid grid-cols-2 gap-2 mb-4">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => sendMessage(q)}
              className="card text-left text-sm text-gray-300 hover:border-blue-500 hover:text-white transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <Bot size={16} />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-900 border border-gray-800 text-gray-200"
              }`}
            >
              {msg.agent && (
                <div className="text-xs text-gray-400 mb-1">
                  via {msg.agent.replace("_", " ").toUpperCase()}
                </div>
              )}
              {msg.content}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
                <User size={16} />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
              <Bot size={16} />
            </div>
            <div className="card flex items-center gap-1 px-4 py-3">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        className="flex gap-2"
        onSubmit={(e) => { e.preventDefault(); sendMessage(input); }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about markets, trades, or trading concepts..."
          className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <Send size={16} />
        </button>
      </form>

      <p className="text-xs text-gray-500 mt-2 text-center">
        For educational purposes only. Not financial advice.
      </p>
    </div>
  );
}
