"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Clock, Zap, User, Bot } from "lucide-react";
import type { Message } from "@/types";
import SourcesDrawer from "./SourcesDrawer";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end animate-slide-right">
        <div className="flex items-end gap-2 max-w-[80%]">
          <div className="gradient-accent rounded-[var(--radius-lg)] rounded-br-[var(--radius-sm)] px-4 py-2.5 shadow-md">
            <p className="text-sm text-white whitespace-pre-wrap break-words leading-relaxed">
              {message.content}
            </p>
          </div>
          <div className="w-7 h-7 rounded-full bg-[var(--bg-emphasis)] flex items-center justify-center flex-shrink-0 mb-0.5">
            <User className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
          </div>
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex justify-start animate-slide-left">
      <div className="flex items-start gap-2 max-w-[90%] w-full">
        {/* Bot avatar */}
        <div className="w-7 h-7 rounded-full gradient-accent flex items-center justify-center flex-shrink-0 mt-0.5 shadow-md animate-glow">
          <Bot className="w-3.5 h-3.5 text-white" />
        </div>

        <div className="flex-1 min-w-0">
          {/* Bubble */}
          <div className="card px-4 py-3 rounded-tl-[var(--radius-sm)]">
            {message.content ? (
              <div className="prose-code text-sm text-[var(--text-primary)] leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Code blocks
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className ?? "");
                      const isBlock = !!match;
                      const codeStr = String(children).replace(/\n$/, "");

                      if (isBlock) {
                        return (
                          <SyntaxHighlighter
                            style={oneDark as Record<string, React.CSSProperties>}
                            language={match[1]}
                            PreTag="div"
                            customStyle={{
                              margin: "0.75rem 0",
                              borderRadius: "var(--radius-md)",
                              border: "1px solid var(--border-default)",
                              fontSize: "12.5px",
                              lineHeight: "1.6",
                              background: "#0d1117",
                            }}
                          >
                            {codeStr}
                          </SyntaxHighlighter>
                        );
                      }
                      return (
                        <code
                          className="font-mono text-[0.85em] bg-[var(--bg-subtle)] px-1.5 py-0.5 rounded text-orange-400"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    // Paragraphs
                    p({ children }) {
                      return <p className="mb-3 last:mb-0">{children}</p>;
                    },
                    // Headings
                    h1({ children }) { return <h1 className="text-lg font-bold mb-2 text-[var(--text-primary)]">{children}</h1>; },
                    h2({ children }) { return <h2 className="text-base font-semibold mb-2 text-[var(--text-primary)]">{children}</h2>; },
                    h3({ children }) { return <h3 className="text-sm font-semibold mb-1.5 text-[var(--text-primary)]">{children}</h3>; },
                    // Lists
                    ul({ children }) { return <ul className="list-disc list-inside mb-3 space-y-1 text-[var(--text-primary)]">{children}</ul>; },
                    ol({ children }) { return <ol className="list-decimal list-inside mb-3 space-y-1 text-[var(--text-primary)]">{children}</ol>; },
                    li({ children }) { return <li className="text-sm">{children}</li>; },
                    // Blockquote
                    blockquote({ children }) {
                      return (
                        <blockquote className="border-l-2 border-[var(--accent-start)] pl-3 text-[var(--text-secondary)] italic my-2">
                          {children}
                        </blockquote>
                      );
                    },
                    // Strong / em
                    strong({ children }) { return <strong className="font-semibold text-[var(--text-primary)]">{children}</strong>; },
                    // Table
                    table({ children }) {
                      return (
                        <div className="overflow-x-auto my-3">
                          <table className="w-full text-xs border-collapse">{children}</table>
                        </div>
                      );
                    },
                    th({ children }) {
                      return <th className="border border-[var(--border-default)] px-3 py-1.5 bg-[var(--bg-subtle)] text-left font-semibold">{children}</th>;
                    },
                    td({ children }) {
                      return <td className="border border-[var(--border-default)] px-3 py-1.5">{children}</td>;
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : (
              /* Skeleton while streaming hasn't started */
              <div className="flex flex-col gap-2 py-1">
                <div className="skeleton h-3 w-3/4 rounded" />
                <div className="skeleton h-3 w-1/2 rounded" />
              </div>
            )}

            {/* Streaming cursor */}
            {message.streaming && message.content && (
              <span className="inline-block w-0.5 h-4 bg-[var(--accent-start)] ml-0.5 align-middle animate-blink" />
            )}
          </div>

          {/* Meta row */}
          {!message.streaming && message.content && (
            <div className="flex items-center gap-3 mt-1.5 px-1">
              {message.latency_ms !== undefined && (
                <span className="flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
                  <Clock className="w-2.5 h-2.5" />
                  {message.latency_ms}ms
                </span>
              )}
              {message.cached && (
                <span className="flex items-center gap-1 text-[10px] text-[var(--color-success)]">
                  <Zap className="w-2.5 h-2.5" />
                  cached
                </span>
              )}
              <span className="text-[10px] text-[var(--text-muted)] ml-auto">
                {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          )}

          {/* Sources drawer */}
          {message.sources && message.sources.length > 0 && (
            <SourcesDrawer sources={message.sources} />
          )}
        </div>
      </div>
    </div>
  );
}
