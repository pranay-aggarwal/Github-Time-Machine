# GitHub Time Machine - MVP Spec

## Vision

GitHub shows what changed. GitHub Time Machine reconstructs why it changed.

Given one public GitHub repository, the system ingests commits, pull requests, issues, developers, modules, technologies, and architecture decisions into an evidence-first knowledge graph. Users can ask questions such as:

- Why was Redis introduced?
- Who knows authentication best?
- Why is this module complex?
- What architectural changes happened over time?
- Which issue led to this feature?

Answers must include explanation, reasoning chain, evidence, and confidence.

## MVP Scope

- Public GitHub repositories only.
- One repository per analysis job.
- Default branch only.
- Bounded commit history with `MAX_COMMITS`.
- Closed PRs and issues first.
- SQLite graph tables plus NetworkX-compatible graph export.
- OpenAI Responses API with configurable `OPENAI_MODEL`.

Out of scope for MVP:

- Slack, Jira, Kubernetes, enterprise auth, private repos, multi-repo analysis.

## Core Flow

1. User enters a GitHub repository URL.
2. Backend creates an analysis job.
3. System clones or refreshes the repository.
4. System fetches commits, PRs, and issues.
5. System builds graph nodes, edges, and evidence.
6. User asks questions in chat.
7. Answers cite commits, PRs, issues, and graph evidence.

## Tech Stack

Frontend:

- Next.js 15
- TypeScript
- Tailwind CSS
- React Flow
- lucide-react

Backend:

- FastAPI
- Python 3.12
- SQLite
- NetworkX-compatible graph export
- GitPython
- PyGithub
- OpenAI Responses API

Deployment:

- Docker
- Docker Compose

## Data Schemas

### RepositoryData

```json
{
  "repo_id": "owner__repo",
  "name": "owner/repo",
  "url": "https://github.com/owner/repo",
  "default_branch": "main",
  "metrics": {
    "commits": 0,
    "contributors": 0,
    "issues": 0,
    "pull_requests": 0,
    "modules": 0,
    "technologies": 0
  }
}
```

### CommitInsight

```json
{
  "commit_id": "",
  "summary": "",
  "intent": "",
  "modules": [],
  "impact": "",
  "evidence_ids": []
}
```

### PRInsight

```json
{
  "pull_request_id": "",
  "problem": "",
  "solution": "",
  "tradeoffs": "",
  "outcome": "",
  "evidence_ids": []
}
```

### IssueInsight

```json
{
  "issue_id": "",
  "issue_summary": "",
  "root_cause": "",
  "module": "",
  "evidence_ids": []
}
```

### Graph Export

```json
{
  "nodes": [
    {
      "id": "technology:redis",
      "type": "default",
      "position": { "x": 0, "y": 0 },
      "data": { "label": "Technology: Redis" }
    }
  ],
  "edges": [
    {
      "id": "edge:commit:technology",
      "source": "commit:abc123",
      "target": "technology:redis",
      "label": "INTRODUCED"
    }
  ]
}
```

## Knowledge Graph

Node types:

- Repository
- Commit
- PullRequest
- Issue
- Developer
- Module
- Technology
- ArchitectureDecision

Relationships:

- AUTHOR_OF
- INTRODUCED
- MODIFIED
- RESOLVES
- DISCUSSES
- AFFECTS
- USES
- DEPENDS_ON
- SUPPORTED_BY

Example evidence path:

Issue -> resolved_by -> PullRequest -> implemented_by -> Commit -> affects -> Module -> introduced -> Technology

## API

### POST `/repo/analyze`

Input:

```json
{ "repo_url": "https://github.com/owner/repo" }
```

Output:

```json
{ "job_id": "" }
```

### GET `/repo/{job_id}/status`

Output:

```json
{
  "job_id": "",
  "repo_id": "owner__repo",
  "status": "queued | cloning | fetching | analyzing | ready | failed",
  "progress": 0,
  "message": ""
}
```

### POST `/chat`

Input:

```json
{
  "repo_id": "owner__repo",
  "question": "Why was Redis introduced?"
}
```

Output:

```json
{
  "answer": "",
  "reasoning_chain": [],
  "evidence": [],
  "confidence": 0.72
}
```

### GET `/graph?repo_id=owner__repo`

Returns React Flow-compatible graph JSON.

### GET `/timeline?repo_id=owner__repo`

Returns architecture events with evidence.

## Success Criteria

A judge can paste a public GitHub repository URL and ask, "Why was Redis added?"

The system should produce:

1. A coherent explanation.
2. Supporting commits.
3. Supporting PRs.
4. Supporting issues when available.
5. Visual graph evidence.
