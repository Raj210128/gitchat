"use client";

import { useEffect, useRef } from "react";
import { MessageSquare, GitBranch, Zap, Code2 } from "lucide-react";
import type { Message } from "@/types";
import MessageBubble from "./MessageBubble";

interface ChatWindowProps {
  messages: Message[];
  repoId: string | null;
}

const EXAMPLE_PROMPTS = [
  { icon: Code2,      text: "How is authentication implemented?" },
  { icon: GitBranch,  text: "What does the main entry point do?" },
  { icon: Zap,        text: "Explain the data models in this repo" },
  { icon: MessageSquare, text: "What are the key API endpoints?" },
];

export default function ChatWindow({ messages, repoId }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex-1 messages-scroll flex flex-col gap-4 px-4 py-4 overflow-y-auto">
      {isEmpty ? (
        /* Empty state */
        <div className="flex-1 flex flex-col items-center justify-center gap-8 py-16 animate-fade-in">
          {/* Logo mark */}
          <div className="relative">
            <div className="w-20 h-20 rounded-2xl gradient-accent flex items-center justify-center shadow-xl animate-glow">
              <MessageSquare className="w-9 h-9 text-white" />
            </div>
            <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-[var(--color-success)] rounded-full border-2 border-[var(--bg-canvas)] flex items-center justify-center">
              <Code2 className="w-3 h-3 text-white" />
            </div>
          </div>

          <div className="text-center max-w-sm">
            <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
              {repoId ? "Repository ready!" : "Chat with your codebase"}
            </h3>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              {repoId
                ? "Ask any question about the indexed repository. I'll find the relevant code and explain it."
                : "Index a GitHub repository on the left, then ask questions about it here."}
            </p>
          </div>

          {/* Example prompts */}
          {repoId && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md">
              {EXAMPLE_PROMPTS.map(({ icon: Icon, text }) => (
                <div
                  key={text}
                  className="card px-3.5 py-2.5 flex items-center gap-2.5 hover:border-[var(--accent-start)]/50 hover:bg-[var(--bg-subtle)] cursor-default transition-all duration-200 group"
                >
                  <Icon className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--text-link)] transition-colors flex-shrink-0" />
                  <span className="text-xs text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
                    {text}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Message list */
        <>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={bottomRef} className="h-2" />
        </>
      )}
    </div>
  );
}
