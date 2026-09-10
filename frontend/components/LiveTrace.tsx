"use client";

import type { TraceEntry, TraceStatus } from "@/lib/useLiveTrace";

interface Props {
  status: TraceStatus;
  entries: TraceEntry[];
  error: string | null;
  onRun: () => void;
}

const STATUS_LABEL: Record<TraceStatus, string> = {
  idle: "Idle",
  connecting: "Connecting…",
  streaming: "Streaming…",
  done: "Done",
  error: "Error",
};

function ToolCard({ entry }: { entry: Extract<TraceEntry, { kind: "tool" }> }) {
  const isPending = entry.status === undefined;
  return (
    <div className={`trace-tool ${isPending ? "pending" : entry.status}`}>
      <div className="trace-tool-header">
        <span className="trace-tool-badge">tool</span>
        <span className="trace-tool-name">{entry.name}</span>
        {isPending && <span className="spinner" aria-label="running" />}
      </div>
      {Object.keys(entry.input).length > 0 && (
        <pre className="trace-tool-io">{JSON.stringify(entry.input)}</pre>
      )}
      {entry.output !== undefined && (
        <pre className="trace-tool-io trace-tool-output">{truncate(entry.output, 600)}</pre>
      )}
    </div>
  );
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

export default function LiveTrace({ status, entries, error, onRun }: Props) {
  return (
    <div className="live-trace">
      <div className="live-trace-header">
        <h2>Live tool trace</h2>
        <div className="live-trace-controls">
          <span className={`status-badge status-${status}`}>{STATUS_LABEL[status]}</span>
          <button
            className="primary"
            onClick={onRun}
            disabled={status === "connecting" || status === "streaming"}
          >
            Run check now
          </button>
        </div>
      </div>

      {error && <p className="trace-error">{error}</p>}

      <div className="trace-feed">
        {entries.length === 0 && status === "idle" && (
          <p className="empty-state">
            Click &ldquo;Run check now&rdquo; to see the orchestrator&rsquo;s tool calls stream in
            live.
          </p>
        )}
        {entries.map((entry, i) =>
          entry.kind === "tool" ? (
            <ToolCard key={entry.id} entry={entry} />
          ) : (
            <div key={i} className="trace-text">
              {entry.text}
            </div>
          )
        )}
      </div>
    </div>
  );
}
