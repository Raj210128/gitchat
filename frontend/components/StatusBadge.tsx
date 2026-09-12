"use client";

import type { IngestStatus } from "@/types";

interface StatusBadgeProps {
  status: IngestStatus;
  className?: string;
}

const STATUS_CONFIG: Record<
  IngestStatus,
  { label: string; dotClass: string; textClass: string; bgClass: string }
> = {
  pending: {
    label: "Pending",
    dotClass: "bg-[var(--color-pending)]",
    textClass: "text-[var(--text-secondary)]",
    bgClass: "bg-[var(--bg-muted)]",
  },
  running: {
    label: "Indexing…",
    dotClass: "bg-[var(--color-warning)] animate-[pulse-dot_1s_ease-in-out_infinite]",
    textClass: "text-[var(--color-warning)]",
    bgClass: "bg-amber-950/40",
  },
  completed: {
    label: "Ready",
    dotClass: "bg-[var(--color-success)]",
    textClass: "text-[var(--color-success)]",
    bgClass: "bg-green-950/40",
  },
  failed: {
    label: "Failed",
    dotClass: "bg-[var(--color-danger)]",
    textClass: "text-[var(--color-danger)]",
    bgClass: "bg-red-950/40",
  },
};

export default function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status];

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.bgClass} ${cfg.textClass} ${className}`}
    >
      <span
        className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dotClass}`}
        style={
          status === "running"
            ? { animation: "pulse-dot 1s ease-in-out infinite" }
            : undefined
        }
      />
      {cfg.label}
    </span>
  );
}
