"""Real pairwise face-embedding comparison + NetworkX connected-component
analysis: if the same face (embedding similarity above threshold) shows
up under two different declared names/document numbers, that's a
multi-identity cluster — a real fraud signal, not a hardcoded flag.
"""
import json

import networkx as nx

from app.models.identity_embedding import IdentityEmbeddingRecord
from app.services.face.embedding import cosine_similarity
from app.services.identity_graph.base import IdentityClusterMember, IdentityGraphResult

DEFAULT_MATCH_THRESHOLD = 0.75


def build_graph(
    records: list[IdentityEmbeddingRecord], threshold: float = DEFAULT_MATCH_THRESHOLD
) -> nx.Graph:
    graph = nx.Graph()
    for record in records:
        graph.add_node(
            str(record.id), reference_name=record.reference_name, document_number=record.document_number
        )

    embeddings = {str(record.id): json.loads(record.embedding_json) for record in records}
    ids = list(embeddings)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            similarity = cosine_similarity(embeddings[ids[i]], embeddings[ids[j]])
            if similarity >= threshold:
                graph.add_edge(ids[i], ids[j], similarity=similarity)
    return graph


def find_multi_identity_cluster(graph: nx.Graph, node_id: str) -> IdentityGraphResult:
    if node_id not in graph:
        return IdentityGraphResult(
            status="NO_CLUSTER", cluster_size=0, members=[], reason=f"record {node_id} not found in graph"
        )

    component = nx.node_connected_component(graph, node_id)
    members = [
        IdentityClusterMember(
            record_id=n,
            reference_name=graph.nodes[n]["reference_name"],
            document_number=graph.nodes[n]["document_number"],
        )
        for n in component
    ]
    distinct_names = {m.reference_name.strip().upper() for m in members}
    distinct_docs = {m.document_number for m in members if m.document_number}

    is_multi_identity = len(component) > 1 and (len(distinct_names) > 1 or len(distinct_docs) > 1)
    if is_multi_identity:
        return IdentityGraphResult(
            status="CLUSTER_FOUND",
            cluster_size=len(component),
            members=members,
            reason=(
                f"{len(component)} face embeddings connected by similarity >= "
                f"{DEFAULT_MATCH_THRESHOLD} form one cluster spanning {len(distinct_names)} "
                f"distinct declared name(s) and {len(distinct_docs)} distinct document number(s)"
            ),
        )
    return IdentityGraphResult(
        status="NO_CLUSTER",
        cluster_size=len(component),
        members=members,
        reason=f"embedding matches only its own declared identity ({len(component)} record(s) in cluster)",
    )
