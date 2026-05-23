"""Cluster: BERTopic over embeddings -> data/derived/stations.json.

BERTopic gives us station centroids and keyword sets in one pass, which solves
the naming problem (PROJECT.md §2). Target 25-40 stations; sweep min_topic_size
if the count drifts outside that range.
"""
