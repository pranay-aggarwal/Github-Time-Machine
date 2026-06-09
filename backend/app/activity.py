from __future__ import annotations

from collections import Counter
from datetime import datetime
import re
from typing import Any

from .storage import Store


def commit_activity(store: Store, repo_id: str) -> dict[str, Any]:
    commits = [node for node in store.list_nodes(repo_id) if node["type"] == "Commit"]
    by_date: Counter[str] = Counter()
    by_hour: Counter[int] = Counter()
    by_contributor: Counter[str] = Counter()
    commits_with_hour = 0

    for commit in commits:
        props = commit.get("properties", {})
        timestamp = props.get("authored_at") or props.get("date")
        parsed, has_hour = parse_commit_timestamp(timestamp)
        if parsed:
            by_date[parsed.date().isoformat()] += 1
            if has_hour:
                by_hour[parsed.hour] += 1
                commits_with_hour += 1
        elif props.get("date"):
            by_date[str(props["date"])] += 1
        author = contributor_for_commit(store, repo_id, commit["id"])
        if author:
            by_contributor[author] += 1

    return {
        "total_commits": len(commits),
        "active_days": len(by_date),
        "has_hour_data": commits_with_hour > 0,
        "commits_with_hour": commits_with_hour,
        "by_date": [{"date": date, "count": count} for date, count in sorted(by_date.items())],
        "by_hour": [{"hour": hour, "count": by_hour.get(hour, 0)} for hour in range(24)],
        "top_dates": [{"date": date, "count": count} for date, count in by_date.most_common(8)],
        "top_time_windows": top_time_windows(by_hour),
        "by_contributor": [{"name": name, "count": count} for name, count in by_contributor.most_common(10)],
    }


def parse_commit_timestamp(value: Any) -> tuple[datetime | None, bool]:
    if not value:
        return None, False
    text = str(value).replace("Z", "+00:00")
    has_hour = "T" in text or bool(re.search(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:", text))
    try:
        return datetime.fromisoformat(text), has_hour
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(f"{text}T00:00:00"), False
    except ValueError:
        return None, False


def contributor_for_commit(store: Store, repo_id: str, commit_node_id: str) -> str | None:
    nodes_by_id = {node["id"]: node for node in store.list_nodes(repo_id)}
    for edge in store.list_edges(repo_id):
        if edge["target_id"] == commit_node_id and edge["type"] == "AUTHOR_OF":
            developer = nodes_by_id.get(edge["source_id"])
            if developer:
                return developer["label"]
    return None


def top_time_windows(by_hour: Counter[int]) -> list[dict[str, int | str]]:
    windows = []
    for start in range(0, 24, 2):
        end = start + 2
        count = by_hour.get(start, 0) + by_hour.get(start + 1, 0)
        windows.append(
            {
                "label": f"{start:02d}:00-{end:02d}:00",
                "start_hour": start,
                "end_hour": end,
                "count": count,
            }
        )
    return [window for window in sorted(windows, key=lambda item: (-int(item["count"]), int(item["start_hour"]))) if int(window["count"]) > 0][:6]
