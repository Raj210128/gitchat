"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, FileCode, Hash, Zap } from "lucide-react";
import type { SourceReference } from "@/types";

interface SourcesDrawerProps {
  sources: SourceReference[];
}

const LANGUAGE_COLORS: Record<string, string> = {
  python:     "#3572A5",
  typescript: "#2b7489",
  javascript: "#f1e05a",
  tsx:        "#61dafb",
  go:         "#00ADD8",
  java:       "#b07219",
  rust:       "#dea584",
  cpp:        "#f34b7d",
  c:          "#555555",
  ruby:       "#701516",
  php:        "#4F5D95",
  swift:      "#ffac45",
  kotlin:     "#A97BFF",
  markdown:   "#083fa1",
  yaml:       "#cb171e",
};

const NODE_TYPE_LABELS: Record<string, string> = {
  function:  "fn",
  class:     "cls",
  interface: "iface",
  method:    "mth",
  module:    "mod",
  unknown:   "—",
};

export default function SourcesDrawer({ sources }: SourcesDrawerProps) {
  const [open, setOpen] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (sources.length === 0) return null;

  return (
    <div className="mt-3 rounded-[var(--radius-md)] border border-[var(--border-muted)] overflow-hidden">
      {/* Toggle header */}
      <button
        type="button"
        id="sources-drawer-toggle"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-muted)] transition-colors text-left group"
      >
        <div className="flex items-center gap-2">
          <FileCode className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-secondary)]">
            {sources.length} source{sources.length > 1 ? "s" : ""} retrieved
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {/* Score pills */}
          <div className="hidden sm:flex gap-1">
            {sources.slice(0, 3).map((s) => (
              <span
                key={s.chunk_id}
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--bg-emphasis)] text-[var(--text-muted)] font-mono"
              >
                {(s.score * 100).toFixed(0)}%
              </span>
            ))}
          </div>
          {open ? (
            <ChevronUp className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--text-secondary)] transition-colors" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--text-secondary)] transition-colors" />
          )}
        </div>
      </button>

      {/* Source list */}
      {open && (
        <div className="divide-y divide-[var(--border-muted)] animate-fade-in">
          {sources.map((src, idx) => {
            const langColor = LANGUAGE_COLORS[src.language] ?? "#8b949e";
            const isExpanded = expandedIdx === idx;
            return (
              <div key={src.chunk_id} className="bg-[var(--bg-overlay)]">
                <button
                  type="button"
                  onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                  className="w-full flex items-start gap-3 px-3.5 py-2.5 hover:bg-[var(--bg-subtle)] transition-colors text-left"
                >
                  {/* Rank badge */}
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[var(--bg-muted)] flex items-center justify-center text-[10px] font-bold text-[var(--text-muted)] mt-0.5">
                    {idx + 1}
                  </span>

                  <div className="flex-1 min-w-0 flex flex-col gap-1">
                    {/* File path */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-mono text-[var(--text-link)] truncate max-w-[220px]">
                        {src.file_path}
                      </span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {/* Lang badge */}
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded-sm font-medium"
                          style={{ background: `${langColor}22`, color: langColor }}
                        >
                          {src.language}
                        </span>
                        {/* Node type */}
                        <span className="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--bg-muted)] text-[var(--text-muted)] font-mono">
                          {NODE_TYPE_LABELS[src.node_type] ?? src.node_type}
                        </span>
                      </div>
                    </div>

                    {/* Meta row */}
                    <div className="flex items-center gap-3 text-[10px] text-[var(--text-muted)]">
                      <span className="flex items-center gap-1">
                        <Hash className="w-2.5 h-2.5" />
                        L{src.start_line}–{src.end_line}
                      </span>
                      {src.node_name && (
                        <span className="font-mono text-[var(--text-secondary)] truncate max-w-[120px]">
                          {src.node_name}
                        </span>
                      )}
                      {/* Score bar */}
                      <span className="flex items-center gap-1 ml-auto">
                        <Zap className="w-2.5 h-2.5 text-[var(--accent-start)]" />
                        <div className="w-16 h-1 bg-[var(--bg-muted)] rounded-full overflow-hidden">
                          <div
                            className="h-full gradient-accent rounded-full"
                            style={{ width: `${Math.round(src.score * 100)}%` }}
                          />
                        </div>
                        <span className="font-mono">{(src.score * 100).toFixed(0)}%</span>
                      </span>
                    </div>
                  </div>

                  <ChevronDown
                    className={`w-3.5 h-3.5 text-[var(--text-muted)] flex-shrink-0 mt-1 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                  />
                </button>

                {/* Code snippet */}
                {isExpanded && src.snippet && (
                  <div className="px-3.5 pb-3 animate-fade-in">
                    <pre className="text-[11px] font-mono text-[var(--text-secondary)] bg-[var(--bg-canvas)] border border-[var(--border-muted)] rounded-[var(--radius-sm)] p-3 overflow-x-auto leading-relaxed whitespace-pre-wrap break-words max-h-40">
                      {src.snippet}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
