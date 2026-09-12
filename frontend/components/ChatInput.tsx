"use client";

import { useRef, useCallback, KeyboardEvent } from "react";
import { Send, Loader2, Radio } from "lucide-react";

interface ChatInputProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
  streaming: boolean;
  repoReady: boolean;
  useStream: boolean;
  onToggleStream: () => void;
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
  streaming,
  repoReady,
  useStream,
  onToggleStream,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow the textarea
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      onChange(e.target.value);
      const el = e.target;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    },
    [onChange]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!disabled && value.trim()) onSend();
      }
    },
    [disabled, value, onSend]
  );

  const canSend = !disabled && value.trim().length > 0 && repoReady;

  return (
    <div className="flex flex-col gap-2">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-1">
        <p className="text-[11px] text-[var(--text-muted)]">
          {repoReady
            ? "Ask anything about the indexed repository"
            : "Index a repository first to start chatting"}
        </p>
        {/* Stream toggle */}
        <button
          id="stream-toggle"
          type="button"
          onClick={onToggleStream}
          title={useStream ? "Streaming ON" : "Streaming OFF"}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-all duration-200 ${
            useStream
              ? "bg-[var(--accent-start)]/15 border-[var(--accent-start)]/30 text-[var(--text-link)]"
              : "bg-[var(--bg-muted)] border-[var(--border-default)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
          }`}
        >
          <Radio className={`w-3 h-3 ${useStream ? "animate-pulse" : ""}`} />
          Stream
        </button>
      </div>

      {/* Input container */}
      <div
        className={`relative flex items-end gap-2 rounded-[var(--radius-lg)] border bg-[var(--bg-overlay)] px-4 py-3 transition-all duration-200 ${
          !repoReady
            ? "opacity-50 border-[var(--border-muted)]"
            : "border-[var(--border-default)] focus-within:border-[var(--accent-start)] focus-within:shadow-[0_0_0_3px_var(--accent-glow)]"
        }`}
      >
        <textarea
          id="chat-input"
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled || !repoReady}
          rows={1}
          placeholder={
            repoReady
              ? "Ask a question… (Enter to send, Shift+Enter for newline)"
              : "Index a repository to unlock chat"
          }
          className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none resize-none leading-relaxed disabled:cursor-not-allowed"
          style={{ minHeight: "24px", maxHeight: "160px" }}
        />

        {/* Send button */}
        <button
          id="send-button"
          type="button"
          onClick={onSend}
          disabled={!canSend}
          className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-[var(--radius-md)] gradient-accent text-white transition-all duration-200 hover:opacity-90 hover:shadow-[var(--shadow-glow)] active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:shadow-none"
          title="Send (Enter)"
        >
          {streaming ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </div>

      <p className="text-[10px] text-[var(--text-muted)] text-center">
        Powered by GPT-4o · RAG · Hybrid retrieval
      </p>
    </div>
  );
}
