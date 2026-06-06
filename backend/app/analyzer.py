from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
import hashlib
import json
import re
import shutil
import stat
import time
from typing import Iterable

from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError
from github import Github
from github.GithubException import GithubException, RateLimitExceededException

from .repository_url import RepoSlug
from .storage import Store


TECH_PATTERNS = {
    "Redis": [r"\bredis\b", r"\bioredis\b", r"\bcelery\[redis\]\b"],
    "Kafka": [r"\bkafka\b", r"\bconfluent\b"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b", r"\bpsycopg\b"],
    "MySQL": [r"\bmysql\b", r"\bpymysql\b"],
    "MongoDB": [r"\bmongo(?:db)?\b", r"\bpymongo\b"],
    "Docker": [r"\bdocker\b", r"\bdockerfile\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Next.js": [r"\bnext\b", r"\bnextjs\b"],
    "React": [r"\breact\b"],
    "Tailwind": [r"\btailwind\b"],
    "Flask": [r"\bflask\b"],
    "Django": [r"\bdjango\b"],
    "SQLAlchemy": [r"\bsqlalchemy\b"],
    "SQLite": [r"\bsqlite\b", r"\.sqlite\b", r"\.db\b"],
    "Vue": [r"\bvue\b", r"\b@vitejs/plugin-vue\b"],
    "Vite": [r"\bvite\b"],
    "TypeScript": [r"\btypescript\b", r"\btsconfig\b"],
    "JavaScript": [r"\bjavascript\b"],
    "Python": [r"\bpython\b", r"\.py\b"],
    "Node.js": [r"\bnode\b", r"\bnodejs\b"],
    "Bootstrap": [r"\bbootstrap\b"],
    "Jinja": [r"\bjinja\b", r"\bjinja2\b"],
    "Celery": [r"\bcelery\b"],
    "Firebase": [r"\bfirebase\b"],
    "Supabase": [r"\bsupabase\b"],
    "Prisma": [r"\bprisma\b"],
}

PACKAGE_TECH_MAP = {
    "flask": "Flask",
    "flask-login": "Flask-Login",
    "flask-sqlalchemy": "SQLAlchemy",
    "sqlalchemy": "SQLAlchemy",
    "django": "Django",
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "pydantic": "Pydantic",
    "redis": "Redis",
    "celery": "Celery",
    "psycopg": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "mysqlclient": "MySQL",
    "pymysql": "MySQL",
    "pymongo": "MongoDB",
    "sqlite3": "SQLite",
    "react": "React",
    "next": "Next.js",
    "vue": "Vue",
    "@vitejs/plugin-vue": "Vite",
    "vite": "Vite",
    "typescript": "TypeScript",
    "tailwindcss": "Tailwind",
    "bootstrap": "Bootstrap",
    "firebase": "Firebase",
    "supabase": "Supabase",
    "prisma": "Prisma",
    "express": "Express",
}

DEPENDENCY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "Dockerfile",
    "docker-compose.yml",
}

PROFILE_FILES = {
    "README.md",
    "README.rst",
    "README.txt",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
}


@dataclass
class CommitRecord:
    sha: str
    short_sha: str
    message: str
    author: str
    authored_date: str
    files: list[str]
    stats: dict[str, int]


def stable_id(*parts: str) -> str:
    return hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:16]


def module_id(repo_id: str, module: str) -> str:
    return f"module:{stable_id(repo_id, module)}"


def technology_id(repo_id: str, technology: str) -> str:
    return f"technology:{stable_id(repo_id, technology)}"


def developer_id(repo_id: str, developer: str) -> str:
    return f"developer:{stable_id(repo_id, developer)}"


def clone_or_refresh(slug: RepoSlug, repo_url: str, repos_dir: Path) -> Repo:
    target = repos_dir / slug.owner / slug.name
    if target.exists():
        repo = None
        try:
            repo = Repo(target)
            remote = get_fetch_remote(repo)
            remote.fetch(prune=True)
            return repo
        except (ValueError, InvalidGitRepositoryError, NoSuchPathError):
            close_repo(repo)
            target = repair_or_alternate_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        try:
            remove_tree(target)
        except PermissionError:
            target = alternate_clone_target(target)
    return Repo.clone_from(repo_url, target)


def get_fetch_remote(repo: Repo):
    try:
        return repo.remote("origin")
    except Exception:
        remotes = list(repo.remotes)
        if not remotes:
            raise ValueError("Repository has no configured git remotes.")
        return remotes[0]


def close_repo(repo: Repo | None) -> None:
    if repo is None:
        return
    try:
        repo.close()
    except Exception:
        pass


def remove_tree(path: Path) -> None:
    last_error: Exception | None = None
    for _ in range(5):
        try:
            shutil.rmtree(path, onerror=make_writable_and_retry)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.4)
    if last_error:
        raise last_error


def make_writable_and_retry(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def repair_or_alternate_target(target: Path) -> Path:
    try:
        remove_tree(target)
        return target
    except Exception:
        return alternate_clone_target(target)


def alternate_clone_target(target: Path) -> Path:
    suffix = stable_id(str(target), str(time.time()))
    return target.with_name(f"{target.name}-{suffix}")


def infer_module(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return "root"
    if parts[0] in {"src", "app", "packages", "services"} and len(parts) > 1:
        return parts[1]
    if parts[0] in {"backend", "frontend", "api", "web", "server", "client"}:
        return parts[0]
    if len(parts) == 1:
        return "root"
    return parts[0]


def extract_terms(question: str) -> list[str]:
    stop = {
        "why", "was", "were", "the", "this", "that", "added", "introduced", "who",
        "what", "which", "how", "best", "knows", "most", "module", "complex",
        "contributed", "to", "is", "are", "a", "an", "of", "for", "in",
    }
    terms = re.findall(r"[A-Za-z][A-Za-z0-9_.-]{2,}", question.lower())
    return [term for term in terms if term not in stop]


def resolve_analysis_ref(repo: Repo) -> tuple[str | None, str | None]:
    try:
        branch = repo.active_branch.name
        return branch, branch
    except Exception:
        pass

    try:
        symbolic = repo.git.symbolic_ref("refs/remotes/origin/HEAD")
        branch = symbolic.rsplit("/", 1)[-1]
        return f"origin/{branch}", branch
    except Exception:
        pass

    remote_refs = [ref for ref in repo.refs if ref.path.startswith("refs/remotes/origin/") and not ref.path.endswith("/HEAD")]
    if remote_refs:
        ref_name = remote_refs[0].name
        branch = ref_name.rsplit("/", 1)[-1]
        return ref_name, branch

    return None, None


def collect_commits(repo: Repo, max_commits: int, rev: str | None = None) -> list[CommitRecord]:
    records: list[CommitRecord] = []
    for commit in repo.iter_commits(rev=rev, max_count=max_commits):
        files = list(commit.stats.files.keys())
        records.append(
            CommitRecord(
                sha=commit.hexsha,
                short_sha=commit.hexsha[:7],
                message=commit.message.strip(),
                author=commit.author.name or commit.author.email or "Unknown",
                authored_date=commit.authored_datetime.date().isoformat(),
                files=files,
                stats={
                    "files": len(files),
                    "insertions": commit.stats.total.get("insertions", 0),
                    "deletions": commit.stats.total.get("deletions", 0),
                    "lines": commit.stats.total.get("lines", 0),
                },
            )
        )
    return records


def detect_technologies(text: str) -> list[str]:
    found: set[str] = set()
    lowered = text.lower()
    for tech, patterns in TECH_PATTERNS.items():
        if any(re.search(pattern, lowered, re.I) for pattern in patterns):
            found.add(tech)
    for package in extract_package_names(text):
        mapped = PACKAGE_TECH_MAP.get(package.lower())
        if mapped:
            found.add(mapped)
    return sorted(found)


def detect_technologies_from_profile(profile: dict[str, str]) -> list[str]:
    found: set[str] = set()
    for file_name, text in profile.items():
        found.update(detect_technologies(f"{file_name}\n{text}"))
        for package in extract_manifest_packages(file_name, text):
            found.add(PACKAGE_TECH_MAP.get(package.lower(), normalize_package_name(package)))
    return sorted(found)


def extract_manifest_packages(file_name: str, text: str) -> set[str]:
    lowered_name = file_name.lower()
    if lowered_name == "package.json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return set()
        packages = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            packages.update((data.get(section) or {}).keys())
        return packages
    if lowered_name in {"requirements.txt", "pyproject.toml"}:
        return extract_package_names(text)
    return set()


def extract_package_names(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        cleaned = line.strip().strip('"').strip("'")
        if not cleaned or cleaned.startswith(("#", "//")):
            continue
        match = re.match(r"([A-Za-z0-9_.@/-]+)", cleaned)
        if match:
            name = match.group(1).split("[", 1)[0].lower()
            if name not in {"from", "import", "version", "scripts"}:
                names.add(name)
    return names


def normalize_package_name(package: str) -> str:
    cleaned = package.split("/")[-1] if package.startswith("@") else package
    return cleaned.replace("-", " ").replace("_", " ").title().replace(" ", "")


def read_repo_profile(repo_path: Path) -> dict[str, str]:
    profile: dict[str, str] = {}
    for name in PROFILE_FILES:
        path = repo_path / name
        if path.exists() and path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if text:
                profile[name] = text[:5000]
    return profile


def first_readme_summary(profile: dict[str, str]) -> str:
    for name in ("README.md", "README.rst", "README.txt"):
        text = profile.get(name)
        if text:
            lines = [line.strip("# ").strip() for line in text.splitlines() if line.strip()]
            return " ".join(lines[:5])[:800]
    return ""


def build_repo_graph(
    store: Store,
    repo_id: str,
    slug: RepoSlug,
    repo_url: str,
    repo: Repo,
    github_token: str | None,
    max_commits: int,
    github_fetch_limit: int,
) -> None:
    store.clear_repo_graph(repo_id)
    analysis_ref, branch = resolve_analysis_ref(repo)
    commits = collect_commits(repo, max_commits, analysis_ref)
    contributors = Counter(commit.author for commit in commits)
    module_churn: dict[str, int] = defaultdict(int)
    module_commits: dict[str, set[str]] = defaultdict(set)
    tech_first_commit: dict[str, CommitRecord] = {}

    metrics = {
        "commits": len(commits),
        "contributors": len(contributors),
        "issues": 0,
        "pull_requests": 0,
        "modules": 0,
        "technologies": 0,
    }
    store.upsert_repository(repo_id, slug.full_name, repo_url, branch, metrics)
    store.add_node(repo_id, f"repo:{repo_id}", "Repository", slug.full_name, {"url": repo_url})
    profile = read_repo_profile(Path(repo.working_tree_dir or ""))
    profile_summary = first_readme_summary(profile)
    if profile:
        store.add_node(
            repo_id,
            f"profile:{repo_id}",
            "ProjectProfile",
            "Project profile",
            {
                "summary": profile_summary,
                "files": sorted(profile.keys()),
            },
        )
        store.add_edge(repo_id, f"edge:repo:{repo_id}:profile", f"repo:{repo_id}", f"profile:{repo_id}", "DESCRIBES")
    if profile_summary:
        store.add_evidence(
            repo_id,
            f"evidence:profile:{repo_id}:readme",
            "project_profile",
            repo_id,
            "Repository README summary",
            profile_summary,
            repo_url,
        )
    profile_technologies = detect_technologies_from_profile(profile)
    for file_name, text in profile.items():
        if file_name.startswith("README"):
            continue
        store.add_evidence(
            repo_id,
            f"evidence:profile:{repo_id}:{stable_id(file_name)}",
            "project_profile",
            repo_id,
            f"Project file: {file_name}",
            text[:1200],
            repo_url,
        )
    for tech in profile_technologies:
        tech_node = technology_id(repo_id, tech)
        store.add_node(repo_id, tech_node, "Technology", tech, {})
        store.add_edge(repo_id, f"edge:profile:{repo_id}:technology:{stable_id(repo_id, tech)}", f"profile:{repo_id}", tech_node, "USES")

    for commit in commits:
        commit_node = f"commit:{commit.sha}"
        store.add_node(
            repo_id,
            commit_node,
            "Commit",
            commit.short_sha,
            {"message": commit.message, "date": commit.authored_date, **commit.stats},
        )
        store.add_evidence(
            repo_id,
            f"evidence:commit:{commit.sha}",
            "commit",
            commit.sha,
            f"Commit {commit.short_sha}",
            commit.message,
            f"{repo_url.rstrip('/')}/commit/{commit.sha}",
        )

        developer_node = developer_id(repo_id, commit.author)
        store.add_node(repo_id, developer_node, "Developer", commit.author, {"commits": contributors[commit.author]})
        store.add_edge(repo_id, f"edge:{developer_node}:{commit_node}", developer_node, commit_node, "AUTHOR_OF")

        commit_text = " ".join([commit.message, *commit.files])
        for file_path in commit.files:
            module = infer_module(file_path)
            module_churn[module] += 1
            module_commits[module].add(commit.sha)
            module_node = module_id(repo_id, module)
            store.add_node(repo_id, module_node, "Module", module, {"path": module})
            store.add_edge(repo_id, f"edge:{commit_node}:{module_node}", commit_node, module_node, "AFFECTS")

            if Path(file_path).name in DEPENDENCY_FILES or file_path in DEPENDENCY_FILES:
                commit_text += f" dependency-manifest {file_path}"

        for tech in detect_technologies(commit_text):
            tech_node = technology_id(repo_id, tech)
            store.add_node(repo_id, tech_node, "Technology", tech, {})
            store.add_edge(repo_id, f"edge:{commit_node}:{tech_node}", commit_node, tech_node, "INTRODUCED")
            tech_first_commit.setdefault(tech, commit)

    for module, count in module_churn.items():
        module_node = module_id(repo_id, module)
        store.add_node(repo_id, module_node, "Module", module, {"churn": count, "commits": len(module_commits[module])})

    for tech, commit in tech_first_commit.items():
        decision_id = f"decision:{stable_id(repo_id, tech)}"
        store.add_node(
            repo_id,
            decision_id,
            "ArchitectureDecision",
            f"{tech} introduced",
            {"date": commit.authored_date, "summary": f"{tech} appears in commit evidence."},
        )
        store.add_edge(repo_id, f"edge:{decision_id}:technology:{stable_id(repo_id, tech)}", decision_id, technology_id(repo_id, tech), "USES")
        store.add_edge(repo_id, f"edge:{decision_id}:commit:{commit.sha}", decision_id, f"commit:{commit.sha}", "SUPPORTED_BY")
        store.add_evidence(
            repo_id,
            f"evidence:decision:{stable_id(repo_id, tech)}",
            "architecture_decision",
            decision_id,
            f"{tech} introduced",
            f"{tech} was detected from commit {commit.short_sha}: {commit.message}",
            f"{repo_url.rstrip('/')}/commit/{commit.sha}",
        )

    issue_count, pr_count = fetch_github_context(store, repo_id, slug, repo_url, github_token, github_fetch_limit)
    metrics.update(
        {
            "issues": issue_count,
            "pull_requests": pr_count,
            "modules": len(module_churn),
            "technologies": len(set(tech_first_commit) | set(profile_technologies)),
        }
    )
    store.upsert_repository(repo_id, slug.full_name, repo_url, branch, metrics)


def build_seed_graph(store: Store, repo_id: str = "demo__time-machine") -> None:
    repo_url = "https://github.com/demo/time-machine"
    store.clear_repo_graph(repo_id)
    store.upsert_repository(
        repo_id,
        "demo/time-machine",
        repo_url,
        "main",
        {"commits": 6, "contributors": 4, "issues": 2, "pull_requests": 2, "modules": 4, "technologies": 3},
    )
    store.add_node(repo_id, f"repo:{repo_id}", "Repository", "demo/time-machine", {"url": repo_url})
    store.add_node(
        repo_id,
        f"profile:{repo_id}",
        "ProjectProfile",
        "Project profile",
        {
            "summary": "GitHub Time Machine is an evidence-first repository historian that analyzes commits, issues, pull requests, modules, technologies, and architecture changes.",
            "files": ["README.md", "package.json", "requirements.txt"],
        },
    )
    store.add_edge(repo_id, f"edge:repo:{repo_id}:profile", f"repo:{repo_id}", f"profile:{repo_id}", "DESCRIBES")
    store.add_evidence(
        repo_id,
        f"evidence:profile:{repo_id}:readme",
        "project_profile",
        repo_id,
        "Repository README summary",
        "GitHub Time Machine is an evidence-first repository historian that analyzes commits, issues, pull requests, modules, technologies, and architecture changes.",
        repo_url,
    )

    fixtures = [
        ("a1b2c3d", "2024-02-18", "Mira Shah", "Add Redis-backed cache for repository analysis jobs", "backend", "Redis", "14", "21"),
        ("b2c3d4e", "2024-03-04", "Noah Kim", "Move graph traversal into NetworkX service", "graph", "NetworkX", "18", "27"),
        ("c3d4e5f", "2024-03-16", "Ava Patel", "Add React Flow evidence explorer", "frontend", "React", "22", "33"),
    ]

    for commit, date, author, message, module, tech, issue, pr in fixtures:
        commit_node = f"commit:{commit}"
        module_node = module_id(repo_id, module)
        tech_node = technology_id(repo_id, tech)
        developer_node = developer_id(repo_id, author)
        issue_node = f"issue:{issue}"
        pr_node = f"pr:{pr}"
        decision_node = f"decision:{stable_id(repo_id, tech)}"

        store.add_node(repo_id, commit_node, "Commit", commit, {"message": message, "date": date})
        store.add_node(repo_id, module_node, "Module", module, {"churn": 12})
        store.add_node(repo_id, tech_node, "Technology", tech, {})
        store.add_node(repo_id, developer_node, "Developer", author, {"commits": 2})
        store.add_node(repo_id, issue_node, "Issue", f"Issue #{issue}: Scaling bottleneck", {"number": issue})
        store.add_node(repo_id, pr_node, "PullRequest", f"PR #{pr}: {message}", {"number": pr, "merged": True})
        store.add_node(repo_id, decision_node, "ArchitectureDecision", f"{tech} introduced", {"date": date, "summary": message})

        store.add_edge(repo_id, f"edge:{developer_node}:{commit_node}", developer_node, commit_node, "AUTHOR_OF")
        store.add_edge(repo_id, f"edge:{issue_node}:{pr_node}", issue_node, pr_node, "RESOLVES")
        store.add_edge(repo_id, f"edge:{pr_node}:{commit_node}", pr_node, commit_node, "IMPLEMENTED_BY")
        store.add_edge(repo_id, f"edge:{commit_node}:{module_node}", commit_node, module_node, "AFFECTS")
        store.add_edge(repo_id, f"edge:{commit_node}:{tech_node}", commit_node, tech_node, "INTRODUCED")
        store.add_edge(repo_id, f"edge:{decision_node}:{commit_node}", decision_node, commit_node, "SUPPORTED_BY")
        store.add_edge(repo_id, f"edge:{decision_node}:{tech_node}", decision_node, tech_node, "USES")

        store.add_evidence(repo_id, f"evidence:commit:{commit}", "commit", commit, f"Commit {commit}", message, f"{repo_url}/commit/{commit}")
        store.add_evidence(
            repo_id,
            f"evidence:pr:{pr}",
            "pull_request",
            pr,
            f"PR #{pr}",
            f"{message} after issue #{issue} showed analysis jobs were repeatedly recomputing expensive results.",
            f"{repo_url}/pull/{pr}",
        )
        store.add_evidence(
            repo_id,
            f"evidence:issue:{issue}",
            "issue",
            issue,
            f"Issue #{issue}",
            f"Users reported slow repeated repository analysis in the {module} module.",
            f"{repo_url}/issues/{issue}",
        )


def fetch_github_context(
    store: Store,
    repo_id: str,
    slug: RepoSlug,
    repo_url: str,
    github_token: str | None,
    limit: int,
) -> tuple[int, int]:
    try:
        gh = Github(github_token) if github_token else Github()
        gh_repo = gh.get_repo(slug.full_name)
    except (GithubException, RateLimitExceededException, Exception):
        return 0, 0

    pr_count = 0
    issue_count = 0
    try:
        for index, pr in enumerate(gh_repo.get_pulls(state="closed", sort="updated", direction="desc")):
            if index >= limit:
                break
            pr_count += 1
            pr_node = f"pr:{pr.number}"
            body = pr.body or ""
            snippet = f"{pr.title}\n{body}"[:2000]
            store.add_node(repo_id, pr_node, "PullRequest", f"PR #{pr.number}: {pr.title}", {"number": pr.number, "merged": bool(pr.merged)})
            store.add_evidence(repo_id, f"evidence:pr:{pr.number}", "pull_request", str(pr.number), pr.title, snippet, pr.html_url)
            for tech in detect_technologies(snippet):
                store.add_edge(repo_id, f"edge:{pr_node}:technology:{stable_id(repo_id, tech)}", pr_node, technology_id(repo_id, tech), "DISCUSSES")
            for issue_number in extract_issue_refs(snippet):
                issue_node = f"issue:{issue_number}"
                store.add_edge(repo_id, f"edge:{issue_node}:{pr_node}", issue_node, pr_node, "RESOLVES")
    except (GithubException, RateLimitExceededException, Exception):
        pass

    try:
        for index, issue in enumerate(gh_repo.get_issues(state="closed", sort="updated", direction="desc")):
            if index >= limit:
                break
            if issue.pull_request:
                continue
            issue_count += 1
            issue_node = f"issue:{issue.number}"
            body = issue.body or ""
            snippet = f"{issue.title}\n{body}"[:2000]
            store.add_node(repo_id, issue_node, "Issue", f"Issue #{issue.number}: {issue.title}", {"number": issue.number})
            store.add_evidence(repo_id, f"evidence:issue:{issue.number}", "issue", str(issue.number), issue.title, snippet, issue.html_url)
            for tech in detect_technologies(snippet):
                store.add_edge(repo_id, f"edge:{issue_node}:technology:{stable_id(repo_id, tech)}", issue_node, technology_id(repo_id, tech), "DISCUSSES")
    except (GithubException, RateLimitExceededException, Exception):
        pass

    return issue_count, pr_count


def extract_issue_refs(text: str) -> Iterable[str]:
    for match in re.finditer(r"(?:fixes|closes|resolves)?\s*#(\d+)", text, re.I):
        yield match.group(1)
