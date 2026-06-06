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

