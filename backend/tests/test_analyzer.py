from app.analyzer import (
    detect_technologies,
    detect_technologies_from_profile,
    developer_id,
    extract_issue_refs,
    first_readme_summary,
    infer_module,
    module_id,
    read_repo_profile,
    resolve_analysis_ref,
    technology_id,
)
from app.reasoning import confidence_from_evidence


def test_infer_module_from_common_paths():
    assert infer_module("src/auth/login.py") == "auth"
    assert infer_module("backend/app/main.py") == "backend"
    assert infer_module("README.md") == "root"


def test_detect_technology_from_text():
    assert "Redis" in detect_technologies("Add redis cache client and Docker config")
    assert "Kafka" in detect_technologies("Switch events to kafka topic")
    assert "Flask" in detect_technologies("Flask==3.0.0")
    assert "SQLAlchemy" in detect_technologies("Flask-SQLAlchemy==3.1.1")


def test_read_repo_profile_extracts_readme_and_manifest(tmp_path):
    (tmp_path / "README.md").write_text("# Parking App\n\nA Flask parking lot management app.", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("Flask\nSQLAlchemy\n", encoding="utf-8")

    profile = read_repo_profile(tmp_path)

    assert "README.md" in profile
    assert "requirements.txt" in profile
    assert first_readme_summary(profile).startswith("Parking App")


def test_detect_technologies_from_manifests():
    profile = {
        "requirements.txt": "Flask==3.0.0\nFlask-SQLAlchemy==3.1.1\npymysql==1.1.0\n",
        "package.json": '{"dependencies":{"@vitejs/plugin-vue":"latest","vue":"^3.0.0","tailwindcss":"latest"}}',
    }

    tech = detect_technologies_from_profile(profile)

    assert "Flask" in tech
    assert "SQLAlchemy" in tech
    assert "MySQL" in tech
    assert "Vue" in tech
    assert "Vite" in tech
    assert "Tailwind" in tech


def test_graph_entity_ids_are_repo_scoped():
    assert module_id("repo_a", "root") != module_id("repo_b", "root")
    assert technology_id("repo_a", "SQLite") != technology_id("repo_b", "SQLite")
    assert developer_id("repo_a", "Pranay") != developer_id("repo_b", "Pranay")


def test_extract_issue_refs():
    assert list(extract_issue_refs("Fixes #12 and closes #34")) == ["12", "34"]


def test_confidence_scoring():
    assert confidence_from_evidence(0) < confidence_from_evidence(1)
    assert confidence_from_evidence(3) < confidence_from_evidence(5)


def test_existing_repo_fetch_uses_prune_keyword(monkeypatch, tmp_path):
    from app import analyzer

    target = tmp_path / "owner" / "repo"
    target.mkdir(parents=True)
    calls = []

    class FakeOrigin:
        def fetch(self, **kwargs):
            calls.append(kwargs)

    class FakeRepo:
        remotes = [FakeOrigin()]

        def remote(self, name):
            assert name == "origin"
            raise AttributeError("origin")

    monkeypatch.setattr(analyzer, "Repo", lambda path: FakeRepo())

    slug = type("Slug", (), {"owner": "owner", "name": "repo"})()
    analyzer.clone_or_refresh(slug, "https://github.com/owner/repo", tmp_path)

    assert calls == [{"prune": True}]


def test_existing_repo_without_remote_is_recloned(monkeypatch, tmp_path):
    from app import analyzer

    target = tmp_path / "owner" / "repo"
    target.mkdir(parents=True)
    cloned = []

    class FakeRepoFactory:
        def __call__(self, path):
            return self

        @staticmethod
        def clone_from(repo_url, clone_target):
            cloned.append((repo_url, clone_target))
            return "new-repo"

        remotes = []

        def remote(self, name):
            raise ValueError("Repository has no configured git remotes.")

    monkeypatch.setattr(analyzer, "Repo", FakeRepoFactory())

    slug = type("Slug", (), {"owner": "owner", "name": "repo"})()
    result = analyzer.clone_or_refresh(slug, "https://github.com/owner/repo", tmp_path)

    assert result == "new-repo"
    assert cloned == [("https://github.com/owner/repo", target)]


def test_locked_broken_repo_clones_to_alternate_target(monkeypatch, tmp_path):
    from app import analyzer
    from git.exc import InvalidGitRepositoryError

    target = tmp_path / "owner" / "repo"
    target.mkdir(parents=True)
    cloned = []

    class FakeRepoFactory:
        def __call__(self, path):
            raise InvalidGitRepositoryError(str(path))

        @staticmethod
        def clone_from(repo_url, clone_target):
            cloned.append((repo_url, clone_target))
            return "fresh-repo"

    monkeypatch.setattr(analyzer, "Repo", FakeRepoFactory())
    monkeypatch.setattr(analyzer, "remove_tree", lambda path: (_ for _ in ()).throw(PermissionError(str(path))))
    monkeypatch.setattr(analyzer, "alternate_clone_target", lambda path: path.with_name("repo-fresh"))

    slug = type("Slug", (), {"owner": "owner", "name": "repo"})()
    result = analyzer.clone_or_refresh(slug, "https://github.com/owner/repo", tmp_path)

    assert result == "fresh-repo"
    assert cloned == [("https://github.com/owner/repo", tmp_path / "owner" / "repo-fresh")]


def test_github_context_failure_returns_zero_counts(monkeypatch, tmp_path):
    from app import analyzer
    from app.storage import Store

    class FakeGithub:
        def __init__(self, token=None):
            pass

        def get_repo(self, full_name):
            raise RuntimeError("rate limit exceeded")

    monkeypatch.setattr(analyzer, "Github", FakeGithub)
    store = Store(tmp_path / "db.sqlite3")
    slug = type("Slug", (), {"full_name": "owner/repo"})()

    assert analyzer.fetch_github_context(store, "repo", slug, "https://github.com/owner/repo", None, 10) == (0, 0)


def test_resolve_analysis_ref_uses_origin_head_when_active_branch_missing():
    class FakeGit:
        def symbolic_ref(self, ref):
            assert ref == "refs/remotes/origin/HEAD"
            return "refs/remotes/origin/main"

    class FakeRepo:
        git = FakeGit()

        @property
        def active_branch(self):
            raise TypeError("Reference at 'refs/heads/master' does not exist")

    assert resolve_analysis_ref(FakeRepo()) == ("origin/main", "main")
