from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from openai import OpenAI

from .analyzer import extract_terms
from .models import ChatResponse, Evidence
from .storage import Store


GENERIC_TERMS = {
    "about", "added", "add", "best", "does", "explain", "find", "give", "how",
    "kind", "know", "knows", "me", "most", "repo", "repository", "show", "tell",
    "there", "this", "used", "uses", "using", "what", "when", "where", "which",
    "who", "why", "with",
}
SQL_TECHNOLOGIES = {"postgresql", "mysql", "sqlite", "mariadb", "mssql", "sql server"}
DATABASE_HINTS = {"sql", "database", "db", "storage", "relational"}


def confidence_from_evidence(count: int) -> float:
    if count >= 5:
        return 0.86
    if count >= 3:
        return 0.72
    if count >= 1:
        return 0.5
    return 0.18


def answer_question(store: Store, repo_id: str, question: str, openai_api_key: str | None, model: str) -> ChatResponse:
    context = build_context(store, repo_id, question)
    if openai_api_key and has_repo_understanding(context):
        ai_answer = answer_with_llm(question, context, openai_api_key, model)
        if ai_answer:
            return ai_answer

    deterministic = answer_from_graph(store, repo_id, question, context)
    if deterministic:
        return deterministic

    if not context["evidence"]:
        if has_repo_understanding(context):
            return repo_understanding_summary_answer(context)
        return no_evidence_answer(context)

    return evidence_summary_answer(context)


def build_context(store: Store, repo_id: str, question: str) -> dict[str, Any]:
    terms = meaningful_terms(question)
    nodes = store.list_nodes(repo_id)
    edges = store.list_edges(repo_id)
    repo = store.get_repository(repo_id)
    evidence_rows = rank_evidence(store.list_evidence(repo_id, limit=300), terms)
    matched_nodes = rank_nodes(nodes, terms)
    expanded_node_ids = expand_node_ids({node["id"] for node in matched_nodes[:12]}, edges)
    expanded_nodes = [node for node in nodes if node["id"] in expanded_node_ids]
    snapshot = repo_understanding_snapshot(repo, nodes, edges)
    return {
        "question": question,
        "terms": terms,
        "repo": repo,
        "nodes": nodes,
        "edges": edges,
        "matched_nodes": matched_nodes,
        "expanded_nodes": expanded_nodes,
        "repo_understanding": snapshot,
        "evidence": dedupe_evidence(evidence_rows[:12]),
    }


def answer_from_graph(store: Store, repo_id: str, question: str, context: dict[str, Any]) -> ChatResponse | None:
    lowered = question.lower()
    if asks_overview(lowered):
        return answer_overview(context)
    if asks_about_contributors(lowered):
        return answer_contributors_question(context)
    if asks_about_technology(lowered):
        return answer_technology_question(store, repo_id, lowered, context)
    if asks_why(lowered):
        return answer_why_question(store, repo_id, lowered, context)
    if asks_about_expertise(lowered):
        return answer_expertise_question(context)
    if asks_about_complexity(lowered):
        return answer_complexity_question(context)
    if asks_about_timeline(lowered):
        return answer_timeline_question(store, repo_id)
    return None


def asks_overview(question: str) -> bool:
    return any(phrase in question for phrase in ["what is this", "what does this", "what is the project", "what does it do", "what does this do", "summarize", "overview"])


def has_repo_understanding(context: dict[str, Any]) -> bool:
    snapshot = context.get("repo_understanding", {})
    return any(snapshot.get(key) for key in ["profile_summary", "technologies", "modules", "contributors", "architecture_decisions"])


def repo_understanding_snapshot(repo: dict[str, Any] | None, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = [node for node in nodes if node["type"] == "ProjectProfile"]
    raw_profile_summary = profiles[0]["properties"].get("summary", "") if profiles else ""
    profile_summary = clean_profile_summary(raw_profile_summary)
    edge_counts = Counter(edge["source_id"] for edge in edges if edge["type"] == "AUTHOR_OF")
    contributors = []
    for node in [item for item in nodes if item["type"] == "Developer"]:
        commits = edge_counts.get(node["id"], int(node["properties"].get("commits", 0)))
        contributors.append({"name": node["label"], "analyzed_commits": commits})
    contributors = sorted(contributors, key=lambda item: (-int(item["analyzed_commits"]), item["name"].lower()))[:12]

    modules = [
        {
            "name": node["label"],
            "churn": int(node["properties"].get("churn", 0)),
            "commits": int(node["properties"].get("commits", 0)),
        }
        for node in top_nodes(nodes, "Module", "churn", limit=12)
    ]
    technologies = sorted({node["label"] for node in nodes if node["type"] == "Technology"})
    decisions = [
        {
            "title": node["label"],
            "date": node["properties"].get("date", ""),
            "summary": node["properties"].get("summary", ""),
        }
        for node in nodes
        if node["type"] == "ArchitectureDecision"
    ][:12]
    return {
        "repo_name": (repo or {}).get("name"),
        "metrics": (repo or {}).get("metrics", {}),
        "profile_summary": profile_summary,
        "technologies": technologies[:20],
        "modules": modules,
        "contributors": contributors,
        "architecture_decisions": decisions,
    }


def asks_why(question: str) -> bool:
    return question.startswith("why ") or any(word in question for word in ["introduced", "added", "reason", "motivation"])


def asks_about_technology(question: str) -> bool:
    technology_words = DATABASE_HINTS | {"cache", "queue", "broker", "framework", "library", "technology", "tech", "stack"}
    return any(word in question for word in technology_words) or "what is used" in question or "what kind of" in question


def asks_about_expertise(question: str) -> bool:
    return any(phrase in question for phrase in ["who knows", "expert", "expertise", "contributed most", "worked most"])


def asks_about_contributors(question: str) -> bool:
    return any(phrase in question for phrase in ["who are the contributors", "list contributors", "contributors", "who contributed", "developer list", "developers"])


def asks_about_complexity(question: str) -> bool:
    return any(word in question for word in ["complex", "complexity", "churn", "hotspot", "heatmap"])


def asks_about_timeline(question: str) -> bool:
    return any(word in question for word in ["timeline", "evolution", "architecture changes", "changed over time"])


def answer_overview(context: dict[str, Any]) -> ChatResponse:
    repo = context["repo"] or {}
    profiles = [node for node in context["nodes"] if node["type"] == "ProjectProfile"]
    modules = top_nodes(context["nodes"], "Module", "churn", limit=5)
    tech = sorted(node["label"] for node in context["nodes"] if node["type"] == "Technology")[:8]
    metrics = repo.get("metrics", {})
    profile_summary = clean_profile_summary(profiles[0]["properties"].get("summary", "")) if profiles else ""
    purpose = project_purpose_sentence(repo.get("name", "This repository"), profile_summary, tech, [node["label"] for node in modules])
    parts = []
    parts.append(purpose or f"{repo.get('name', 'This repository')} has {metrics.get('commits', 0)} analyzed commits")
    if modules:
        parts.append(f"The main active areas are {format_list([node['label'] for node in modules])}")
    if tech:
        parts.append(f"It uses or references {format_list(tech)}")
    answer = ". ".join(parts) + "."
    return ChatResponse(
        answer=answer,
        reasoning_chain=[
            "Read repository profile evidence from README/manifests when available.",
            "Read repository metrics from the analysis summary.",
            "Ranked modules by recorded churn.",
            "Listed technologies detected from commits, dependency files, PRs, and issues.",
        ],
        evidence=context["evidence"],
        confidence=0.7 if metrics else 0.45,
    )


def answer_technology_question(store: Store, repo_id: str, question: str, context: dict[str, Any]) -> ChatResponse:
    tech_nodes = [node for node in context["nodes"] if node["type"] == "Technology"]
    topic = "technology usage"
    if DATABASE_HINTS & set(context["terms"]):
        topic = "database/storage usage"
        sql_matches = [node for node in tech_nodes if node["label"].lower() in SQL_TECHNOLOGIES]
        tech_nodes = sql_matches or [node for node in tech_nodes if any(hint in node["label"].lower() for hint in DATABASE_HINTS)]
    else:
        filtered = [node for node in tech_nodes if text_matches(node["label"], context["terms"])]
        tech_nodes = filtered or tech_nodes

    if not tech_nodes:
        return ChatResponse(
            answer=f"I could not find direct graph evidence for {topic}. The repo may still use it, but it was not detected in commits, PRs, issues, or dependency/config evidence.",
            reasoning_chain=["Checked Technology nodes in the graph.", "No matching technology nodes were found."],
            evidence=[],
            confidence=confidence_from_evidence(0),
        )

    labels = sorted({node["label"] for node in tech_nodes})
    evidence = evidence_for_labels(store, repo_id, labels, context["evidence"])
    answer = f"The repository evidence points to {format_list(labels)} for {topic}."
    if len(labels) > 1:
        answer += " Because multiple technologies matched, treat this as evidence of references or historical usage rather than proof that all are active in production."
    return ChatResponse(
        answer=answer,
        reasoning_chain=[
            "Detected a technology or stack question.",
            "Matched the question against Technology nodes in the graph.",
            "Attached evidence records that mention the matched technologies.",
        ],
        evidence=evidence,
        confidence=confidence_from_evidence(len(evidence)),
    )


def answer_why_question(store: Store, repo_id: str, question: str, context: dict[str, Any]) -> ChatResponse:
    terms = context["terms"]
    decisions = [node for node in context["nodes"] if node["type"] == "ArchitectureDecision" and text_matches(node["label"], terms)]
    tech = [node for node in context["nodes"] if node["type"] == "Technology" and text_matches(node["label"], terms)]
    labels = [node["label"] for node in decisions + tech]
    evidence = evidence_for_labels(store, repo_id, labels or terms, context["evidence"])

    if not evidence:
        return no_evidence_answer(context)

    decision_bits = []
    for decision in decisions[:3]:
        summary = decision["properties"].get("summary")
        date = decision["properties"].get("date")
        if summary:
            decision_bits.append(f"{decision['label']} on {date or 'an unknown date'}: {summary}")

    if decision_bits:
        answer = "Evidence: " + " ".join(decision_bits)
    else:
        answer = f"Evidence: I found related records for {readable_question_topic(context['question'])}: {format_list([item.title for item in evidence[:4]])}."
    answer += f" Most likely reason: {infer_likely_reason(context, evidence)}"

    return ChatResponse(
        answer=answer,
        reasoning_chain=[
            "Detected a why/motivation question.",
            "Looked for matching ArchitectureDecision and Technology nodes.",
            "Used related commits, PRs, and issues as supporting evidence.",
            "Added a clearly labeled likely reason when the evidence implies intent but does not state it directly.",
        ],
        evidence=evidence,
        confidence=confidence_from_evidence(len(evidence)),
    )


def answer_expertise_question(context: dict[str, Any]) -> ChatResponse:
    edges_by_target = defaultdict(list)
    for edge in context["edges"]:
        edges_by_target[edge["target_id"]].append(edge)

    developer_scores = Counter()
    developer_labels = {}
    matched_module_ids = {node["id"] for node in context["matched_nodes"] if node["type"] == "Module"}

    for node in context["nodes"]:
        if node["type"] == "Developer":
            developer_labels[node["id"]] = node["label"]
            developer_scores[node["id"]] += int(node["properties"].get("commits", 0))

    if matched_module_ids:
        commit_ids = {edge["source_id"] for edge in context["edges"] if edge["type"] == "AFFECTS" and edge["target_id"] in matched_module_ids}
        developer_scores = Counter()
        for commit_id in commit_ids:
            for edge in edges_by_target[commit_id]:
                if edge["type"] == "AUTHOR_OF":
                    developer_scores[edge["source_id"]] += 1

    ranked = [(developer_labels.get(dev_id, dev_id), score) for dev_id, score in developer_scores.most_common(5) if score > 0]
    if not ranked:
        return ChatResponse(
            answer="I could not find developer contribution evidence for that question.",
            reasoning_chain=["Checked Developer and AUTHOR_OF edges.", "No usable contribution evidence was available."],
            evidence=[],
            confidence=confidence_from_evidence(0),
        )

    answer = f"Based on the graph, the strongest expertise candidates are {format_list([f'{name} ({score} matching commits)' for name, score in ranked])}."
    if not matched_module_ids:
        answer += " This is a broad repository-level ranking because the question did not match a specific module."
    return ChatResponse(
        answer=answer,
        reasoning_chain=[
            "Detected an expertise question.",
            "Matched the question to modules when possible.",
            "Ranked developers from AUTHOR_OF commit edges.",
        ],
        evidence=context["evidence"],
        confidence=0.7,
    )


def answer_contributors_question(context: dict[str, Any]) -> ChatResponse:
    developers = [node for node in context["nodes"] if node["type"] == "Developer"]
    if not developers:
        return ChatResponse(
            answer="I could not find contributor evidence in the analyzed graph.",
            reasoning_chain=["Detected a contributors question.", "Checked Developer nodes.", "No Developer nodes were available."],
            evidence=[],
            confidence=confidence_from_evidence(0),
        )

    author_edges = [edge for edge in context["edges"] if edge["type"] == "AUTHOR_OF"]
    edge_counts = Counter(edge["source_id"] for edge in author_edges)
    ranked = sorted(
        developers,
        key=lambda node: (edge_counts.get(node["id"], 0), int(node["properties"].get("commits", 0)), node["label"].lower()),
        reverse=True,
    )
    labels = []
    for developer in ranked[:8]:
        count = edge_counts.get(developer["id"], int(developer["properties"].get("commits", 0)))
        labels.append(f"{developer['label']} ({count} analyzed commits)")

    return ChatResponse(
        answer=f"The contributors I found in the analyzed commit graph are {format_list(labels)}.",
        reasoning_chain=[
            "Detected a contributors question.",
            "Read Developer nodes from the graph.",
            "Counted AUTHOR_OF edges to rank contributors by analyzed commits.",
        ],
        evidence=context["evidence"],
        confidence=0.72 if author_edges else 0.5,
    )


def answer_complexity_question(context: dict[str, Any]) -> ChatResponse:
    ranked = top_nodes(context["nodes"], "Module", "churn", limit=5)
    if not ranked:
        return ChatResponse(
            answer="I could not find module churn evidence for complexity ranking.",
            reasoning_chain=["Checked Module nodes in the graph.", "No module churn metrics were available."],
            evidence=[],
            confidence=confidence_from_evidence(0),
        )
    labels = [f"{node['label']} (churn {node['properties'].get('churn', 0)}, commits {node['properties'].get('commits', 'unknown')})" for node in ranked]
    return ChatResponse(
        answer=f"The highest-complexity candidates by available churn evidence are {format_list(labels)}.",
        reasoning_chain=[
            "Detected a complexity question.",
            "Ranked Module nodes by churn.",
            "Used churn as a proxy rather than claiming true code complexity.",
        ],
        evidence=context["evidence"],
        confidence=0.68,
    )


def answer_timeline_question(store: Store, repo_id: str) -> ChatResponse:
    events = timeline_events(store, repo_id)
    if not events:
        return ChatResponse(
            answer="I could not find architecture timeline events in the graph.",
            reasoning_chain=["Checked ArchitectureDecision nodes.", "No timeline events were available."],
            evidence=[],
            confidence=confidence_from_evidence(0),
        )
    descriptions = [f"{event['date'] or 'unknown date'}: {event['title']}" for event in events[:6]]
    evidence = []
    for event in events[:6]:
        evidence.extend(event["evidence"])
    return ChatResponse(
        answer=f"The architecture timeline I can support is {format_list(descriptions)}.",
        reasoning_chain=[
            "Detected an architecture evolution question.",
            "Sorted ArchitectureDecision nodes by date.",
            "Returned only events with graph evidence.",
        ],
        evidence=evidence[:10],
        confidence=confidence_from_evidence(len(evidence)),
    )


def answer_with_llm(question: str, context: dict[str, Any], openai_api_key: str, model: str) -> ChatResponse | None:
    evidence = context["evidence"]
    try:
        client = OpenAI(api_key=openai_api_key)
        payload = {
            "question": question,
            "repo": context["repo"],
            "repo_understanding": context["repo_understanding"],
            "matched_graph_nodes": compact_nodes(context["expanded_nodes"][:40]),
            "evidence": [item.model_dump() for item in evidence],
            "rules": [
                "Answer only from supplied repo_understanding, graph nodes, and evidence.",
                "Use repo_understanding for broad questions about contributors, modules, tech stack, project purpose, and architecture.",
                "Write naturally and directly. Do not expose internal retrieval steps.",
                "For 'what does this do' or similar questions, explain the application purpose and main capabilities first; do not repeat assignment metadata, student names, roll numbers, or term details unless explicitly asked.",
                "When motivation is not explicit, provide a clearly labeled 'Most likely reason' grounded in the evidence.",
                "If the graph has relevant facts but no evidence snippets, say it is based on analyzed graph metadata.",
                "If the supplied context is not enough, say what is missing instead of guessing.",
                "Return strict JSON with answer, reasoning_chain, confidence.",
            ],
        }
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": "You are an evidence-bound software repository historian."},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        parsed = json.loads(response.output_text)
        return ChatResponse(
            answer=parsed.get("answer", "").strip() or evidence_summary_answer(context).answer,
            reasoning_chain=parsed.get("reasoning_chain", [])[:6] or evidence_summary_answer(context).reasoning_chain,
            evidence=evidence,
            confidence=float(parsed.get("confidence", confidence_from_evidence(len(evidence)))),
        )
    except Exception:
        return None


def evidence_summary_answer(context: dict[str, Any]) -> ChatResponse:
    evidence = context["evidence"]
    top_titles = [item.title for item in evidence[:5]]
    answer = f"I found evidence related to {readable_question_topic(context['question'])}: {format_list(top_titles)}."
    answer += " The available evidence does not support a more specific conclusion without reading the linked items."
    return ChatResponse(
        answer=answer,
        reasoning_chain=[
            "Cleaned the question into meaningful repository terms.",
            "Ranked evidence records and graph nodes by relevance.",
            "Summarized only the strongest matching evidence.",
        ],
        evidence=evidence,
        confidence=confidence_from_evidence(len(evidence)),
    )


def repo_understanding_summary_answer(context: dict[str, Any]) -> ChatResponse:
    snapshot = context["repo_understanding"]
    parts = []
    purpose = project_purpose_sentence(
        snapshot.get("repo_name") or "This repository",
        snapshot.get("profile_summary", ""),
        snapshot.get("technologies", []),
        [item["name"] for item in snapshot.get("modules", [])],
    )
    if purpose:
        parts.append(purpose)
    if snapshot.get("contributors"):
        contributors = [f"{item['name']} ({item['analyzed_commits']} analyzed commits)" for item in snapshot["contributors"][:6]]
        parts.append(f"contributors found in the analyzed graph include {format_list(contributors)}")
    if snapshot.get("technologies"):
        parts.append(f"detected technologies include {format_list(snapshot['technologies'][:8])}")
    if snapshot.get("modules"):
        modules = [f"{item['name']} (churn {item['churn']})" for item in snapshot["modules"][:5]]
        parts.append(f"active modules include {format_list(modules)}")
    if snapshot.get("architecture_decisions"):
        decisions = [item["title"] for item in snapshot["architecture_decisions"][:4]]
        parts.append(f"architecture events include {format_list(decisions)}")

    return ChatResponse(
        answer=". ".join(parts) + ".",
        reasoning_chain=[
            "Used the analyzed repository graph rather than keyword-only evidence.",
            "Read project profile, contributor, module, technology, and architecture nodes.",
            "Summarized only facts present in the graph metadata.",
        ],
        evidence=context["evidence"],
        confidence=0.62,
    )


def infer_likely_reason(context: dict[str, Any], evidence: list[Evidence]) -> str:
    text = " ".join([item.title + " " + item.snippet for item in evidence]).lower()
    profile_nodes = [node for node in context["nodes"] if node["type"] == "ProjectProfile"]
    profile_summary = profile_nodes[0]["properties"].get("summary", "").lower() if profile_nodes else ""
    combined = f"{text} {profile_summary}"

    if any(word in combined for word in ["cache", "caching", "redis", "slow", "performance", "speed", "latency"]):
        return "to improve performance or reduce repeated expensive work, based on caching/performance-related evidence."
    if any(word in combined for word in ["auth", "login", "user", "permission", "security", "oauth"]):
        return "to support user identity, access control, or security-related functionality."
    if any(word in combined for word in ["database", "sql", "postgres", "mysql", "sqlite", "storage", "persist"]):
        return "to persist structured application data reliably."
    if any(word in combined for word in ["docker", "container", "compose", "deploy", "production"]):
        return "to make the application easier to run, package, or deploy consistently."
    if any(word in combined for word in ["graph", "networkx", "relationship", "evidence"]):
        return "to model relationships between repository artifacts so answers can be backed by connected evidence."
    if evidence:
        return f"to support the change described by {format_list([item.title for item in evidence[:3]])}; the exact motivation is inferred because the evidence does not state it directly."
    return "there is not enough evidence to infer a likely reason confidently."


def clean_profile_summary(summary: str) -> str:
    if not summary:
        return ""
    cleaned_parts = []
    for part in re.split(r"\s+(?=(?:[-*#]|\*\*|[A-Z][A-Za-z ]{2,}:))", summary):
        text = strip_markdown(part).strip(" -:;")
        lowered = text.lower()
        if not text:
            continue
        if any(noise in lowered for noise in ["student name", "student roll", "roll number", "term:", "iitm bs degree", "mad 2 project"]):
            continue
        cleaned_parts.append(text)
    cleaned = " ".join(cleaned_parts).strip()
    return re.sub(r"\s+", " ", cleaned)[:500]


def strip_markdown(text: str) -> str:
    text = re.sub(r"[*_`>#]+", "", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text


def project_purpose_sentence(repo_name: str, profile_summary: str, technologies: list[str], modules: list[str]) -> str:
    source = f"{repo_name} {profile_summary}".lower()
    tech_text = " ".join(technologies).lower()
    module_text = " ".join(modules).lower()

    if "parking" in source:
        base = f"{repo_name} is a vehicle parking web application."
        details = []
        if any(word in module_text for word in ["frontend", "backend"]):
            details.append("It has separate frontend and backend areas")
        if any(word in tech_text for word in ["flask", "sqlalchemy", "sqlite"]):
            details.append("the backend appears to handle application logic and database-backed parking data")
        if any(word in tech_text for word in ["redis", "celery"]):
            details.append("Redis/Celery suggest background jobs or caching support")
        return base + (" " + "; ".join(details) if details else "")

    if profile_summary:
        return f"{repo_name} is {profile_summary.rstrip('.')}"

    if technologies or modules:
        bits = []
        if modules:
            bits.append(f"active areas include {format_list(modules[:4])}")
        if technologies:
            bits.append(f"detected technologies include {format_list(technologies[:6])}")
        return f"{repo_name} is an analyzed software repository; " + "; ".join(bits)

    return ""


def no_evidence_answer(context: dict[str, Any]) -> ChatResponse:
    return ChatResponse(
        answer=f"I do not have enough repository evidence to answer about {readable_question_topic(context['question'])}. Try asking about a detected module, technology, commit, PR, issue, or run analysis with GitHub metadata enabled.",
        reasoning_chain=[
            "Cleaned the question into meaningful repository terms.",
            "Searched graph nodes and evidence records.",
            "No matching evidence was strong enough to support an answer.",
        ],
        evidence=[],
        confidence=confidence_from_evidence(0),
    )


def timeline_events(store: Store, repo_id: str) -> list[dict[str, Any]]:
    nodes = store.list_nodes(repo_id)
    edges = store.list_edges(repo_id)
    evidence_rows = store.list_evidence(repo_id, limit=500)
    node_by_id = {node["id"]: node for node in nodes}
    events: list[dict[str, Any]] = []

    for decision in [node for node in nodes if node["type"] == "ArchitectureDecision"]:
        props = decision["properties"]
        evidence = evidence_for_timeline_item(evidence_rows, [decision["id"], decision["label"]])
        events.append(
            {
                "date": props.get("date", ""),
                "title": decision["label"],
                "summary": props.get("summary") or "Architecture decision detected from repository evidence.",
                "evidence": evidence,
                "category": "Architecture",
                "confidence": confidence_from_evidence(len(evidence)),
            }
        )

    events.extend(technology_timeline_events(edges, node_by_id, evidence_rows))
    events.extend(module_timeline_events(edges, node_by_id, evidence_rows))
    return sorted(dedupe_timeline_events(events), key=timeline_sort_key)


def technology_timeline_events(edges: list[dict[str, Any]], node_by_id: dict[str, dict[str, Any]], evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    introduced: dict[str, dict[str, Any]] = {}
    for edge in edges:
        if edge["type"] != "INTRODUCED":
            continue
        commit = node_by_id.get(edge["source_id"])
        tech = node_by_id.get(edge["target_id"])
        if not commit or not tech or commit["type"] != "Commit" or tech["type"] != "Technology":
            continue
        current = introduced.get(tech["id"])
        commit_date = commit["properties"].get("date", "")
        if current is None or commit_date < current["commit"]["properties"].get("date", "9999-99-99"):
            introduced[tech["id"]] = {"technology": tech, "commit": commit}

    events = []
    for item in introduced.values():
        tech = item["technology"]
        commit = item["commit"]
        evidence = evidence_for_timeline_item(evidence_rows, [tech["label"], commit["id"].replace("commit:", ""), commit["label"]])
        events.append(
            {
                "date": commit["properties"].get("date", ""),
                "title": f"{tech['label']} introduced",
                "summary": f"{tech['label']} first appears in analyzed commit evidence: {commit['properties'].get('message', commit['label'])}",
                "evidence": evidence,
                "category": "Technology",
                "confidence": confidence_from_evidence(len(evidence)),
            }
        )
    return events


def module_timeline_events(edges: list[dict[str, Any]], node_by_id: dict[str, dict[str, Any]], evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    commits_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        if edge["type"] != "AFFECTS":
            continue
        commit = node_by_id.get(edge["source_id"])
        module = node_by_id.get(edge["target_id"])
        if not commit or not module or commit["type"] != "Commit" or module["type"] != "Module":
            continue
        commits_by_module[module["id"]].append(commit)

    events = []
    for module_id, commits in commits_by_module.items():
        module = node_by_id[module_id]
        churn = int(module["properties"].get("churn", 0))
        if churn < 2 and len(commits) < 2:
            continue
        earliest = sorted(commits, key=lambda commit: commit["properties"].get("date", ""))[0]
        evidence = evidence_for_timeline_item(evidence_rows, [module["label"], earliest["id"].replace("commit:", ""), earliest["label"]])
        events.append(
            {
                "date": earliest["properties"].get("date", ""),
                "title": f"{module['label']} module becomes active",
                "summary": f"{module['label']} is one of the more active modules in the analyzed history, with churn {churn or len(commits)} across {len(commits)} related commits.",
                "evidence": evidence,
                "category": "Module",
                "confidence": 0.6 if evidence else 0.42,
            }
        )
    return events


def evidence_for_timeline_item(evidence_rows: list[dict[str, Any]], keys: list[str]) -> list[Evidence]:
    terms = []
    for key in keys:
        terms.extend(meaningful_terms(key))
    ranked = rank_evidence(evidence_rows, terms)
    return evidence_from_rows(ranked[:4])


def dedupe_timeline_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for event in events:
        key = (event.get("date", ""), event.get("category", ""), event.get("title", "").lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def timeline_sort_key(event: dict[str, Any]) -> tuple[str, str]:
    return (event.get("date") or "9999-99-99", event.get("title", ""))


def meaningful_terms(question: str) -> list[str]:
    raw_terms = extract_terms(question)
    terms = [term.lower() for term in raw_terms if term.lower() not in GENERIC_TERMS]
    if "sql" in question.lower() and "sql" not in terms:
        terms.append("sql")
    return terms


def rank_evidence(rows: list[dict[str, Any]], terms: list[str]) -> list[dict[str, Any]]:
    if not terms:
        return rows[:12]
    scored = []
    for row in rows:
        text = f"{row['title']} {row['snippet']}".lower()
        score = sum(3 if re.search(rf"\b{re.escape(term)}\b", text) else (1 if term in text else 0) for term in terms)
        if score:
            scored.append((score, row))
    return [row for _, row in sorted(scored, key=lambda item: item[0], reverse=True)]


def rank_nodes(nodes: list[dict[str, Any]], terms: list[str]) -> list[dict[str, Any]]:
    if not terms:
        return []
    scored = []
    for node in nodes:
        text = f"{node['type']} {node['label']} {json.dumps(node.get('properties', {}))}".lower()
        score = sum(2 if re.search(rf"\b{re.escape(term)}\b", text) else (1 if term in text else 0) for term in terms)
        if score:
            scored.append((score, node))
    return [node for _, node in sorted(scored, key=lambda item: item[0], reverse=True)]


def expand_node_ids(seed_ids: set[str], edges: list[dict[str, Any]]) -> set[str]:
    expanded = set(seed_ids)
    for edge in edges:
        if edge["source_id"] in seed_ids:
            expanded.add(edge["target_id"])
        if edge["target_id"] in seed_ids:
            expanded.add(edge["source_id"])
    return expanded


def evidence_for_labels(store: Store, repo_id: str, labels: list[str], fallback: list[Evidence]) -> list[Evidence]:
    rows = []
    for label in labels:
        rows.extend(store.search_evidence(repo_id, meaningful_terms(label), limit=4))
    evidence = dedupe_evidence(rows)
    return evidence or fallback[:6]


def text_matches(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def top_nodes(nodes: list[dict[str, Any]], node_type: str, property_name: str, limit: int) -> list[dict[str, Any]]:
    typed = [node for node in nodes if node["type"] == node_type]
    return sorted(typed, key=lambda node: int(node["properties"].get(property_name, 0)), reverse=True)[:limit]


def readable_question_topic(question: str) -> str:
    terms = meaningful_terms(question)
    if not terms:
        return "that question"
    return " ".join(terms)


def dedupe_evidence(rows: list[dict[str, Any]]) -> list[Evidence]:
    return evidence_from_rows(rows)[:10]


def evidence_from_rows(rows: list[dict[str, Any]]) -> list[Evidence]:
    seen = set()
    evidence: list[Evidence] = []
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        evidence.append(
            Evidence(
                id=row["id"],
                source_type=row["source_type"],
                source_id=row["source_id"],
                title=row["title"],
                url=row["url"],
                snippet=row["snippet"],
            )
        )
    return evidence


def compact_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": node["id"],
            "type": node["type"],
            "label": node["label"],
            "properties": node.get("properties", {}),
        }
        for node in nodes
    ]


def format_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"
