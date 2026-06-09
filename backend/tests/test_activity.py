from pathlib import Path

from app.activity import commit_activity
from app.analyzer import build_seed_graph
from app.graph import react_flow_graph
from app.storage import Store


def test_activity_groups_commits_by_date_hour_and_contributor(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__activity"
    store.upsert_repository(repo_id, "demo/activity", "https://github.com/demo/activity", "main", {})
    store.add_node(repo_id, "commit:1", "Commit", "abc1234", {"authored_at": "2024-01-01T10:30:00+00:00"})
    store.add_node(repo_id, "commit:2", "Commit", "def5678", {"authored_at": "2024-01-01T11:45:00+00:00"})
    store.add_node(repo_id, "commit:3", "Commit", "ghi9012", {"authored_at": "2024-01-02T20:00:00+00:00"})
    store.add_node(repo_id, "developer:ava", "Developer", "Ava", {})
    store.add_node(repo_id, "developer:noah", "Developer", "Noah", {})
    store.add_edge(repo_id, "edge:ava:1", "developer:ava", "commit:1", "AUTHOR_OF")
    store.add_edge(repo_id, "edge:ava:2", "developer:ava", "commit:2", "AUTHOR_OF")
    store.add_edge(repo_id, "edge:noah:3", "developer:noah", "commit:3", "AUTHOR_OF")

    activity = commit_activity(store, repo_id)

    assert activity["total_commits"] == 3
    assert activity["active_days"] == 2
    assert activity["has_hour_data"] is True
    assert activity["commits_with_hour"] == 3
    assert activity["top_dates"][0] == {"date": "2024-01-01", "count": 2}
    assert activity["by_hour"][10]["count"] == 1
    assert activity["by_hour"][11]["count"] == 1
    assert activity["top_time_windows"][0]["label"] == "10:00-12:00"
    assert activity["by_contributor"][0] == {"name": "Ava", "count": 2}


def test_activity_empty_repo_returns_safe_arrays(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__empty"
    store.upsert_repository(repo_id, "demo/empty", "https://github.com/demo/empty", "main", {})

    activity = commit_activity(store, repo_id)

    assert activity["total_commits"] == 0
    assert activity["active_days"] == 0
    assert activity["has_hour_data"] is False
    assert activity["by_date"] == []
    assert len(activity["by_hour"]) == 24
    assert all(item["count"] == 0 for item in activity["by_hour"])


def test_activity_date_only_commits_do_not_fake_midnight_windows(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__date_only"
    store.upsert_repository(repo_id, "demo/date-only", "https://github.com/demo/date-only", "main", {})
    store.add_node(repo_id, "commit:1", "Commit", "abc1234", {"date": "2024-01-01"})
    store.add_node(repo_id, "commit:2", "Commit", "def5678", {"date": "2024-01-01"})

    activity = commit_activity(store, repo_id)

    assert activity["total_commits"] == 2
    assert activity["active_days"] == 1
    assert activity["top_dates"] == [{"date": "2024-01-01", "count": 2}]
    assert activity["has_hour_data"] is False
    assert activity["commits_with_hour"] == 0
    assert activity["top_time_windows"] == []
    assert all(item["count"] == 0 for item in activity["by_hour"])


def test_graph_export_includes_readable_metadata(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    graph = react_flow_graph(store, "demo__time-machine")
    node = graph["nodes"][0]
    edge = graph["edges"][0]

    assert "type" in node["data"]
    assert "summary" in node["data"]
    assert "evidenceCount" in node["data"]
    assert "relationship" in edge["data"]
