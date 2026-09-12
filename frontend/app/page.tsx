"use client";

import { useState, useCallback, useRef } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { GitBranch, Sparkles, ChevronLeft, ChevronRight } from "lucide-react";

const uuidv4 = () => crypto.randomUUID();
import type { Message, SourceReference } from "@/types";
import { chatSync } from "@/lib/api";
import IngestPanel from "@/components/IngestPanel";
import ChatWindow from "@/components/ChatWindow";
import ChatInput from "@/components/ChatInput";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [repoId, setRepoId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  // ── Helpers ──────────────────────────────────────────────────────────────────
  const addMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg]);
    return msg.id;
  }, []);

  const updateMessage = useCallback(
    (id: string, patch: Partial<Message>) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...patch } : m))
      );
    },
    []
  );

  // ── Handle repo ready ─────────────────────────────────────────────────────
  const handleRepoReady = useCallback((id: string) => {
    setRepoId(id);
    setMessages([]);
  }, []);

  // ── SSE streaming send ────────────────────────────────────────────────────
  const sendStreaming = useCallback(
    async (question: string) => {
      if (!repoId) return;

      const userMsgId = uuidv4();
      const asstMsgId = uuidv4();

      addMessage({
        id: userMsgId,
        role: "user",
        content: question,
        timestamp: new Date(),
      });

      addMessage({
        id: asstMsgId,
        role: "assistant",
        content: "",
        streaming: true,
        timestamp: new Date(),
      });

      setStreaming(true);
      abortRef.current = new AbortController();

      const params = new URLSearchParams({ repo_id: repoId, question, top_k: "8" });
      const url = `${API_BASE}/api/v1/chat/stream?${params}`;

      let tokenBuffer = "";

      try {
        await fetchEventSource(url, {
          signal: abortRef.current.signal,
          onopen: async (res) => {
            if (!res.ok) {
              throw new Error(`SSE error: ${res.status}`);
            }
          },
          onmessage: (event) => {
            if (event.event === "sources") {
              try {
                const sources: SourceReference[] = JSON.parse(event.data);
                updateMessage(asstMsgId, { sources });
              } catch { /* ignore parse error */ }
            } else if (event.event === "token") {
              tokenBuffer += event.data;
              updateMessage(asstMsgId, { content: tokenBuffer });
            } else if (event.event === "done") {
              updateMessage(asstMsgId, { streaming: false });
              setStreaming(false);
            } else if (event.event === "error") {
              updateMessage(asstMsgId, {
                content: `❌ ${event.data}`,
                streaming: false,
              });
              setStreaming(false);
            }
          },
          onerror: (err) => {
            updateMessage(asstMsgId, {
              content: "❌ Connection error. Is the backend running?",
              streaming: false,
            });
            setStreaming(false);
            throw err; // stop retrying
          },
        });
      } catch {
        setStreaming(false);
        updateMessage(asstMsgId, {
          content: tokenBuffer || "❌ Stream interrupted.",
          streaming: false,
        });
      }
    },
    [repoId, addMessage, updateMessage]
  );

  // ── Sync send ─────────────────────────────────────────────────────────────
  const sendSync = useCallback(
    async (question: string) => {
      if (!repoId) return;

      const userMsgId = uuidv4();
      const asstMsgId = uuidv4();

      addMessage({
        id: userMsgId,
        role: "user",
        content: question,
        timestamp: new Date(),
      });

      addMessage({
        id: asstMsgId,
        role: "assistant",
        content: "",
        streaming: true,
        timestamp: new Date(),
      });

      setStreaming(true);
      try {
        const t0 = Date.now();
        const resp = await chatSync(repoId, question);
        updateMessage(asstMsgId, {
          content: resp.answer,
          sources: resp.sources,
          cached: resp.cached,
          latency_ms: resp.latency_ms ?? Date.now() - t0,
          streaming: false,
        });
      } catch (e: unknown) {
        updateMessage(asstMsgId, {
          content: `❌ ${e instanceof Error ? e.message : "Unknown error"}`,
          streaming: false,
        });
      } finally {
        setStreaming(false);
      }
    },
    [repoId, addMessage, updateMessage]
  );

  // ── On send ───────────────────────────────────────────────────────────────
  const handleSend = useCallback(() => {
    const q = input.trim();
    if (!q || streaming || !repoId) return;
    setInput("");
    if (useStream) {
      sendStreaming(q);
    } else {
      sendSync(q);
    }
  }, [input, streaming, repoId, useStream, sendStreaming, sendSync]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen bg-[var(--bg-canvas)]">
      {/* ── Top bar ──────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)] bg-[var(--bg-overlay)] shadow-sm flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md gradient-accent flex items-center justify-center">
            <GitBranch className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold gradient-text leading-tight">GitChat</h1>
            <p className="text-[10px] text-[var(--text-muted)] leading-tight hidden sm:block">
              AI code assistant powered by RAG
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {repoId && (
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--bg-muted)] border border-[var(--border-default)]">
              <GitBranch className="w-3 h-3 text-[var(--text-muted)]" />
              <span className="text-[11px] text-[var(--text-secondary)] font-mono truncate max-w-[160px]">
                {repoId.replace("__", "/")}
              </span>
            </div>
          )}
          <div className="flex items-center gap-1 text-[11px] text-[var(--text-muted)]">
            <Sparkles className="w-3 h-3 text-[var(--accent-start)]" />
            <span>GPT-4o</span>
          </div>
        </div>
      </header>

      {/* ── Main layout ──────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Sidebar: Ingest Panel ──────────────────────────────────────── */}
        <aside
          className={`flex-shrink-0 border-r border-[var(--border-default)] bg-[var(--bg-overlay)] transition-all duration-300 overflow-y-auto ${
            sidebarOpen ? "w-[300px] xl:w-[320px]" : "w-0 overflow-hidden border-r-0"
          }`}
        >
          <div className="p-5 min-w-[300px]">
            <IngestPanel onReady={handleRepoReady} />
          </div>
        </aside>

        {/* ── Sidebar toggle tab ─────────────────────────────────────────── */}
        <button
          type="button"
          id="sidebar-toggle"
          onClick={() => setSidebarOpen((v) => !v)}
          title={sidebarOpen ? "Hide panel" : "Show panel"}
          className="flex-shrink-0 w-5 self-stretch flex items-center justify-center bg-[var(--bg-subtle)] border-r border-[var(--border-muted)] hover:bg-[var(--bg-muted)] transition-colors group"
        >
          {sidebarOpen ? (
            <ChevronLeft className="w-3 h-3 text-[var(--text-muted)] group-hover:text-[var(--text-secondary)] transition-colors" />
          ) : (
            <ChevronRight className="w-3 h-3 text-[var(--text-muted)] group-hover:text-[var(--text-secondary)] transition-colors" />
          )}
        </button>

        {/* ── Chat area ─────────────────────────────────────────────────── */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <ChatWindow messages={messages} repoId={repoId} />

          {/* Input */}
          <div className="flex-shrink-0 border-t border-[var(--border-default)] bg-[var(--bg-overlay)] px-4 pt-3 pb-4">
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={handleSend}
              disabled={streaming}
              streaming={streaming}
              repoReady={!!repoId}
              useStream={useStream}
              onToggleStream={() => setUseStream((v) => !v)}
            />
          </div>
        </main>
      </div>
    </div>
  );
}
