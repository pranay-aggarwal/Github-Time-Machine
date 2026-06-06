from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class Store:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists analysis_jobs (
                    id text primary key,
                    repo_id text,
                    repo_url text not null,
                    status text not null,
                    progress integer not null,
                    message text not null,
                    created_at text default current_timestamp,
                    updated_at text default current_timestamp
                );

                create table if not exists repositories (
                    id text primary key,
                    name text not null,
                    url text not null,
                    default_branch text,
                    metrics_json text not null default '{}',
                    created_at text default current_timestamp
                );

                create table if not exists nodes (
                    id text primary key,
                    repo_id text not null,
                    type text not null,
                    label text not null,
                    properties_json text not null default '{}'
                );

                create table if not exists edges (
                    id text primary key,
                    repo_id text not null,
                    source_id text not null,
                    target_id text not null,
                    type text not null,
                    properties_json text not null default '{}'
                );

                create table if not exists evidence (
                    id text primary key,
                    repo_id text not null,
                    source_type text not null,
                    source_id text not null,
                    title text not null,
                    url text,
                    snippet text not null,
                    created_at text default current_timestamp
                );

                create index if not exists idx_nodes_repo on nodes(repo_id);
                create index if not exists idx_edges_repo on edges(repo_id);
                create index if not exists idx_evidence_repo on evidence(repo_id);
                """
            )

    def create_job(self, job_id: str, repo_url: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert into analysis_jobs (id, repo_url, status, progress, message) values (?, ?, ?, ?, ?)",
                (job_id, repo_url, "queued", 0, "Queued for analysis"),
            )

    def update_job(self, job_id: str, status: str, progress: int, message: str, repo_id: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                update analysis_jobs
                set status = ?, progress = ?, message = ?, repo_id = coalesce(?, repo_id), updated_at = current_timestamp
                where id = ?
                """,
                (status, progress, message, repo_id, job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from analysis_jobs where id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def upsert_repository(self, repo_id: str, name: str, url: str, default_branch: str | None, metrics: dict[str, int]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into repositories (id, name, url, default_branch, metrics_json)
                values (?, ?, ?, ?, ?)
                on conflict(id) do update set name = excluded.name, url = excluded.url,
                default_branch = excluded.default_branch, metrics_json = excluded.metrics_json
                """,
                (repo_id, name, url, default_branch, json.dumps(metrics)),
            )

    def get_repository(self, repo_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from repositories where id = ?", (repo_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["metrics"] = json.loads(data.pop("metrics_json") or "{}")
            return data

    def clear_repo_graph(self, repo_id: str) -> None:
        with self.connect() as conn:
            conn.execute("delete from evidence where repo_id = ?", (repo_id,))
            conn.execute("delete from edges where repo_id = ?", (repo_id,))
            conn.execute("delete from nodes where repo_id = ?", (repo_id,))

    def add_node(self, repo_id: str, node_id: str, node_type: str, label: str, properties: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into nodes (id, repo_id, type, label, properties_json)
                values (?, ?, ?, ?, ?)
                on conflict(id) do update set label = excluded.label, properties_json = excluded.properties_json
                """,
                (node_id, repo_id, node_type, label, json.dumps(properties or {})),
            )

    def add_edge(self, repo_id: str, edge_id: str, source_id: str, target_id: str, edge_type: str, properties: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert or ignore into edges (id, repo_id, source_id, target_id, type, properties_json)
                values (?, ?, ?, ?, ?, ?)
                """,
                (edge_id, repo_id, source_id, target_id, edge_type, json.dumps(properties or {})),
            )

    def add_evidence(self, repo_id: str, evidence_id: str, source_type: str, source_id: str, title: str, snippet: str, url: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert or ignore into evidence (id, repo_id, source_type, source_id, title, url, snippet)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (evidence_id, repo_id, source_type, source_id, title, url, snippet[:2000]),
            )

    def list_nodes(self, repo_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("select * from nodes where repo_id = ?", (repo_id,)).fetchall()
        return [self._decode(row) for row in rows]

    def list_edges(self, repo_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("select * from edges where repo_id = ?", (repo_id,)).fetchall()
        return [self._decode(row) for row in rows]

    def list_evidence(self, repo_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from evidence where repo_id = ? order by created_at desc limit ?",
                (repo_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def search_evidence(self, repo_id: str, terms: list[str], limit: int = 12) -> list[dict[str, Any]]:
        if not terms:
            return []
        clauses = " or ".join(["lower(title || ' ' || snippet) like ?" for _ in terms])
        params = [repo_id, *[f"%{term.lower()}%" for term in terms]]
        with self.connect() as conn:
            rows = conn.execute(
                f"select * from evidence where repo_id = ? and ({clauses}) order by created_at desc limit ?",
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        if "properties_json" in data:
            data["properties"] = json.loads(data.pop("properties_json") or "{}")
        return data
