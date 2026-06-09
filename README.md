# GitHub Time Machine

GitHub Time Machine is an evidence-first AI historian for public GitHub repositories.

Paste a GitHub repo URL, let the app analyze its commits and metadata, then ask questions like:

- What does this project do?
- Why was Redis introduced?
- Who are the contributors?
- Who knows the authentication module best?
- Which modules are most complex?
- What changed architecturally over time?

The app builds a SQLite-backed knowledge graph of commits, modules, technologies, developers, pull requests, issues, and architecture decisions. Chat answers are grounded in that graph and returned with reasoning, confidence, and evidence.

## Current Features

- Public GitHub repository analysis.
- Commit, module, contributor, technology, and architecture graph extraction.
- Evidence-backed chat with cleaner formatted answers.
- Repo-understanding chat context using README/profile, modules, technologies, contributors, and decisions.
- Interactive React Flow graph:
  - dark canvas
  - type-colored nodes
  - node search and filters
  - selected-node neighborhood highlighting
  - search-result neighborhood highlighting
  - click selected node again to deselect
- Timeline view for architecture, technology, and module activity.
- Activity view:
  - most active dates
  - active contribution windows when commit timestamps are available
  - contributor breakdown
  - date-only fallback without fake time-window data
- Compact command-center UI with Overview, Ask, Graph, Timeline, and Activity views.

## Tech Stack

Backend:

- FastAPI
- SQLite
- NetworkX
- GitPython
- PyGithub
- OpenAI Responses API

Frontend:

- Next.js
- React
- Tailwind CSS
- React Flow
- Lucide icons

## Clean Local Setup

These commands assume you are in:

```text
C:\Users\Pranay\Desktop\AI time machine
```

### 1. Backend

PowerShell:

```powershell
cd "C:\Users\Pranay\Desktop\AI time machine\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env`:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.1
GITHUB_TOKEN=your_github_token_optional
MAX_COMMITS=500
GITHUB_FETCH_LIMIT=100
```

Run backend:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8080 --reload
```

Git Bash:

```bash
cd "/c/Users/Pranay/Desktop/AI time machine/backend"
./.venv/Scripts/uvicorn.exe app.main:app --host 127.0.0.1 --port 8080 --reload
```

Health check:

```text
http://127.0.0.1:8080/health
```

Expected response:

```json
{ "status": "ok" }
```

### 2. Frontend

PowerShell:

```powershell
cd "C:\Users\Pranay\Desktop\AI time machine\frontend"
npm install
npm run dev
```

Git Bash:

```bash
cd "/c/Users/Pranay/Desktop/AI time machine/frontend"
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

If the backend is running on another port, start frontend with:

PowerShell:

```powershell
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8080"
npm run dev
```

Git Bash:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8080 npm run dev
```

## Docker Setup

From the project root:

```bash
docker compose up --build
```

Then open:

```text
http://127.0.0.1:3000
```

The compose file exposes:

- Backend: `http://127.0.0.1:8080`
- Frontend: `http://127.0.0.1:3000`

Environment variables can be passed from your shell:

```bash
OPENAI_API_KEY=your_key GITHUB_TOKEN=your_token docker compose up --build
```

## GitHub Token

`GITHUB_TOKEN` is optional but recommended.

Without it, public repo cloning still works, but GitHub API calls for PRs/issues can hit rate limits quickly. A token improves access to:

- closed pull requests
- closed issues
- issue/PR metadata
- richer evidence linking

For public repositories, the token does not need private repo access.

## OpenAI Key

`OPENAI_API_KEY` is optional but recommended for natural chat answers.

Without it, the app uses deterministic graph-based fallback answers. Those are evidence-safe but less conversational.

With it, chat receives a repo-understanding snapshot and can answer more naturally while still using graph/evidence constraints.

## API Endpoints

- `POST /repo/analyze`
- `GET /repo/{job_id}/status`
- `GET /repo/{repo_id}/summary`
- `POST /chat`
- `GET /graph?repo_id=...`
- `GET /timeline?repo_id=...`
- `GET /activity?repo_id=...`
- `GET /health`

## Data Model

The backend stores graph-like records in SQLite:

- `repositories`
- `analysis_jobs`
- `nodes`
- `edges`
- `evidence`

Important node types:

- `Repository`
- `ProjectProfile`
- `Commit`
- `Developer`
- `Module`
- `Technology`
- `PullRequest`
- `Issue`
- `ArchitectureDecision`

Important edge types:

- `AUTHOR_OF`
- `AFFECTS`
- `INTRODUCED`
- `USES`
- `SUPPORTED_BY`
- `RESOLVES`
- `IMPLEMENTED_BY`
- `DISCUSSES`

## Testing

Backend tests:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests
```

Frontend build check:

```powershell
cd frontend
npm run build
```

## Troubleshooting

### Frontend says `failed to fetch`

Check backend:

```text
http://127.0.0.1:8080/health
```

The frontend expects the backend on `8080` by default.

### Backend port 8080 is blocked

Find the process using port `8080`:

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen | Select-Object OwningProcess
```

Stop that process:

```powershell
Stop-Process -Id <OwningProcess> -Force
```

Then start the backend again on `8080`.

### Next.js returns missing chunk errors

Clear the frontend build cache:

PowerShell:

```powershell
cd "C:\Users\Pranay\Desktop\AI time machine\frontend"
Remove-Item -Recurse -Force .next
npm run dev
```

Git Bash:

```bash
cd "/c/Users/Pranay/Desktop/AI time machine/frontend"
rm -rf .next
npm run dev
```

### Re-analyze after backend changes

If the backend was restarted and the frontend is holding an old job/repo state, click **Change repo** and analyze the repo again.

## Hackathon Pitch Notes

GitHub Time Machine is not a generic repo chatbot. It is an evidence-first software history engine.

The key idea: turn a repository into a graph of evidence, then answer questions by traversing that graph.

Strong pitch points:

- It explains why a project changed, not just what changed.
- It links commits, modules, technologies, developers, PRs, and issues.
- It gives confidence and evidence instead of unsupported AI guesses.
- The graph view makes the reasoning path visual and inspectable.
- The timeline and activity panels help teams understand project evolution quickly.

Logical agents used by the system:

1. Repository ingestion agent
2. Repository profile agent
3. Commit/module analysis agent
4. GitHub context agent
5. Knowledge graph agent
6. Reasoning/chat agent
7. Timeline/activity agent
