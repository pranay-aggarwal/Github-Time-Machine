"use client";

import { useEffect, useState } from "react";
import { GitBranch, History, Loader2, Search, ShieldCheck } from "lucide-react";
import {
  analyzeRepo,
  askQuestion,
  getGraph,
  getStatus,
  getSummary,
  getTimeline,
  type ChatResponse,
  type GraphResponse,
  type StatusResponse,
  type SummaryResponse,
  type TimelineResponse
} from "@/lib/api";
import { Background, Controls, ReactFlow } from "@xyflow/react";

type View = "dashboard" | "chat" | "graph" | "timeline";

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/redis/redis-py");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [question, setQuestion] = useState("Why was Redis introduced?");
  const [chat, setChat] = useState<ChatResponse | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!jobId || status?.status === "ready" || status?.status === "failed") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await getStatus(jobId);
        setStatus(next);
        if (next.status === "ready" && next.repo_id) {
          const repoSummary = await getSummary(next.repo_id);
          setSummary(repoSummary);
          setGraph(await getGraph(next.repo_id));
          setTimeline(await getTimeline(next.repo_id));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to fetch status");
      }
    }, 1600);
    return () => window.clearInterval(timer);
  }, [jobId, status?.status]);

  async function startAnalysis() {
    setBusy(true);
    setError(null);
    setChat(null);
    try {
      const result = await analyzeRepo(repoUrl);
      setJobId(result.job_id);
      setStatus({ job_id: result.job_id, repo_id: null, status: "queued", progress: 0, message: "Queued for analysis" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed to start");
    } finally {
      setBusy(false);
    }
  }

  async function startDemo() {
    setRepoUrl("demo://github-time-machine");
    setBusy(true);
    setError(null);
    setChat(null);
    try {
      const result = await analyzeRepo("demo://github-time-machine");
      setJobId(result.job_id);
      setStatus({ job_id: result.job_id, repo_id: null, status: "queued", progress: 0, message: "Queued seeded demo" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo failed to start");
    } finally {
      setBusy(false);
    }
  }

  async function submitQuestion(nextQuestion = question) {
    if (!summary) return;
    setBusy(true);
    setError(null);
    setQuestion(nextQuestion);
    try {
      setChat(await askQuestion(summary.repo_id, nextQuestion));
      setView("chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setBusy(false);
    }
  }

  const ready = status?.status === "ready" && summary;

  return (
    <main className="min-h-screen">
      <section className="border-b border-line bg-paper/90">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-5 py-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-normal text-ink">GitHub Time Machine</h1>
              <p className="mt-2 max-w-2xl text-sm text-ink/70">
                Ask why software changed, backed by commits, PRs, issues, and graph evidence.
              </p>
            </div>
            <div className="flex items-center gap-2 text-sm text-mint">
              <ShieldCheck size={18} />
              Evidence-bound answers
            </div>
          </div>

          <div className="flex flex-col gap-3 md:flex-row">
            <div className="relative flex-1">
              <GitBranch className="absolute left-3 top-3 text-ink/45" size={18} />
              <input
                className="h-11 w-full rounded-md border border-line bg-white pl-10 pr-3 text-sm outline-none ring-mint/30 focus:ring-4"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
              />
            </div>
            <button
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-ink px-5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
              onClick={startAnalysis}
              disabled={busy}
            >
              {busy ? <Loader2 className="animate-spin" size={18} /> : <Search size={18} />}
              Analyze
            </button>
            <button
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium text-ink disabled:cursor-not-allowed disabled:opacity-60"
              onClick={startDemo}
              disabled={busy}
            >
              <History size={18} />
              Demo
            </button>
          </div>

          {status && (
            <div className="rounded-md border border-line bg-white p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium capitalize">{status.status}</span>
                <span>{status.progress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-line">
                <div className="h-full bg-mint transition-all" style={{ width: `${status.progress}%` }} />
              </div>
              <p className="mt-2 text-sm text-ink/70">{status.message}</p>
            </div>
          )}

          {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-5">
        <div className="mb-5 flex flex-wrap gap-2">
          {(["dashboard", "chat", "graph", "timeline"] as View[]).map((item) => (
            <button
              key={item}
              className={`rounded-md border px-3 py-2 text-sm capitalize ${view === item ? "border-ink bg-ink text-white" : "border-line bg-white"}`}
              onClick={() => setView(item)}
            >
              {item}
            </button>
          ))}
        </div>

        {!ready && (
          <div className="flex min-h-[360px] items-center justify-center rounded-md border border-dashed border-line bg-white/70 p-8 text-center text-ink/65">
            Paste a public GitHub repository URL and start analysis.
          </div>
        )}

        {ready && view === "dashboard" && <Dashboard summary={summary} onAsk={submitQuestion} />}
        {ready && view === "chat" && (
          <ChatPanel
            question={question}
            setQuestion={setQuestion}
            busy={busy}
            chat={chat}
            onSubmit={() => submitQuestion()}
            suggestions={summary.suggested_questions}
            onAsk={submitQuestion}
          />
        )}
        {ready && view === "graph" && <GraphPanel graph={graph} />}
        {ready && view === "timeline" && <TimelinePanel timeline={timeline} />}
      </section>
    </main>
  );
}

function Dashboard({ summary, onAsk }: { summary: SummaryResponse; onAsk: (question: string) => void }) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
      <div className="rounded-md border border-line bg-white p-5">
        <h2 className="text-xl font-semibold">{summary.name}</h2>
        <a className="mt-1 block text-sm text-mint" href={summary.url} target="_blank">
          {summary.url}
        </a>
        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
          {Object.entries(summary.metrics).map(([key, value]) => (
            <div key={key} className="rounded-md border border-line p-4">
              <div className="text-2xl font-semibold">{value}</div>
              <div className="mt-1 text-xs uppercase text-ink/55">{key.replace("_", " ")}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-md border border-line bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase text-ink/60">Suggested questions</h3>
        <div className="flex flex-col gap-2">
          {summary.suggested_questions.map((item) => (
            <button key={item} className="rounded-md border border-line px-3 py-2 text-left text-sm hover:border-mint" onClick={() => onAsk(item)}>
              {item}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChatPanel(props: {
  question: string;
  setQuestion: (value: string) => void;
  busy: boolean;
  chat: ChatResponse | null;
  onSubmit: () => void;
  suggestions: string[];
  onAsk: (question: string) => void;
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_420px]">
      <div className="rounded-md border border-line bg-white p-5">
        <div className="flex gap-2">
          <input
            className="h-11 flex-1 rounded-md border border-line px-3 text-sm outline-none ring-mint/30 focus:ring-4"
            value={props.question}
            onChange={(event) => props.setQuestion(event.target.value)}
          />
          <button className="inline-flex h-11 items-center gap-2 rounded-md bg-ink px-4 text-sm text-white" onClick={props.onSubmit} disabled={props.busy}>
            {props.busy ? <Loader2 className="animate-spin" size={18} /> : <Search size={18} />}
            Ask
          </button>
        </div>
        {props.chat ? (
          <div className="mt-5">
            <div className="mb-3 inline-flex rounded-md bg-mint/10 px-2 py-1 text-xs font-medium text-mint">
              Confidence {Math.round(props.chat.confidence * 100)}%
            </div>
            <p className="text-base leading-7">{props.chat.answer}</p>
            <div className="mt-5">
              <h3 className="text-sm font-semibold uppercase text-ink/60">Reasoning chain</h3>
              <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-ink/75">
                {props.chat.reasoning_chain.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ol>
            </div>
          </div>
        ) : (
          <div className="mt-5 rounded-md border border-dashed border-line p-6 text-sm text-ink/60">Ask a repository history question.</div>
        )}
      </div>
      <EvidencePanel evidence={props.chat?.evidence ?? []} suggestions={props.suggestions} onAsk={props.onAsk} />
    </div>
  );
}

function EvidencePanel({ evidence, suggestions, onAsk }: { evidence: ChatResponse["evidence"]; suggestions: string[]; onAsk: (question: string) => void }) {
  return (
    <div className="rounded-md border border-line bg-white p-5">
      <h3 className="text-sm font-semibold uppercase text-ink/60">Evidence explorer</h3>
      <div className="mt-3 flex flex-col gap-3">
        {evidence.length === 0 &&
          suggestions.map((item) => (
            <button key={item} className="rounded-md border border-line px-3 py-2 text-left text-sm hover:border-mint" onClick={() => onAsk(item)}>
              {item}
            </button>
          ))}
        {evidence.map((item) => (
          <a key={item.id} href={item.url ?? "#"} target="_blank" className="rounded-md border border-line p-3 hover:border-mint">
            <div className="text-xs uppercase text-plum">{item.source_type}</div>
            <div className="mt-1 text-sm font-medium">{item.title}</div>
            <p className="mt-2 max-h-20 overflow-hidden text-xs leading-5 text-ink/65">{item.snippet}</p>
          </a>
        ))}
      </div>
    </div>
  );
}

function GraphPanel({ graph }: { graph: GraphResponse | null }) {
  return (
    <div className="h-[620px] overflow-hidden rounded-md border border-line bg-white">
      {graph ? (
        <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView>
          <Background />
          <Controls />
        </ReactFlow>
      ) : (
        <div className="flex h-full items-center justify-center text-sm text-ink/60">No graph loaded.</div>
      )}
    </div>
  );
}

function TimelinePanel({ timeline }: { timeline: TimelineResponse | null }) {
  const categories = Array.from(new Set((timeline?.events ?? []).map((event) => event.category).filter(Boolean)));
  return (
    <div className="rounded-md border border-line bg-white">
      <div className="border-b border-line p-5">
        <div className="flex items-center gap-2">
          <History size={18} />
          <h2 className="text-lg font-semibold">Architecture evolution</h2>
        </div>
        {categories.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {categories.map((category) => (
              <span key={category} className="rounded-md border border-line px-2 py-1 text-xs text-ink/65">
                {category}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-0 p-5">
        {timeline?.events.length ? (
          timeline.events.map((event) => (
            <div key={`${event.date}-${event.title}`} className="grid grid-cols-[120px_1fr] gap-4 border-l-2 border-mint pb-5 pl-4 last:pb-0">
              <div className="text-xs font-medium text-ink/55">{event.date || "Unknown date"}</div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold">{event.title}</h3>
                  {event.category && <span className="rounded-md bg-mint/10 px-2 py-1 text-xs text-mint">{event.category}</span>}
                  {typeof event.confidence === "number" && (
                    <span className="rounded-md bg-amber/10 px-2 py-1 text-xs text-amber">{Math.round(event.confidence * 100)}%</span>
                  )}
                </div>
                <p className="mt-1 text-sm leading-6 text-ink/70">{event.summary}</p>
                {event.evidence.length > 0 && <div className="mt-2 text-xs text-ink/50">{event.evidence.length} evidence item{event.evidence.length === 1 ? "" : "s"}</div>}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-md border border-dashed border-line p-6 text-sm text-ink/60">No architecture decisions detected yet.</div>
        )}
      </div>
    </div>
  );
}
