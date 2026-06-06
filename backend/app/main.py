from __future__ import annotations

from typing import Dict
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .analyzer import build_repo_graph, build_seed_graph, clone_or_refresh
from .config import get_settings
from .graph import react_flow_graph
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ChatRequest,
    ChatResponse,
    GraphResponse,
    StatusResponse,
    SummaryResponse,
    TimelineResponse,
)
from .reasoning import answer_question, timeline_events
from .repository_url import parse_github_url
from .storage import Store


settings = get_settings()
store = Store(settings.database_path)
app = FastAPI(title="GitHub Time Machine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/repo/analyze", response_model=AnalyzeResponse)
def analyze_repo(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    job_id = str(uuid4())
    store.create_job(job_id, str(request.repo_url))
    background_tasks.add_task(run_analysis, job_id, str(request.repo_url))
    return AnalyzeResponse(job_id=job_id)


@app.get("/repo/{job_id}/status", response_model=StatusResponse)
def repo_status(job_id: str) -> StatusResponse:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["job_id"] = job.pop("id")
    return StatusResponse(**job)


@app.get("/repo/{repo_id}/summary", response_model=SummaryResponse)
def repo_summary(repo_id: str) -> SummaryResponse:
    repo = store.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return SummaryResponse(
        repo_id=repo["id"],
        name=repo["name"],
        url=repo["url"],
        metrics=repo["metrics"],
        suggested_questions=[
            "Why was Redis introduced?",
            "Who knows authentication best?",
            "Which modules are most complex?",
            "What architectural changes happened over time?",
        ],
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not store.get_repository(request.repo_id):
        raise HTTPException(status_code=404, detail="Repository not found")
    return answer_question(store, request.repo_id, request.question, settings.openai_api_key, settings.openai_model)


@app.get("/graph", response_model=GraphResponse)
def graph(repo_id: str) -> GraphResponse:
    if not store.get_repository(repo_id):
        raise HTTPException(status_code=404, detail="Repository not found")
    return GraphResponse(**react_flow_graph(store, repo_id))


@app.get("/timeline", response_model=TimelineResponse)
def timeline(repo_id: str) -> TimelineResponse:
    if not store.get_repository(repo_id):
        raise HTTPException(status_code=404, detail="Repository not found")
    return TimelineResponse(events=timeline_events(store, repo_id))


def run_analysis(job_id: str, repo_url: str) -> None:
    try:
        if repo_url in {"demo", "seed", "demo://github-time-machine"}:
            repo_id = "demo__time-machine"
            store.update_job(job_id, "analyzing", 60, "Loading seeded demo evidence graph", repo_id)
            build_seed_graph(store, repo_id)
            store.update_job(job_id, "ready", 100, "Seeded demo analysis complete", repo_id)
            return
        slug = parse_github_url(repo_url)
        repo_id = slug.full_name.replace("/", "__")
        store.update_job(job_id, "cloning", 10, "Cloning repository", repo_id)
        repo = clone_or_refresh(slug, repo_url, settings.repos_dir)
        store.update_job(job_id, "fetching", 35, "Fetching commits, pull requests, and issues", repo_id)
        store.update_job(job_id, "analyzing", 60, "Building evidence graph", repo_id)
        build_repo_graph(
            store=store,
            repo_id=repo_id,
            slug=slug,
            repo_url=repo_url,
            repo=repo,
            github_token=settings.github_token,
            max_commits=settings.max_commits,
            github_fetch_limit=settings.github_fetch_limit,
        )
        store.update_job(job_id, "ready", 100, "Analysis complete", repo_id)
    except Exception as exc:
        store.update_job(job_id, "failed", 100, f"Analysis failed: {exc}")
