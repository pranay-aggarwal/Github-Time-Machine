from __future__ import annotations

import networkx as nx

from .storage import Store


TYPE_COLORS = {
    "Repository": "#15171a",
    "ProjectProfile": "#2f8f83",
    "ArchitectureDecision": "#c07a21",
    "Technology": "#7d4e8a",
    "Module": "#2563eb",
    "PullRequest": "#0f766e",
    "Issue": "#be123c",
    "Commit": "#475569",
    "Developer": "#9333ea",
}


def react_flow_graph(store: Store, repo_id: str) -> dict[str, list[dict]]:
    nodes = store.list_nodes(repo_id)
    edges = store.list_edges(repo_id)
    evidence = store.list_evidence(repo_id, 1000)
    evidence_by_source = {}
    for item in evidence:
        evidence_by_source.setdefault(str(item["source_id"]), []).append(item["id"])
    graph = nx.MultiDiGraph()
    for node in nodes:
        graph.add_node(node["id"], **node)
    for edge in edges:
        graph.add_edge(edge["source_id"], edge["target_id"], key=edge["id"], **edge)
    type_order = {
        "Repository": 0,
        "ProjectProfile": 1,
        "ArchitectureDecision": 2,
        "Technology": 3,
        "Module": 4,
        "PullRequest": 5,
        "Issue": 6,
        "Commit": 7,
        "Developer": 8,
    }
    type_rows: dict[str, int] = {}
    flow_nodes = []
    for index, node in enumerate(sorted(nodes, key=lambda item: (type_order.get(item["type"], 9), item["label"]))[:200]):
        column = type_order.get(node["type"], 8)
        row = type_rows.get(node["type"], 0)
        type_rows[node["type"]] = row + 1
        properties = node.get("properties", {})
        evidence_ids = evidence_ids_for_node(node, evidence_by_source)
        summary = properties.get("summary") or properties.get("message") or properties.get("path") or node["label"]
        flow_nodes.append(
            {
                "id": node["id"],
                "type": "default",
                "position": {"x": column * 250, "y": row * 96},
                "className": f"graph-node graph-node-{node['type'].lower()}",
                "style": {
                    "borderColor": TYPE_COLORS.get(node["type"], "#d8d5ca"),
                    "borderWidth": 2,
                    "background": "#ffffff",
                },
                "data": {
                    "label": node["label"],
                    "type": node["type"],
                    "summary": str(summary)[:260],
                    "properties": properties,
                    "evidenceCount": len(evidence_ids),
                    "evidenceIds": evidence_ids,
                    "color": TYPE_COLORS.get(node["type"], "#64748b"),
                },
            }
        )
    node_ids = {node["id"] for node in flow_nodes}
    graph_edges = [data for _, _, _, data in graph.edges(keys=True, data=True)]
    flow_edges = [
        {
            "id": edge["id"],
            "source": edge["source_id"],
            "target": edge["target_id"],
            "label": edge["type"],
            "data": {
                "relationship": edge["type"],
                "label": edge["type"].replace("_", " ").title(),
                "properties": edge.get("properties", {}),
            },
            "animated": edge["type"] in {"INTRODUCED", "RESOLVES", "SUPPORTED_BY"},
            "style": {"strokeWidth": 2 if edge["type"] in {"INTRODUCED", "SUPPORTED_BY"} else 1.5},
        }
        for edge in graph_edges
        if edge["source_id"] in node_ids and edge["target_id"] in node_ids
    ][:300]
    return {"nodes": flow_nodes, "edges": flow_edges}


def evidence_ids_for_node(node: dict, evidence_by_source: dict[str, list[str]]) -> list[str]:
    node_id = node["id"]
    candidates = [node_id, node_id.split(":", 1)[-1]]
    if node["type"] == "Commit":
        candidates.append(node_id.replace("commit:", ""))
    if node["type"] == "ArchitectureDecision":
        candidates.append(node_id)
    ids: list[str] = []
    for candidate in candidates:
        ids.extend(evidence_by_source.get(candidate, []))
    return sorted(set(ids))
