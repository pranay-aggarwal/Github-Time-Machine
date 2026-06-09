"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Clock,
  GitBranch,
  History,
  Layers3,
  Loader2,
  MessageSquare,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
  UserRound
} from "lucide-react";
import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import {
  analyzeRepo,
  askQuestion,
  getActivity,
  getGraph,
  getStatus,
  getSummary,
  getTimeline,
  type ActivityResponse,
  type ChatResponse,
  type Evidence,
  type GraphResponse,
  type StatusResponse,
  type SummaryResponse,
  type TimelineResponse
} from "@/lib/api";

type View = "overview" | "ask" | "graph" | "timeline" | "activity";
type TimelineEvent = TimelineResponse["events"][number];
type GraphNode = GraphResponse["nodes"][number];
type InspectorMode = "repo" | "evidence" | "node" | "timeline";

const NODE_TYPES = ["Repository", "ProjectProfile", "ArchitectureDecision", "Technology", "Module", "PullRequest", "Issue", "Commit", "Developer"];
const TYPE_COLORS: Record<string, string> = {
  Repository: "#15171a",
  ProjectProfile: "#2f8f83",
  ArchitectureDecision: "#c07a21",
  Technology: "#7d4e8a",
  Module: "#2563eb",
  PullRequest: "#0f766e",
  Issue: "#be123c",
  Commit: "#475569",
  Developer: "#9333ea"
};

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/redis/redis-py");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [question, setQuestion] = useState("What kind of SQL is used?");
  const [chat, setChat] = useState<ChatResponse | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [activity, setActivity] = useState<ActivityResponse | null>(null);
  const [pendingRepoUrl, setPendingRepoUrl] = useState<string | null>(null);
  const [loadedRepoUrl, setLoadedRepoUrl] = useState<string | null>(null);
  const [repoInputExpanded, setRepoInputExpanded] = useState(true);
  const [view, setView] = useState<View>("overview");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [graphSearch, setGraphSearch] = useState("");
  const [graphTypes, setGraphTypes] = useState<string[]>(NODE_TYPES);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedTimelineEvent, setSelectedTimelineEvent] = useState<TimelineEvent | null>(null);
  const [highlightedEvidenceIds, setHighlightedEvidenceIds] = useState<string[]>([]);

  const loadRepo = useCallback(async (repoId: string) => {
    const [repoSummary, repoGraph, repoTimeline, repoActivity] = await Promise.all([
      getSummary(repoId),
      getGraph(repoId),
      getTimeline(repoId),
      getActivity(repoId)
    ]);
    setSummary(repoSummary);
    setGraph(repoGraph);
    setTimeline(repoTimeline);
    setActivity(repoActivity);
    setSelectedEvidence(null);
    setSelectedNode(null);
    setSelectedTimelineEvent(null);
    setHighlightedEvidenceIds([]);
    setLoadedRepoUrl(pendingRepoUrl ?? repoUrl);
    setRepoInputExpanded(false);
  }, [pendingRepoUrl, repoUrl]);

  useEffect(() => {
    if (!jobId || status?.status === "ready" || status?.status === "failed") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await getStatus(jobId);
        setStatus(next);
        if (next.status === "ready" && next.repo_id) {
          await loadRepo(next.repo_id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to fetch status");
      }
    }, 1600);
    return () => window.clearInterval(timer);
  }, [jobId, loadRepo, status?.status]);

  async function startAnalysis() {
    setBusy(true);
    setError(null);
    setChat(null);
    try {
      setPendingRepoUrl(repoUrl);
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
      setPendingRepoUrl("demo://github-time-machine");
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
      const answer = await askQuestion(summary.repo_id, nextQuestion);
      setChat(answer);
      setView("ask");
      setSelectedEvidence(answer.evidence[0] ?? null);
      setSelectedNode(null);
      setSelectedTimelineEvent(null);
      setHighlightedEvidenceIds(answer.evidence.map((item) => item.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setBusy(false);
    }
  }

  function askFromInspector(nextQuestion: string) {
    setQuestion(nextQuestion);
    setView("ask");
    void submitQuestion(nextQuestion);
  }

  function selectEvidence(evidence: Evidence) {
    setSelectedEvidence(evidence);
    setSelectedNode(null);
    setSelectedTimelineEvent(null);
    setHighlightedEvidenceIds([evidence.id]);
  }

  function selectNode(node: GraphNode) {
    if (selectedNode?.id === node.id) {
      setSelectedNode(null);
      setSelectedEvidence(null);
      setSelectedTimelineEvent(null);
      setHighlightedEvidenceIds([]);
      return;
    }
    setSelectedNode(node);
    setSelectedEvidence(null);
    setSelectedTimelineEvent(null);
    setHighlightedEvidenceIds(node.data.evidenceIds ?? []);
  }

  function selectTimelineEvent(event: TimelineEvent) {
    setSelectedTimelineEvent(event);
    setSelectedEvidence(event.evidence[0] ?? null);
    setSelectedNode(null);
    setHighlightedEvidenceIds(event.evidence.map((item) => item.id));
  }

  const ready = status?.status === "ready" && summary;
  const currentRepoChanged = Boolean(loadedRepoUrl && repoUrl.trim() !== loadedRepoUrl.trim());
  const showRepoInput = repoInputExpanded || !ready || currentRepoChanged;
  const inspectorMode: InspectorMode = view === "overview" ? "repo" : selectedNode ? "node" : selectedTimelineEvent ? "timeline" : selectedEvidence ? "evidence" : "repo";

  return (
    <main className="min-h-screen">
      <TopAnalysisBar
        repoUrl={repoUrl}
        setRepoUrl={(value) => {
          setRepoUrl(value);
          setRepoInputExpanded(true);
        }}
        loadedRepoUrl={loadedRepoUrl}
        repoInputExpanded={showRepoInput}
        setRepoInputExpanded={setRepoInputExpanded}
        status={status}
        summary={summary}
        busy={busy}
        error={error}
        onAnalyze={startAnalysis}
        onDemo={startDemo}
      />

      {!ready && (
        <section className="mx-auto flex max-w-7xl px-5 py-5">
          <div className="flex min-h-[460px] w-full items-center justify-center rounded-md border border-dashed border-line bg-white/80 p-8 text-center text-ink/65">
            Paste a public GitHub repository URL and start analysis. Use Demo if GitHub is rate-limiting.
          </div>
        </section>
      )}

      {ready && (
        <section className="mx-auto grid max-w-[1800px] grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[76px_minmax(0,1fr)_300px]">
          <NavigationRail view={view} setView={setView} />
          <div className="min-w-0">
            {view === "overview" && (
              <OverviewView
                summary={summary}
                graph={graph}
                activity={activity}
                timeline={timeline}
                onAsk={submitQuestion}
                onView={setView}
                onSelectTimeline={selectTimelineEvent}
              />
            )}
            {view === "ask" && (
              <AskView
                question={question}
                setQuestion={setQuestion}
                busy={busy}
                chat={chat}
                suggestions={summary.suggested_questions}
                timeline={timeline}
                onSubmit={() => submitQuestion()}
                onAsk={submitQuestion}
                onEvidence={selectEvidence}
                onSelectTimeline={selectTimelineEvent}
              />
            )}
            {view === "graph" && (
              <GraphView
                graph={graph}
                search={graphSearch}
                setSearch={setGraphSearch}
                activeTypes={graphTypes}
                setActiveTypes={setGraphTypes}
                highlightedEvidenceIds={highlightedEvidenceIds}
                selectedNodeId={selectedNode?.id ?? null}
                onSelectNode={selectNode}
              />
            )}
            {view === "timeline" && <TimelineView timeline={timeline} selectedEvent={selectedTimelineEvent} onSelectEvent={selectTimelineEvent} />}
            {view === "activity" && <ActivityView activity={activity} />}
          </div>
          <InspectorPanel
            mode={inspectorMode}
            summary={summary}
            evidence={selectedEvidence}
            node={selectedNode}
            timelineEvent={selectedTimelineEvent}
            onAsk={askFromInspector}
            onEvidence={selectEvidence}
          />
        </section>
      )}
    </main>
  );
}

function TopAnalysisBar(props: {
  repoUrl: string;
  setRepoUrl: (value: string) => void;
  loadedRepoUrl: string | null;
  repoInputExpanded: boolean;
  setRepoInputExpanded: (value: boolean) => void;
  status: StatusResponse | null;
  summary: SummaryResponse | null;
  busy: boolean;
  error: string | null;
  onAnalyze: () => void;
  onDemo: () => void;
}) {
  const loaded = props.status?.status === "ready" && props.summary && props.loadedRepoUrl;
  const repoChanged = Boolean(props.loadedRepoUrl && props.repoUrl.trim() !== props.loadedRepoUrl.trim());
  const showAnalyze = !loaded || repoChanged || props.status?.status === "failed";
  const showProgress = props.status && props.status.status !== "ready";

  return (
    <section className="sticky top-0 z-20 border-b border-line bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1800px] flex-col gap-3 px-4 py-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-ink text-white">
                <Network size={20} />
              </div>
              <div className="min-w-0">
                <h1 className="text-2xl font-semibold tracking-normal text-ink">GitHub Time Machine</h1>
                <p className="max-w-[760px] break-words text-sm text-ink/65">
                  {props.summary ? props.summary.name : "Evidence-bound repository historian"}
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {loaded && !props.repoInputExpanded && (
              <div className="inline-flex min-w-0 items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm text-ink/70">
                <ShieldCheck className="shrink-0 text-mint" size={17} />
                <span className="max-w-[360px] truncate">Loaded: {props.loadedRepoUrl}</span>
              </div>
            )}
            {loaded && (
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium text-ink hover:border-mint"
                onClick={() => props.setRepoInputExpanded(!props.repoInputExpanded)}
              >
                <GitBranch size={17} />
                {props.repoInputExpanded ? "Hide repo input" : "Change repo"}
              </button>
            )}
            <div className="hidden items-center gap-2 text-sm text-mint sm:flex">
              <ShieldCheck size={18} />
              Graph evidence first
            </div>
          </div>
        </div>

        {props.repoInputExpanded && (
          <div className="grid gap-3 xl:grid-cols-[1fr_auto_auto]">
            <div className="relative">
              <GitBranch className="absolute left-3 top-3 text-ink/45" size={18} />
              <input
                className="h-11 w-full rounded-md border border-line bg-white pl-10 pr-3 text-sm outline-none ring-mint/30 focus:ring-4"
                value={props.repoUrl}
                onChange={(event) => props.setRepoUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
              />
            </div>
            {showAnalyze ? (
              <button
                className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-ink px-5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
                onClick={props.onAnalyze}
                disabled={props.busy}
              >
                {props.busy ? <Loader2 className="animate-spin" size={18} /> : <Search size={18} />}
                Analyze
              </button>
            ) : (
              <button
                className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium text-ink hover:border-mint"
                onClick={() => props.setRepoInputExpanded(false)}
              >
                Done
              </button>
            )}
            <button
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium text-ink disabled:cursor-not-allowed disabled:opacity-60"
              onClick={props.onDemo}
              disabled={props.busy}
            >
              <Sparkles size={18} />
              Demo
            </button>
          </div>
        )}

        {showProgress && (
          <div className="rounded-md border border-line bg-white p-3">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium capitalize">{props.status?.status}</span>
              <span>{props.status?.progress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-line">
              <div className="h-full bg-mint transition-all" style={{ width: `${props.status?.progress ?? 0}%` }} />
            </div>
            <p className="mt-2 text-sm text-ink/70">{props.status?.message}</p>
          </div>
        )}
        {props.error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{props.error}</div>}
      </div>
    </section>
  );
}

function NavigationRail({ view, setView }: { view: View; setView: (view: View) => void }) {
  const items: Array<{ id: View; label: string; icon: ReactNode }> = [
    { id: "overview", label: "Overview", icon: <Layers3 size={19} /> },
    { id: "ask", label: "Ask", icon: <MessageSquare size={19} /> },
    { id: "graph", label: "Graph", icon: <Network size={19} /> },
    { id: "timeline", label: "Timeline", icon: <History size={19} /> },
    { id: "activity", label: "Activity", icon: <Activity size={19} /> }
  ];
  return (
    <nav className="grid grid-cols-5 gap-2 lg:sticky lg:top-[178px] lg:block lg:h-fit lg:space-y-2">
      {items.map((item) => (
        <button
          key={item.id}
          className={`group flex h-14 items-center justify-center gap-2 rounded-md border text-xs font-medium lg:w-full lg:flex-col ${
            view === item.id ? "border-ink bg-ink text-white" : "border-line bg-white text-ink hover:border-mint"
          }`}
          onClick={() => setView(item.id)}
          title={item.label}
        >
          {item.icon}
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function OverviewView(props: {
  summary: SummaryResponse;
  graph: GraphResponse | null;
  activity: ActivityResponse | null;
  timeline: TimelineResponse | null;
  onAsk: (question: string) => void;
  onView: (view: View) => void;
  onSelectTimeline: (event: TimelineEvent) => void;
}) {
  const nodeCounts = useMemo(() => countGraphTypes(props.graph), [props.graph]);
  const technologies = (props.graph?.nodes ?? []).filter((node) => node.data.type === "Technology").slice(0, 12);
  const modules = (props.graph?.nodes ?? [])
    .filter((node) => node.data.type === "Module")
    .sort((a, b) => Number(b.data.properties?.churn ?? 0) - Number(a.data.properties?.churn ?? 0))
    .slice(0, 6);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <section className="rounded-md border border-line bg-white p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <h2 className="break-words text-xl font-semibold">{props.summary.name}</h2>
              <a className="mt-1 block break-all text-sm text-mint" href={props.summary.url} target="_blank">
                {props.summary.url}
              </a>
            </div>
            <button className="rounded-md border border-line px-3 py-2 text-sm hover:border-mint" onClick={() => props.onView("graph")}>
              Open graph
            </button>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
            {Object.entries(props.summary.metrics).map(([key, value]) => (
              <MetricCard key={key} label={key.replace("_", " ")} value={value} />
            ))}
          </div>
        </section>

        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="text-sm font-semibold uppercase text-ink/60">Suggested questions</h3>
          <div className="mt-3 flex flex-col gap-2">
            {props.summary.suggested_questions.map((item) => (
              <button key={item} className="rounded-md border border-line px-3 py-2 text-left text-sm leading-5 hover:border-mint" onClick={() => props.onAsk(item)}>
                {item}
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-4 flex items-center gap-2 font-semibold">
            <Network size={18} />
            Evidence graph shape
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(nodeCounts).map(([type, count]) => (
              <div key={type} className="rounded-md border border-line p-3">
                <div className="flex items-center gap-2 text-xs text-ink/60">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: TYPE_COLORS[type] ?? "#64748b" }} />
                  <span className="min-w-0 break-words">{type}</span>
                </div>
                <div className="mt-1 text-xl font-semibold">{count}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-4 flex items-center gap-2 font-semibold">
            <Layers3 size={18} />
            Most complex modules
          </h3>
          <ModuleBars modules={modules} />
        </section>

        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-4 flex items-center gap-2 font-semibold">
            <Clock size={18} />
            Active contribution time
          </h3>
          <TopActivity activity={props.activity} />
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-3 font-semibold">Detected technology stack</h3>
          <div className="flex flex-wrap gap-2">
            {technologies.length ? (
              technologies.map((node) => (
                <span key={node.id} className="max-w-full rounded-md border border-line px-3 py-2 text-sm">
                  {node.data.label}
                </span>
              ))
            ) : (
              <p className="text-sm text-ink/60">No technology nodes detected yet.</p>
            )}
          </div>
        </section>
        <section className="rounded-md border border-line bg-white p-5">
          <TimelineStrip timeline={props.timeline} onSelectEvent={props.onSelectTimeline} />
        </section>
      </div>
    </div>
  );
}

function AskView(props: {
  question: string;
  setQuestion: (value: string) => void;
  busy: boolean;
  chat: ChatResponse | null;
  suggestions: string[];
  timeline: TimelineResponse | null;
  onSubmit: () => void;
  onAsk: (question: string) => void;
  onEvidence: (evidence: Evidence) => void;
  onSelectTimeline: (event: TimelineEvent) => void;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section className="rounded-md border border-line bg-white p-5">
        <div className="flex gap-2">
          <input
            className="h-11 flex-1 rounded-md border border-line px-3 text-sm outline-none ring-mint/30 focus:ring-4"
            value={props.question}
            onChange={(event) => props.setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") props.onSubmit();
            }}
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
            <FormattedAnswer answer={props.chat.answer} />
            <div className="mt-5">
              <h3 className="text-sm font-semibold uppercase text-ink/60">Reasoning chain</h3>
              <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-ink/75">
                {props.chat.reasoning_chain.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ol>
            </div>
            <EvidenceList evidence={props.chat.evidence} onEvidence={props.onEvidence} />
          </div>
        ) : (
          <div className="mt-5 rounded-md border border-dashed border-line p-6 text-sm text-ink/60">Ask a repository history question.</div>
        )}
      </section>

      <aside className="space-y-4">
        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="text-sm font-semibold uppercase text-ink/60">Context questions</h3>
          <div className="mt-3 flex flex-col gap-2">
            {props.suggestions.map((item) => (
              <button key={item} className="rounded-md border border-line px-3 py-2 text-left text-sm leading-5 hover:border-mint" onClick={() => props.onAsk(item)}>
                {item}
              </button>
            ))}
          </div>
        </section>
        <section className="rounded-md border border-line bg-white p-5">
          <TimelineStrip timeline={props.timeline} onSelectEvent={props.onSelectTimeline} />
        </section>
      </aside>
    </div>
  );
}

function GraphView(props: {
  graph: GraphResponse | null;
  search: string;
  setSearch: (value: string) => void;
  activeTypes: string[];
  setActiveTypes: (types: string[]) => void;
  highlightedEvidenceIds: string[];
  selectedNodeId: string | null;
  onSelectNode: (node: GraphNode) => void;
}) {
  const filtered = useMemo(() => filterGraph(props.graph, props.search, props.activeTypes, props.highlightedEvidenceIds, props.selectedNodeId), [
    props.graph,
    props.search,
    props.activeTypes,
    props.highlightedEvidenceIds,
    props.selectedNodeId
  ]);
  return (
    <section className="overflow-hidden rounded-md border border-line bg-white">
      <div className="border-b border-line p-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Network size={19} />
              Evidence graph
            </h2>
            <p className="text-sm text-ink/60">Search, filter, and click nodes to inspect the proof path.</p>
          </div>
          <div className="relative min-w-[260px]">
            <Search className="absolute left-3 top-2.5 text-ink/45" size={17} />
            <input
              className="h-10 w-full rounded-md border border-line pl-9 pr-3 text-sm outline-none ring-mint/30 focus:ring-4"
              value={props.search}
              onChange={(event) => props.setSearch(event.target.value)}
              placeholder="Search graph"
            />
          </div>
        </div>
        <GraphLegend activeTypes={props.activeTypes} setActiveTypes={props.setActiveTypes} />
      </div>
      <div className="graph-canvas h-[calc(100vh-230px)] min-h-[780px] bg-black">
        {props.graph ? (
          <ReactFlow
            nodes={filtered.nodes as Node[]}
            edges={filtered.edges as Edge[]}
            fitView
            colorMode="dark"
            onNodeClick={(_, node) => {
              const original = props.graph?.nodes.find((item) => item.id === node.id);
              if (original) props.onSelectNode(original);
            }}
          >
            <Background color="#334155" gap={28} />
            <MiniMap nodeColor={(node) => String((node.data?.color as string) ?? "#64748b")} />
            <Controls />
          </ReactFlow>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-ink/60">No graph loaded.</div>
        )}
      </div>
    </section>
  );
}

function TimelineView({ timeline, selectedEvent, onSelectEvent }: { timeline: TimelineResponse | null; selectedEvent: TimelineEvent | null; onSelectEvent: (event: TimelineEvent) => void }) {
  const [category, setCategory] = useState("All");
  const categories = ["All", ...Array.from(new Set((timeline?.events ?? []).map((event) => event.category).filter((item): item is string => Boolean(item))))];
  const events = (timeline?.events ?? []).filter((event) => category === "All" || event.category === category);
  return (
    <section className="rounded-md border border-line bg-white">
      <div className="border-b border-line p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <History size={18} />
            <h2 className="text-lg font-semibold">Architecture evolution</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {categories.map((item) => (
              <button
                key={item}
                className={`rounded-md border px-2 py-1 text-xs ${category === item ? "border-ink bg-ink text-white" : "border-line bg-white text-ink/70"}`}
                onClick={() => setCategory(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="p-5">
        {events.length ? (
          events.map((event) => (
            <button
              key={`${event.date}-${event.title}`}
              className={`mb-4 grid w-full grid-cols-1 gap-2 border-l-2 pb-4 pl-4 text-left last:mb-0 last:pb-0 sm:grid-cols-[120px_minmax(0,1fr)] sm:gap-4 ${
                selectedEvent?.title === event.title && selectedEvent?.date === event.date ? "border-plum bg-plum/5" : "border-mint"
              }`}
              onClick={() => onSelectEvent(event)}
            >
              <div className="text-xs font-medium text-ink/55">{event.date || "Unknown date"}</div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="min-w-0 break-words font-semibold">{event.title}</h3>
                  {event.category && <span className="rounded-md bg-mint/10 px-2 py-1 text-xs text-mint">{event.category}</span>}
                  {typeof event.confidence === "number" && (
                    <span className="rounded-md bg-amber/10 px-2 py-1 text-xs text-amber">{Math.round(event.confidence * 100)}%</span>
                  )}
                </div>
                <p className="mt-1 text-sm leading-6 text-ink/70">{event.summary}</p>
                {event.evidence.length > 0 && <div className="mt-2 text-xs text-ink/50">{event.evidence.length} evidence item{event.evidence.length === 1 ? "" : "s"}</div>}
              </div>
            </button>
          ))
        ) : (
          <div className="rounded-md border border-dashed border-line p-6 text-sm text-ink/60">No architecture timeline events detected yet.</div>
        )}
      </div>
    </section>
  );
}

function ActivityView({ activity }: { activity: ActivityResponse | null }) {
  const maxHour = Math.max(1, ...((activity?.by_hour ?? []).map((item) => item.count)));
  const topDate = activity?.top_dates[0];
  const topContributor = activity?.by_contributor[0];
  return (
    <div className="space-y-4">
      <section className="rounded-md border border-line bg-white p-5">
        <div className="flex flex-col gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Activity size={19} />
              Commit activity
            </h2>
            <p className="text-sm text-ink/60">Contribution rhythm from the analyzed commit graph.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ActivityStat label="Analyzed commits" value={activity?.total_commits ?? 0} />
            <ActivityStat label="Active dates" value={activity?.active_days ?? activity?.by_date.length ?? 0} />
            <ActivityStat label="Busiest date" value={topDate ? topDate.date : "No date"} detail={topDate ? `${topDate.count} commits` : undefined} />
            <ActivityStat label="Top contributor" value={topContributor ? topContributor.name : "Unknown"} detail={topContributor ? `${topContributor.count} commits` : undefined} />
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-4 flex items-center gap-2 font-semibold">
            <BarChart3 size={18} />
            Most active dates
          </h3>
          {activity?.top_dates.length ? (
            <DateActivityBars dates={activity.top_dates} />
          ) : (
            <EmptyState text="No commit date data available yet." />
          )}
        </section>

        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-4 flex items-center gap-2 font-semibold">
            <UserRound size={18} />
            Contributor breakdown
          </h3>
          <ContributorBars activity={activity} />
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-4 flex items-center gap-2 font-semibold">
            <Clock size={18} />
            Hour of day
          </h3>
          {activity?.has_hour_data ? <HourActivityBars hours={activity.by_hour} maxHour={maxHour} /> : <EmptyState text="This analysis has commit dates, but not precise commit times. Re-analyze the repo to collect hour-level activity." />}
        </section>

        <section className="rounded-md border border-line bg-white p-5">
          <h3 className="mb-4 flex items-center gap-2 font-semibold">
            <Clock size={18} />
            Active windows
          </h3>
          <TimeWindows activity={activity} />
        </section>
      </div>
    </div>
  );
}

function ActivityStat({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <div className="rounded-md border border-line bg-paper/40 p-3">
      <div className="text-xs uppercase text-ink/55">{label}</div>
      <div className="mt-1 truncate text-lg font-semibold" title={String(value)}>
        {value}
      </div>
      {detail && <div className="mt-1 text-xs text-ink/55">{detail}</div>}
    </div>
  );
}

function DateActivityBars({ dates }: { dates: ActivityResponse["top_dates"] }) {
  const max = Math.max(1, ...dates.map((item) => item.count));
  return (
    <div className="space-y-3">
      {dates.map((item) => (
        <div key={item.date}>
          <div className="mb-1 flex items-start justify-between gap-3 text-sm">
            <span className="font-medium">{item.date}</span>
            <span className="shrink-0 text-ink/55">{item.count} commits</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-line">
            <div className="h-full rounded-full bg-mint" style={{ width: `${Math.max(6, (item.count / max) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function HourActivityBars({ hours, maxHour }: { hours: ActivityResponse["by_hour"]; maxHour: number }) {
  const activeHours = hours.filter((item) => item.count > 0);
  if (!activeHours.length) return <EmptyState text="No hour-level commit activity was detected." />;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
      {activeHours.map((item) => (
        <div key={item.hour} className="rounded-md border border-line p-3">
          <div className="mb-2 flex items-center justify-between gap-2 text-sm">
            <span className="font-medium">{String(item.hour).padStart(2, "0")}:00</span>
            <span className="shrink-0 text-ink/55">{item.count}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-line">
            <div className="h-full rounded-full bg-plum" style={{ width: `${Math.max(8, (item.count / maxHour) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function InspectorPanel(props: {
  mode: InspectorMode;
  summary: SummaryResponse;
  evidence: Evidence | null;
  node: GraphNode | null;
  timelineEvent: TimelineEvent | null;
  onAsk: (question: string) => void;
  onEvidence: (evidence: Evidence) => void;
}) {
  return (
    <aside className="lg:sticky lg:top-[178px] lg:h-[calc(100vh-194px)]">
      <div className="h-full overflow-auto rounded-md border border-line bg-white p-5">
        <h2 className="text-sm font-semibold uppercase text-ink/60">Inspector</h2>

        {props.mode === "node" && props.node && (
          <div className="mt-4">
            <div className="mb-3 inline-flex rounded-md px-2 py-1 text-xs font-medium text-white" style={{ background: props.node.data.color ?? "#64748b" }}>
              {props.node.data.type ?? "Node"}
            </div>
            <h3 className="text-lg font-semibold">{props.node.data.label}</h3>
            <p className="mt-2 text-sm leading-6 text-ink/70">{props.node.data.summary}</p>
            <PropertyList properties={props.node.data.properties} />
            <button className="mt-4 w-full rounded-md border border-line px-3 py-2 text-sm hover:border-mint" onClick={() => props.onAsk(`Explain ${props.node?.data.label}`)}>
              Ask about this
            </button>
          </div>
        )}

        {props.mode === "timeline" && props.timelineEvent && (
          <div className="mt-4">
            <div className="text-xs font-medium text-ink/55">{props.timelineEvent.date || "Unknown date"}</div>
            <h3 className="mt-1 text-lg font-semibold">{props.timelineEvent.title}</h3>
            <p className="mt-2 text-sm leading-6 text-ink/70">{props.timelineEvent.summary}</p>
            <EvidenceList evidence={props.timelineEvent.evidence} onEvidence={props.onEvidence} compact />
          </div>
        )}

        {props.mode === "evidence" && props.evidence && (
          <div className="mt-4">
            <div className="mb-3 inline-flex rounded-md bg-plum/10 px-2 py-1 text-xs font-medium text-plum">{props.evidence.source_type}</div>
            <h3 className="text-lg font-semibold">{props.evidence.title}</h3>
            <p className="mt-2 text-sm leading-6 text-ink/70">{props.evidence.snippet}</p>
            {props.evidence.url && (
              <a className="mt-4 block rounded-md border border-line px-3 py-2 text-center text-sm text-mint hover:border-mint" href={props.evidence.url} target="_blank">
                Open source
              </a>
            )}
          </div>
        )}

        {props.mode === "repo" && (
          <div className="mt-4">
            <h3 className="text-lg font-semibold">{props.summary.name}</h3>
            <p className="mt-2 text-sm leading-6 text-ink/70">Select a chat citation, timeline event, or graph node to inspect evidence and ask focused follow-up questions.</p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {Object.entries(props.summary.metrics).map(([key, value]) => (
                <MetricCard key={key} label={key.replace("_", " ")} value={value} compact />
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function GraphLegend({ activeTypes, setActiveTypes }: { activeTypes: string[]; setActiveTypes: (types: string[]) => void }) {
  function toggle(type: string) {
    setActiveTypes(activeTypes.includes(type) ? activeTypes.filter((item) => item !== type) : [...activeTypes, type]);
  }
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {NODE_TYPES.map((type) => (
        <button
          key={type}
          className={`inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs ${activeTypes.includes(type) ? "border-line bg-white" : "border-line bg-line/40 text-ink/45"}`}
          onClick={() => toggle(type)}
        >
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: TYPE_COLORS[type] }} />
          {type}
        </button>
      ))}
    </div>
  );
}

function FormattedAnswer({ answer }: { answer: string }) {
  const sections = formatAnswerSections(answer);
  return (
    <div className="space-y-3">
      {sections.map((section, index) => {
        if (section.kind === "reason") {
          return (
            <div key={`${section.kind}-${index}`} className="rounded-md border border-amber/30 bg-amber/10 p-4">
              <div className="mb-1 text-xs font-semibold uppercase text-amber">Most likely reason</div>
              <p className="text-sm leading-6 text-ink/80">{section.text}</p>
            </div>
          );
        }
        if (section.kind === "list") {
          return (
            <ul key={`${section.kind}-${index}`} className="space-y-2 rounded-md border border-line bg-paper/40 p-4 text-sm leading-6 text-ink/80">
              {section.items.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-mint" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={`${section.kind}-${index}`} className={`text-base leading-7 ${index === 0 ? "font-medium text-ink" : "text-ink/78"}`}>
            {section.text}
          </p>
        );
      })}
    </div>
  );
}

function formatAnswerSections(answer: string): Array<{ kind: "paragraph"; text: string } | { kind: "reason"; text: string } | { kind: "list"; items: string[] }> {
  const normalized = answer.replace(/\r/g, "").trim();
  if (!normalized) return [{ kind: "paragraph", text: "No answer was returned." }];

  const reasonMatch = normalized.match(/Most likely reason:\s*/i);
  const beforeReason = reasonMatch ? normalized.slice(0, reasonMatch.index).trim() : normalized;
  const reason = reasonMatch ? normalized.slice((reasonMatch.index ?? 0) + reasonMatch[0].length).trim() : "";
  const sections: Array<{ kind: "paragraph"; text: string } | { kind: "reason"; text: string } | { kind: "list"; items: string[] }> = [];

  for (const block of splitAnswerBlocks(beforeReason)) {
    if (looksLikeList(block)) {
      sections.push({ kind: "list", items: splitListItems(block) });
    } else {
      sections.push(...splitReadableParagraphs(block).map((text) => ({ kind: "paragraph" as const, text })));
    }
  }

  if (reason) {
    sections.push({ kind: "reason", text: trimTrailingPeriod(reason) });
  }
  return sections.length ? sections : [{ kind: "paragraph", text: normalized }];
}

function splitAnswerBlocks(text: string) {
  return text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
}

function looksLikeList(text: string) {
  return /\n\s*(?:[-*]|\d+\.)\s+/.test(text) || text.includes("; ");
}

function splitListItems(text: string) {
  const lineItems = text
    .split("\n")
    .map((line) => line.replace(/^\s*(?:[-*]|\d+\.)\s+/, "").trim())
    .filter(Boolean);
  if (lineItems.length > 1) return lineItems;
  return text
    .split(";")
    .map((item) => trimTrailingPeriod(item.trim()))
    .filter(Boolean);
}

function splitReadableParagraphs(text: string) {
  const cleaned = text.trim();
  if (cleaned.length < 260) return [cleaned];
  return cleaned
    .split(/(?<=\.)\s+(?=[A-Z])/)
    .reduce<string[]>((paragraphs, sentence) => {
      const current = paragraphs[paragraphs.length - 1] ?? "";
      if (!current || current.length + sentence.length > 260) {
        paragraphs.push(sentence);
      } else {
        paragraphs[paragraphs.length - 1] = `${current} ${sentence}`;
      }
      return paragraphs;
    }, []);
}

function trimTrailingPeriod(text: string) {
  return text.replace(/\s+/g, " ").replace(/\.$/, "");
}

function EvidenceList({ evidence, onEvidence, compact = false }: { evidence: Evidence[]; onEvidence: (evidence: Evidence) => void; compact?: boolean }) {
  if (!evidence.length) return <div className="mt-4 rounded-md border border-dashed border-line p-4 text-sm text-ink/60">No evidence attached.</div>;
  return (
    <div className={`${compact ? "mt-4" : "mt-6"} space-y-3`}>
      <h3 className="text-sm font-semibold uppercase text-ink/60">Evidence</h3>
      {evidence.map((item) => (
        <button key={item.id} className="block w-full rounded-md border border-line p-3 text-left hover:border-mint" onClick={() => onEvidence(item)}>
          <div className="text-xs uppercase text-plum">{item.source_type}</div>
          <div className="mt-1 text-sm font-medium">{item.title}</div>
          <p className="mt-2 max-h-20 overflow-hidden text-xs leading-5 text-ink/65">{item.snippet}</p>
        </button>
      ))}
    </div>
  );
}

function TimelineStrip({ timeline, onSelectEvent }: { timeline: TimelineResponse | null; onSelectEvent: (event: TimelineEvent) => void }) {
  const events = (timeline?.events ?? []).slice(0, 4);
  return (
    <div>
      <h3 className="mb-3 flex items-center gap-2 font-semibold">
        <History size={18} />
        Recent architecture events
      </h3>
      {events.length ? (
        <div className="space-y-2">
          {events.map((event) => (
            <button key={`${event.date}-${event.title}`} className="w-full rounded-md border border-line px-3 py-2 text-left hover:border-mint" onClick={() => onSelectEvent(event)}>
              <div className="text-xs text-ink/50">{event.date || "Unknown date"}</div>
              <div className="mt-1 text-sm font-medium">{event.title}</div>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-sm text-ink/60">No timeline events detected yet.</p>
      )}
    </div>
  );
}

function MetricCard({ label, value, compact = false }: { label: string; value: number; compact?: boolean }) {
  return (
    <div className="rounded-md border border-line p-3">
      <div className={`${compact ? "text-lg" : "text-2xl"} font-semibold`}>{value}</div>
      <div className="mt-1 text-xs uppercase text-ink/55">{label}</div>
    </div>
  );
}

function ModuleBars({ modules }: { modules: GraphNode[] }) {
  const max = Math.max(1, ...modules.map((node) => Number(node.data.properties?.churn ?? 0)));
  if (!modules.length) return <EmptyState text="No module churn metrics available yet." />;
  return (
    <div className="space-y-3">
      {modules.map((node) => {
        const churn = Number(node.data.properties?.churn ?? 0);
        return (
          <div key={node.id}>
            <div className="mb-1 flex items-start justify-between gap-3 text-sm">
              <span className="min-w-0 break-words">{node.data.label}</span>
              <span className="shrink-0 text-ink/55">{churn}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-line">
              <div className="h-full bg-plum" style={{ width: `${Math.max(8, (churn / max) * 100)}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TopActivity({ activity }: { activity: ActivityResponse | null }) {
  const topDates = activity?.top_dates ?? [];
  const activeWindows = (activity?.top_time_windows ?? []).filter((item) => item.count > 0);
  if (!topDates.length && !activeWindows.length) return <EmptyState text="No commit timestamp data available yet." />;
  return (
    <div className="space-y-4">
      <div>
        <div className="mb-2 text-xs font-semibold uppercase text-ink/55">Top dates</div>
        <div className="space-y-2">
          {topDates.slice(0, 4).map((item) => (
            <div key={item.date} className="flex items-start justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm">
              <span className="min-w-0 break-words">{item.date}</span>
              <span className="shrink-0 font-semibold">{item.count}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold uppercase text-ink/55">Time windows</div>
        <div className="space-y-2">
          {activeWindows.slice(0, 4).map((item) => (
            <div key={item.label} className="flex items-start justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm">
              <span className="min-w-0 break-words">{item.label}</span>
              <span className="shrink-0 font-semibold">{item.count}</span>
            </div>
          ))}
          {!activeWindows.length && <div className="rounded-md border border-dashed border-line p-3 text-sm text-ink/60">No hourly commit timestamps available.</div>}
        </div>
      </div>
    </div>
  );
}

function TimeWindows({ activity }: { activity: ActivityResponse | null }) {
  const activeWindows = (activity?.top_time_windows ?? []).filter((item) => item.count > 0);
  if (!activity?.has_hour_data) return <EmptyState text="Precise commit times were not available for this analysis, so active time windows cannot be ranked." />;
  if (!activeWindows.length) return <EmptyState text="No active time windows were detected." />;
  return (
    <div className="space-y-2">
      {activeWindows.slice(0, 6).map((item) => (
        <div key={item.label} className="flex items-start justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm">
          <span className="min-w-0 break-words">{item.label}</span>
          <span className="shrink-0 font-semibold">{item.count}</span>
        </div>
      ))}
    </div>
  );
}

function ContributorBars({ activity }: { activity: ActivityResponse | null }) {
  const contributors = activity?.by_contributor ?? [];
  const max = Math.max(1, ...contributors.map((item) => item.count));
  if (!contributors.length) return <EmptyState text="No contributor activity available yet." />;
  return (
    <div className="space-y-3">
      {contributors.map((item) => (
        <div key={item.name}>
          <div className="mb-1 flex items-start justify-between gap-3 text-sm">
            <span className="min-w-0 break-words">{item.name}</span>
            <span className="shrink-0 text-ink/55">{item.count}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-line">
            <div className="h-full bg-amber" style={{ width: `${Math.max(8, (item.count / max) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function PropertyList({ properties }: { properties?: Record<string, unknown> }) {
  const entries = Object.entries(properties ?? {}).slice(0, 8);
  if (!entries.length) return null;
  return (
    <dl className="mt-4 space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border border-line p-2">
          <dt className="text-[11px] uppercase text-ink/50">{key.replace("_", " ")}</dt>
          <dd className="mt-1 break-words text-sm">{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-line p-4 text-sm text-ink/60">{text}</div>;
}

function countGraphTypes(graph: GraphResponse | null) {
  const counts: Record<string, number> = {};
  for (const node of graph?.nodes ?? []) {
    const type = node.data.type ?? "Unknown";
    counts[type] = (counts[type] ?? 0) + 1;
  }
  return counts;
}

function filterGraph(graph: GraphResponse | null, search: string, activeTypes: string[], highlightedEvidenceIds: string[], selectedNodeId: string | null) {
  if (!graph) return { nodes: [], edges: [] };
  const lower = search.trim().toLowerCase();
  const highlighted = new Set(highlightedEvidenceIds);
  const activeNodes = graph.nodes.filter((node) => activeTypes.includes(node.data.type ?? ""));
  const activeNodeIds = new Set(activeNodes.map((node) => node.id));
  const visibleEdges = graph.edges.filter((edge) => activeNodeIds.has(edge.source) && activeNodeIds.has(edge.target));
  const matchedNodeIds = new Set(
    activeNodes
      .filter((node) => lower && `${node.data.label} ${node.data.type} ${node.data.summary}`.toLowerCase().includes(lower))
      .map((node) => node.id)
  );
  const seedNodeIds = new Set<string>();
  if (selectedNodeId && activeNodeIds.has(selectedNodeId)) seedNodeIds.add(selectedNodeId);
  for (const id of matchedNodeIds) seedNodeIds.add(id);

  const neighborNodeIds = new Set<string>(seedNodeIds);
  const focusEdgeIds = new Set<string>();
  if (seedNodeIds.size) {
    for (const edge of visibleEdges) {
      if (seedNodeIds.has(edge.source) || seedNodeIds.has(edge.target)) {
        neighborNodeIds.add(edge.source);
        neighborNodeIds.add(edge.target);
        focusEdgeIds.add(edge.id);
      }
    }
  }
  if (highlighted.size) {
    for (const node of activeNodes) {
      if ((node.data.evidenceIds ?? []).some((id) => highlighted.has(id))) {
        neighborNodeIds.add(node.id);
      }
    }
  }
  const hasFocus = seedNodeIds.size > 0 || highlighted.size > 0;
  const nodes = graph.nodes
    .filter((node) => activeTypes.includes(node.data.type ?? ""))
    .map((node) => {
      const hasEvidenceHighlight = (node.data.evidenceIds ?? []).some((id) => highlighted.has(id));
      const selected = node.id === selectedNodeId;
      const matched = matchedNodeIds.has(node.id);
      const inNeighborhood = neighborNodeIds.has(node.id);
      return {
        ...node,
        style: {
          ...node.style,
          opacity: hasFocus && !inNeighborhood && !hasEvidenceHighlight ? 0.18 : 1,
          boxShadow:
            selected || matched
              ? "0 0 0 5px rgba(47, 143, 131, 0.24)"
              : hasEvidenceHighlight || inNeighborhood
                ? "0 0 0 3px rgba(125, 78, 138, 0.16)"
                : "none",
          zIndex: selected || matched ? 10 : inNeighborhood ? 5 : 1
        }
      };
    });
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = visibleEdges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => {
      const focused = focusEdgeIds.has(edge.id) || (neighborNodeIds.has(edge.source) && neighborNodeIds.has(edge.target) && hasFocus);
      return {
        ...edge,
        animated: edge.animated || focused,
        style: {
          ...edge.style,
          opacity: hasFocus && !focused ? 0.12 : 1,
          strokeWidth: focused ? 3 : edge.style?.strokeWidth ?? 1.5,
          stroke: focused ? "#2f8f83" : edge.style?.stroke ?? "#94a3b8"
        }
      };
    });
  return { nodes, edges };
}
