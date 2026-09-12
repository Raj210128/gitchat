"use client";

import { useState, useCallback, useRef } from "react";
import { GitFork, Loader2, RefreshCw, ChevronDown, ChevronUp, CheckCircle, AlertCircle } from "lucide-react";
import { startIngest, pollIngestStatus } from "@/lib/api";
import type { IngestStatusResponse } from "@/types";
import StatusBadge from "./StatusBadge";

interface IngestPanelProps {
  onReady: (repoId: string) => void;
}

export default function IngestPanel({ onReady }: IngestPanelProps) {
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [force, setForce] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<IngestStatusResponse | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const handleSubmit = useCallback(async () => {
    const trimmed = url.trim();
    if (!trimmed) return;
    if (!trimmed.includes("github.com")) {
      setError("Please enter a valid GitHub repository URL.");
      return;
    }

    setError(null);
    setLoading(true);
    setJob(null);
    stopPolling();

    try {
      const initial = await startIngest({ repo_url: trimmed, branch, force_reindex: force });
      setJob(initial);

      // Poll for status every 2.5 seconds
      pollRef.current = setInterval(async () => {
        try {
          const status = await pollIngestStatus(initial.job_id);
          setJob(status);
          if (status.status === "completed") {
            stopPolling();
            setLoading(false);
            // Derive repo_id the same way the backend does
            const parsed = new URL(trimmed);
            const repoId = parsed.pathname.replace(/^\//, "").replace(/\.git$/, "").replace(/\//g, "__");
            onReady(repoId);
          } else if (status.status === "failed") {
            stopPolling();
            setLoading(false);
            setError(status.error ?? "Ingestion failed. Please try again.");
          }
        } catch {
          // silently ignore transient poll errors
        }
      }, 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start ingestion.");
      setLoading(false);
    }
  }, [url, branch, force, stopPolling, onReady]);

  const progressPercent =
    job?.status === "running" && job.files_processed > 0
      ? Math.min(95, Math.round((job.chunks_indexed / Math.max(job.chunks_indexed + 50, 1)) * 100))
      : 0;

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg gradient-accent flex items-center justify-center shadow-lg flex-shrink-0">
          <GitFork className="w-4 h-4 text-white" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Index Repository</h2>
          <p className="text-xs text-[var(--text-muted)]">Clone &amp; embed any public GitHub repo</p>
        </div>
      </div>

      {/* URL Input */}
      <div className="flex flex-col gap-2">
        <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide">
          Repository URL
        </label>
        <div
          className={`flex items-center gap-2 rounded-[var(--radius-md)] border bg-[var(--bg-subtle)] px-3 py-2.5 transition-all duration-200 ${
            error ? "border-[var(--color-danger)]" : "border-[var(--border-default)] focus-within:border-[var(--accent-start)] focus-within:shadow-[0_0_0_3px_var(--accent-glow)]"
          }`}
        >
          <span className="text-[var(--text-muted)] text-xs font-mono select-none">github.com/</span>
          <input
            id="repo-url-input"
            type="url"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setError(null); }}
            onKeyDown={(e) => { if (e.key === "Enter" && !loading) handleSubmit(); }}
            placeholder="owner/repository"
            disabled={loading}
            className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none disabled:opacity-50"
          />
        </div>
        {error && (
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-danger)] animate-fade-in">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Advanced toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced((v) => !v)}
        className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors w-fit"
      >
        {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        Advanced options
      </button>

      {showAdvanced && (
        <div className="flex flex-col gap-3 p-3 rounded-[var(--radius-md)] bg-[var(--bg-subtle)] border border-[var(--border-muted)] animate-fade-in">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--text-secondary)]">Branch / Tag</label>
            <input
              id="branch-input"
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              disabled={loading}
              className="bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-[var(--radius-sm)] px-3 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-start)] disabled:opacity-50 transition-colors"
            />
          </div>
          <label className="flex items-center gap-2.5 cursor-pointer select-none">
            <input
              id="force-reindex-checkbox"
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              disabled={loading}
              className="w-4 h-4 accent-[var(--accent-start)] rounded cursor-pointer"
            />
            <span className="text-xs text-[var(--text-secondary)]">Force re-index (drop existing vectors)</span>
          </label>
        </div>
      )}

      {/* Submit button */}
      <button
        id="ingest-button"
        type="button"
        onClick={handleSubmit}
        disabled={loading || !url.trim()}
        className="relative flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-[var(--radius-md)] text-sm font-semibold text-white gradient-accent shadow-lg transition-all duration-200 hover:opacity-90 hover:shadow-[var(--shadow-glow)] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Indexing…
          </>
        ) : job?.status === "completed" ? (
          <>
            <RefreshCw className="w-4 h-4" />
            Re-index
          </>
        ) : (
          <>
            <GitFork className="w-4 h-4" />
            Index Repository
          </>
        )}
      </button>

      {/* Job status card */}
      {job && (
        <div className="card p-4 flex flex-col gap-3 animate-fade-in">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[var(--text-secondary)] truncate max-w-[160px]">
              {job.repo_url.replace("https://github.com/", "")}
            </span>
            <StatusBadge status={job.status} />
          </div>

          {/* Progress bar */}
          {job.status === "running" && (
            <div className="flex flex-col gap-1.5">
              <div className="h-1.5 bg-[var(--bg-muted)] rounded-full overflow-hidden">
                {progressPercent > 0 ? (
                  <div
                    className="h-full gradient-accent rounded-full transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                ) : (
                  <div className="h-full w-1/3 gradient-accent rounded-full"
                    style={{ animation: "progress-indeterminate 1.5s ease-in-out infinite" }}
                  />
                )}
              </div>
              <div className="flex justify-between text-[10px] text-[var(--text-muted)]">
                <span>{job.files_processed} files</span>
                <span>{job.chunks_indexed.toLocaleString()} chunks</span>
              </div>
            </div>
          )}

          {job.status === "completed" && (
            <div className="flex items-center gap-2 text-xs text-[var(--color-success)] animate-fade-in">
              <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
              {job.files_processed} files · {job.chunks_indexed.toLocaleString()} chunks indexed
            </div>
          )}

          {job.status === "failed" && job.error && (
            <div className="text-xs text-[var(--color-danger)] bg-red-950/30 rounded-[var(--radius-sm)] p-2 font-mono break-all">
              {job.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
