from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


JobStatus = Literal["queued", "cloning", "fetching", "analyzing", "ready", "failed"]


class AnalyzeRequest(BaseModel):
    repo_url: str = Field(min_length=3, max_length=500)


class AnalyzeResponse(BaseModel):
    job_id: str


class StatusResponse(BaseModel):
    job_id: str
    repo_id: Optional[str] = None
    status: JobStatus
    progress: int
    message: str


class ChatRequest(BaseModel):
    repo_id: str
    question: str = Field(min_length=3, max_length=1000)


class Evidence(BaseModel):
    id: str
    source_type: str
    source_id: str
    title: str
    url: Optional[str] = None
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    reasoning_chain: List[str]
    evidence: List[Evidence]
    confidence: float


class GraphResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class TimelineEvent(BaseModel):
    date: str
    title: str
    summary: str
    evidence: List[Evidence]
    category: Optional[str] = None
    confidence: Optional[float] = None


class TimelineResponse(BaseModel):
    events: List[TimelineEvent]


class ActivityByDate(BaseModel):
    date: str
    count: int


class ActivityByHour(BaseModel):
    hour: int
    count: int


class ActivityTimeWindow(BaseModel):
    label: str
    start_hour: int
    end_hour: int
    count: int


class ActivityContributor(BaseModel):
    name: str
    count: int


class ActivityResponse(BaseModel):
    total_commits: int
    active_days: int
    has_hour_data: bool
    commits_with_hour: int
    by_date: List[ActivityByDate]
    by_hour: List[ActivityByHour]
    top_dates: List[ActivityByDate]
    top_time_windows: List[ActivityTimeWindow]
    by_contributor: List[ActivityContributor]


class SummaryResponse(BaseModel):
    repo_id: str
    name: str
    url: str
    metrics: Dict[str, int]
    suggested_questions: List[str]
