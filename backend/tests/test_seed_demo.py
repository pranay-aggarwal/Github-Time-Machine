from pathlib import Path

from app.analyzer import build_seed_graph
from app.graph import react_flow_graph
from app.reasoning import answer_question, timeline_events
from app.storage import Store


def test_seed_graph_supports_demo_question(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    answer = answer_question(store, "demo__time-machine", "Why was Redis introduced?", None, "test-model")
    graph = react_flow_graph(store, "demo__time-machine")
    timeline = timeline_events(store, "demo__time-machine")

    assert "redis" in answer.answer.lower()
    assert answer.evidence
    assert answer.confidence > 0
    assert graph["nodes"]
    assert graph["edges"]
    assert any(event["title"] == "Redis introduced" for event in timeline)


def test_technology_question_uses_graph_nodes(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__sql"
    store.upsert_repository(repo_id, "demo/sql", "https://github.com/demo/sql", "main", {})
    store.add_node(repo_id, "technology:postgres", "Technology", "PostgreSQL", {})
    store.add_node(repo_id, "technology:mysql", "Technology", "MySQL", {})
    store.add_evidence(repo_id, "evidence:postgres", "architecture_decision", "postgres", "PostgreSQL introduced", "Added PostgreSQL for relational storage.")
    store.add_evidence(repo_id, "evidence:mysql", "architecture_decision", "mysql", "MySQL introduced", "Added MySQL compatibility.")

    answer = answer_question(store, repo_id, "what kind of sql is used", None, "test-model")

    assert "PostgreSQL" in answer.answer
    assert "MySQL" in answer.answer
    assert "kind, sql, used" not in answer.answer
    assert answer.evidence


def test_technology_question_handles_missing_evidence(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__empty"
    store.upsert_repository(repo_id, "demo/empty", "https://github.com/demo/empty", "main", {})

    answer = answer_question(store, repo_id, "what kind of sql is used", None, "test-model")

    assert "could not find direct graph evidence" in answer.answer.lower()
    assert answer.confidence < 0.3


def test_why_question_uses_decision_summary(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    answer = answer_question(store, "demo__time-machine", "Why was Redis added?", None, "test-model")

    assert "Add Redis-backed cache" in answer.answer
    assert "Most likely reason" in answer.answer
    assert "performance" in answer.answer or "expensive work" in answer.answer
    assert answer.evidence


def test_overview_question_summarizes_repo_graph(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    answer = answer_question(store, "demo__time-machine", "What is this repository about?", None, "test-model")

    assert "demo/time-machine" in answer.answer
    assert "repository historian" in answer.answer
    assert "uses or references" in answer.answer


def test_timeline_includes_categories_and_module_activity(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    events = timeline_events(store, "demo__time-machine")
    categories = {event["category"] for event in events}

    assert "Architecture" in categories
    assert "Technology" in categories
    assert "Module" in categories
    assert all("confidence" in event for event in events)
    assert any(event["title"] == "Redis introduced" for event in events)


def test_timeline_works_without_architecture_decisions(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__timeline"
    store.upsert_repository(repo_id, "demo/timeline", "https://github.com/demo/timeline", "main", {})
    store.add_node(repo_id, "commit:1", "Commit", "abc1234", {"message": "Add auth module", "date": "2024-01-01"})
    store.add_node(repo_id, "commit:2", "Commit", "def5678", {"message": "Refine auth module", "date": "2024-01-03"})
    store.add_node(repo_id, "module:auth", "Module", "auth", {"churn": 2, "commits": 2})
    store.add_edge(repo_id, "edge:1:auth", "commit:1", "module:auth", "AFFECTS")
    store.add_edge(repo_id, "edge:2:auth", "commit:2", "module:auth", "AFFECTS")
    store.add_evidence(repo_id, "evidence:commit:1", "commit", "1", "Commit abc1234", "Add auth module")

    events = timeline_events(store, repo_id)

    assert len(events) == 1
    assert events[0]["category"] == "Module"
    assert events[0]["title"] == "auth module becomes active"


def test_expertise_question_ranks_developers(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    answer = answer_question(store, "demo__time-machine", "Who knows backend best?", None, "test-model")

    assert "Mira Shah" in answer.answer
    assert "matching commits" in answer.answer


def test_contributor_question_lists_developers(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    answer = answer_question(store, "demo__time-machine", "Who are the contributors?", None, "test-model")

    assert "Mira Shah" in answer.answer
    assert "Noah Kim" in answer.answer
    assert "Ava Patel" in answer.answer
    assert "analyzed commits" in answer.answer
    assert answer.confidence > 0.5


def test_broad_repo_understanding_uses_graph_snapshot(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    build_seed_graph(store)

    answer = answer_question(store, "demo__time-machine", "What do you understand about this repo?", None, "test-model")

    assert "repository historian" in answer.answer
    assert "contributors" in answer.answer
    assert "detected technologies" in answer.answer
    assert answer.confidence > 0.5


def test_what_does_this_do_avoids_readme_metadata_dump(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__parking"
    store.upsert_repository(repo_id, "pranay/parking_app", "https://github.com/pranay/parking_app", "main", {"commits": 4})
    store.add_node(
        repo_id,
        f"profile:{repo_id}",
        "ProjectProfile",
        "Project profile",
        {
            "summary": "Vehicle Parking App **MAD 2 Project - IITM BS Degree Program** - **Student Name:** Pranay Aggarwal - **Student Roll Number:** 24F3004524 - **Term:** Sep 2025",
        },
    )
    store.add_node(repo_id, "module:frontend", "Module", "frontend", {"churn": 8, "commits": 2})
    store.add_node(repo_id, "module:backend", "Module", "backend", {"churn": 7, "commits": 2})
    store.add_node(repo_id, "technology:flask", "Technology", "Flask", {})
    store.add_node(repo_id, "technology:sqlite", "Technology", "SQLite", {})
    store.add_node(repo_id, "technology:sqlalchemy", "Technology", "SQLAlchemy", {})

    answer = answer_question(store, repo_id, "what does this do", None, "test-model")

    assert "vehicle parking web application" in answer.answer.lower()
    assert "frontend" in answer.answer
    assert "backend" in answer.answer
    assert "Student Name" not in answer.answer
    assert "Roll Number" not in answer.answer
    assert "Sep 2025" not in answer.answer


def test_generic_no_evidence_answer_is_not_keyword_slop(tmp_path: Path):
    store = Store(tmp_path / "time_machine.sqlite3")
    repo_id = "demo__empty"
    store.upsert_repository(repo_id, "demo/empty", "https://github.com/demo/empty", "main", {})

    answer = answer_question(store, repo_id, "why did they add oauth?", None, "test-model")

    assert "oauth" in answer.answer.lower()
    assert "keyword" not in answer.answer.lower()
    assert answer.evidence == []
