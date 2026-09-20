"""Real pairwise face-embedding comparison + NetworkX connected-component
analysis: if the same face (embedding similarity above threshold) shows
up under two different declared names/document numbers, that's a
multi-identity cluster — a real fraud signal, not a hardcoded flag.

Reports only the queried record's *direct* matches (1-hop neighbors in
the similarity graph), not the full transitively-connected component,
and this matters in practice, not just in theory: real testing against
the AT&T/Olivetti Faces dataset (40 people, 10 photos each — see
scripts/seed_identity_embeddings.py) found that at threshold 0.75, only
31 of 78000 impostor (different-person) pairs false-matched — but
connected-component transitivity turned that into single "clusters"
merging over a dozen unrelated people, because a false edge between A-B
and a separate one between B-C used to silently imply A and C were
clustered too. Direct-neighbor reporting doesn't have that failure
mode: a spurious edge stays local to the two records it actually
connects, instead of chaining unrelated identities together. See
_MATCH_THRESHOLD's docstring in app/services/face/classical_provider.py
for the full genuine/impostor tradeoff numbers behind the shared
threshold value.
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
            if len(embeddings[ids[i]]) != len(embeddings[ids[j]]):
                continue
            similarity = cosine_similarity(embeddings[ids[i]], embeddings[ids[j]])
            if similarity >= threshold:
                graph.add_edge(ids[i], ids[j], similarity=similarity)
    return graph


def find_multi_identity_cluster(graph: nx.Graph, node_id: str) -> IdentityGraphResult:
    if node_id not in graph:
        return IdentityGraphResult(
            status="NO_CLUSTER", cluster_size=0, members=[], reason=f"record {node_id} not found in graph"
        )

    # Direct neighbors only — not nx.node_connected_component's full
    # transitive closure. See this module's docstring for why: a rare
    # false-positive edge would otherwise silently chain unrelated
    # people into one reported "cluster" instead of staying local to the
    # two records it actually connects.
    component = set(graph.neighbors(node_id)) | {node_id}
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
                f"{len(component)} face embeddings directly matched (similarity >= "
                f"{DEFAULT_MATCH_THRESHOLD}) spanning {len(distinct_names)} "
                f"distinct declared name(s) and {len(distinct_docs)} distinct document number(s)"
            ),
        )
    return IdentityGraphResult(
        status="NO_CLUSTER",
        cluster_size=len(component),
        members=members,
        reason=f"embedding matches only its own declared identity ({len(component)} record(s) in cluster)",
    )
