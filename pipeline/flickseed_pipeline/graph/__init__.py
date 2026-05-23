"""Graph: station-to-station edges + candidate paths.

Edges: mutual k-NN (k=5-10) — gives uniform local density without the hubs and
orphans a similarity threshold would produce.

Outputs:
    data/derived/station_graph.json    nodes + edges
    data/derived/candidate_paths.json  top ~50 ranked paths between high-centrality
                                       endpoint pairs (score = local_coherence x
                                       drift x monotonicity x length_bonus, with a
                                       diversity filter <=30%% node overlap)

The ~50 candidates feed the manual curation step that produces lines.json.
"""
