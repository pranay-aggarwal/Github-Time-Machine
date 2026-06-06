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


class SummaryResponse(BaseModel):
    repo_id: str
    name: str
    url: str
    metrics: Dict[str, int]
    suggested_questions: List[str]
