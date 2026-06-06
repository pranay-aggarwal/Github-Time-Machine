from __future__ import annotations

import networkx as nx

from .storage import Store


def react_flow_graph(store: Store, repo_id: str) -> dict[str, list[dict]]:
    nodes = store.list_nodes(repo_id)
    edges = store.list_edges(repo_id)
    graph = nx.MultiDiGraph()
    for node in nodes:
        graph.add_node(node["id"], **node)
    for edge in edges:
        graph.add_edge(edge["source_id"], edge["target_id"], key=edge["id"], **edge)
    type_order = {
        "Repository": 0,
        "ArchitectureDecision": 1,
        "Technology": 2,
        "Module": 3,
        "PullRequest": 4,
        "Issue": 5,
        "Commit": 6,
        "Developer": 7,
    }
    flow_nodes = []
    for index, node in enumerate(sorted(nodes, key=lambda item: (type_order.get(item["type"], 9), item["label"]))[:200]):
        column = type_order.get(node["type"], 8)
        row = index % 18
        flow_nodes.append(
            {
                "id": node["id"],
                "type": "default",
                "position": {"x": column * 230, "y": row * 80},
                "data": {"label": f"{node['type']}: {node['label']}"},
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
            "animated": edge["type"] in {"INTRODUCED", "RESOLVES", "SUPPORTED_BY"},
        }
        for edge in graph_edges
        if edge["source_id"] in node_ids and edge["target_id"] in node_ids
    ][:300]
    return {"nodes": flow_nodes, "edges": flow_edges}
