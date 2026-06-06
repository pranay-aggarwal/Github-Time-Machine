# GitHub Time Machine

Evidence-first AI historian for public GitHub repositories.

The MVP ingests one public repository, builds a SQLite-backed knowledge graph of commits, PRs, issues, developers, modules, technologies, and architecture decisions, then answers questions only from cited evidence.

## Quick Start

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Optional environment variables:

```powershell
$env:GITHUB_TOKEN="..."
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="gpt-5.1"
$env:MAX_COMMITS="500"
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## MVP Scope

- Public GitHub repositories only.
- One repository per analysis job.
- Default branch and bounded commit history.
- Closed PRs and issues first.
- SQLite persistence with NetworkX graph traversal.
- Responses include explanation, reasoning chain, evidence, and confidence.

## API

- `POST /repo/analyze`
- `GET /repo/{job_id}/status`
- `GET /repo/{repo_id}/summary`
- `POST /chat`
- `GET /graph?repo_id=...`
- `GET /timeline?repo_id=...`


## Product Description

An AI-powered repository historian. Instead of only showing *what changed* like GitHub does, it tries to reconstruct *why things changed* by analyzing commits, PRs, issues, modules, technologies, developers, and architecture evolution.

Implemented as multiple logical “agents” rather than separate running processes:

1. **Repository Ingestion Agent** : clones/fetches the repo and reads commits/files.
2. **Repository Profile Agent** : reads README and manifest files to understand the project and tech stack.
3. **Commit/Module Analysis Agent** : maps commits to modules, churn, contributors, and technologies.
4. **GitHub Context Agent** : fetches PRs/issues when GitHub API allows it.
5. **Knowledge Graph Agent** : builds nodes/edges for commits, modules, technologies, developers, PRs, issues, decisions.
6. **Reasoning/Chat Agent** : answers questions using graph + evidence.
7. **Timeline Agent** : builds architecture/technology/module evolution events.

By ingesting a GitHub repository and building an evidence-backed knowledge graph from commits, pull requests, issues, modules, developers, and technologies, it enables users to ask questions such as "Why was this technology introduced?", "Who knows this module best?", or "Which parts of the codebase are most complex?". 

Every answer is grounded in repository evidence rather than AI speculation. The platform also generates architecture evolution timelines and complexity heatmaps, helping developers understand the history, rationale, and evolution of a project through a single conversational interface.
