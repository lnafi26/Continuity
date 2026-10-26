"""Cluster related items into project groups (pure functions).

Stage 5 groups items by taking connected components of the candidate-relationship
graph from Stage 4: nodes are included source items, edges are item_relationships
whose combined_score clears a threshold. Each connected component is a candidate
project. No I/O here -- takes nodes + edges, returns clusters.
"""

from __future__ import annotations


class _DisjointSet:
    def __init__(self):
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # Path compression.
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def connected_components(
    node_ids: list, edges: list[tuple], min_score: float = 0.0
) -> list[list]:
    """Group nodes into connected components.

    node_ids: every item eligible for grouping (so isolated items become
              singleton components).
    edges:    (a, b, combined_score) triples.
    min_score: only edges at or above this score connect their endpoints.

    Returns a list of components, each a list of node ids, largest first.
    """
    ds = _DisjointSet()
    for node in node_ids:
        ds.find(node)  # register every node
    for a, b, score in edges:
        if score >= min_score and a in ds.parent and b in ds.parent:
            ds.union(a, b)

    groups: dict = {}
    for node in node_ids:
        groups.setdefault(ds.find(node), []).append(node)

    components = list(groups.values())
    components.sort(key=len, reverse=True)
    return components


def cluster_cohesion(members: set, edges: list[tuple]) -> float:
    """Average combined_score of edges internal to a cluster (0.0 if none)."""
    internal = [s for a, b, s in edges if a in members and b in members]
    if not internal:
        return 0.0
    return sum(internal) / len(internal)
